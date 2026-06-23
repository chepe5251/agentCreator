---
name: building-an-agent
description: >
  Standard for designing, implementing, or reviewing an LLM-powered agent.
  Use whenever the task involves an agent's control loop, tool-calling contract,
  agent-pattern selection (single-shot / ReAct / plan-execute / multi-agent),
  state and memory boundaries, or the reliability and security requirements an
  agent must meet before it can be called production-ready. Builders follow it
  as a spec; auditors use it as a rubric.
---

# Building an Agent

An "agent" is an LLM placed inside a **bounded control loop** with **tools**. It is
NOT a single prompt-and-response. If your code calls the model once and returns the
text, you wrote a wrapper, not an agent. This skill defines what a correct agent looks
like and the mistakes that get a build rejected.

## 1. The agent loop (non-negotiable shape)

Every agent runs this loop:

```
system prompt (role + contract)  ──►  add user goal
        ▲                                   │
        │                                   ▼
        │                          model decides: answer OR call tool(s)
        │                                   │
        │            ┌──────────────────────┴───────────────────┐
        │         answer                                    tool call(s)
        │            │                                           │
        │            ▼                                           ▼
        │     return final text                      execute tool, append result
        │                                            as role:"tool" message
        └────────────────────────────────────────────────────────┘
                         (repeat, with a HARD round cap)
```

Rules that are always true:

- **Bound the loop.** A `for _ in range(MAX_TOOL_ROUNDS)` with a finite cap (e.g. 25),
  never `while True`. If the cap is hit, return an explicit error — do not silently stop.
- **Tool results go back as `role: "tool"`** with the matching `tool_call_id`, and the
  assistant message that requested them must be appended *with its `tool_calls`* before
  the tool results. Skipping the assistant turn corrupts the message history and the
  next call fails.
- **One source of truth for messages.** Append in order: system → user → assistant(tool_calls) → tool → assistant → … Never mutate earlier messages.
- **Termination is a decision, not an accident.** The loop ends when the model returns
  no tool calls (final answer) or the cap is reached. State both conditions explicitly.

## 2. Choose the right pattern (don't default to multi-agent)

| Pattern | Use when | Cost |
|---------|----------|------|
| **Single-shot** | Deterministic transform, no external data needed | Cheapest, most reliable |
| **ReAct / tool loop** (section 1) | Needs to look things up or act, ≤ a handful of steps | Medium |
| **Plan-then-execute** | Multi-step task where a plan up front reduces wandering | Medium-high |
| **Multi-agent** | Genuinely separable roles with handoffs, or parallel subtasks | Highest — only if a single agent measurably fails |

Default to the simplest pattern that solves the problem. Multi-agent adds coordination
cost, more failure modes, and more tokens. Over-engineering here is a rejection cause.

## 3. Tool-calling contract

- Tools are plain typed functions. The schema is derived from the signature, so
  **type every parameter** and write a docstring that states what the tool does and
  what each arg means — the model only sees the docstring.
- **Required vs optional** is decided by whether the param has a default. Make optional
  anything that has a sane default.
- **Return values the model can use.** Return a string or JSON-serializable object.
  On failure, return a *structured error string the model can recover from*
  (`"Error: file X not found"`), never raise into the loop.
- **Confine side effects.** A tool that writes files MUST resolve paths inside a fixed
  base dir and reject anything that escapes it (absolute paths, `../`). Treat every path
  the model gives you as hostile input. (See `agent-security` and `tool-design`.)
- **Idempotency where possible.** Re-running a tool with the same args shouldn't corrupt
  state; the model will sometimes retry.

## 4. State and memory boundaries

- **Working context** = the message list for the current task. Keep it lean; long
  histories degrade small models and blow context windows.
- **Persistence** = anything that must survive the process. Write it atomically
  (temp file + `os.replace`), never a bare `open(..., "w")` that can truncate on crash.
- **Session isolation.** One run's state must never leak into another. Key persistence
  by a run id.
- Decide *explicitly* what is short-term (in context) vs long-term (on disk/db). Don't
  stuff everything into the prompt "just in case." (See `memory-design`.)

## 5. Reliability requirements (auditors check these directly)

- **Timeout on every model call.** A hung call must fail, not block forever.
- **Retries** on transient failures (`num_retries`), with the timeout per attempt.
- **Bounded tool rounds** (section 1).
- **Robust structured-output parsing.** If you ask the model for JSON, do NOT parse it
  with a naive non-greedy regex — nested objects (`"issues": [{…}]`) break it. Prefer a
  fenced ```json``` block, then fall back to a **brace-balanced** extractor, then a
  keyword fallback. Validate the parsed object has the field you need before trusting it.
- **Don't block the event loop.** In async code, offload blocking I/O / subprocess work
  (`asyncio.to_thread`) if anything runs concurrently.
- **Provider-agnostic calls** (via a layer like LiteLLM) so the model is config, not code.

## 6. Security baseline

- File/tool side effects confined to a sandbox dir (section 3).
- **No secrets in code or prompts.** Credentials come from env vars only.
- Generated/third-party code is **untrusted** — run it sandboxed (container or, at
  minimum, confined paths + timeouts), never directly on the host with full permissions.
- Assume the user goal (and any retrieved content) may contain **prompt injection**.
  Tools that act on the world need confinement that the prompt cannot override.

## 7. Anti-patterns → automatic rejection

- `while True:` agent loop, or any loop without a hard cap.
- Model call with no `timeout` / no retry.
- Parsing nested JSON with `re.search(r"\{.*?\}")` (truncates at the first `}`).
- Tools that join a model-supplied path onto a base dir with no escape check.
- Hardcoded absolute paths (`/home/<user>/...`) instead of config/env-derived paths.
- Side effects at import time (creating dirs, network calls) — makes the module
  unimportable elsewhere and untestable.
- Pseudocode, `TODO`, or `pass` placeholders where real logic belongs.
- Tests that don't actually exercise agent behavior (no mocked LLM, no tool assertions).

## 8. Implementation rules (the parts models get wrong)

There is deliberately NO copy-paste skeleton here. Write the loop yourself from the
requirements above. These are hard rules — each one is a real bug that has shipped before:

- **Tool schemas must contain the real parameters.** Derive each tool's parameter names,
  types, and required-ness from its actual function signature. A schema with an empty
  `parameters: {}` or `{"properties": {}}` is WRONG — the model can never pass arguments, so
  every tool silently does nothing. Build the properties from the signature.
- **Tool-call arguments arrive as a JSON STRING, not a dict.** Parse before calling:
  `args = json.loads(tool_call.function.arguments or "{}")`, then `fn(**args)`. Doing
  `fn(**tool_call.function.arguments)` passes a string to `**` and raises TypeError — a
  guaranteed crash.
- **Never mock, stub, or simulate the LLM call.** The completion MUST hit a real provider
  (e.g. litellm `acompletion`). A function returning a hard-coded "simulated response",
  faking failures with `random`, or returning `'model'` / `['tool1']` is a placeholder and
  will be rejected.
- **The tool registry maps names to real callables.** `tool_map = {t.__name__: t for t in tools}`
  requires `tools` to be actual functions; a list of strings breaks `t.__name__`.
- **Imports must run from the project root.** Use ONE consistent import style across the whole
  project (a package with `__init__.py`, e.g. `from myproj.agent import run_agent`) so the
  entrypoint runs from a clean checkout. Never mix `from agent import ...` in one file with
  `from src.agent import ...` in another — only one works from a given working directory.
- **The loop body must contain, explicitly:** a bounded `for` over max rounds; the assistant
  message appended WITH its tool_calls before the tool results; each tool result appended as
  `role: "tool"` with the matching `tool_call_id`; return the content when there are no tool
  calls; return an explicit error string when the round cap is hit. Implement exactly the
  shape in section 1, in your own code.

If you are tempted to leave a helper body as a one-liner stub or a comment like `# simplified`
or `# assuming a function exists`, STOP and implement it fully. A stubbed helper is the single
most common reason a build is rejected.

## 9. Self-check before declaring "done"

Do not finish until ALL are true:

- [ ] Loop is bounded; both termination conditions are explicit.
- [ ] Every model call has a timeout and retries.
- [ ] Tool schemas come from typed signatures with real docstrings.
- [ ] Every tool returns a recoverable error string instead of raising into the loop.
- [ ] All file/tool side effects are confined to a sandbox dir; model paths are validated.
- [ ] Structured output is parsed robustly (fenced → brace-balanced → keyword), then validated.
- [ ] No secrets in code; all from env. No hardcoded absolute paths. No import-time side effects.
- [ ] The chosen pattern is the simplest that works (justify multi-agent if used).
- [ ] Tests (and ONLY tests) may mock the LLM; application code calls the REAL LLM client. Tests assert real tool/agent behavior and pass.
- [ ] The project installs and the entrypoint runs from a clean checkout.
