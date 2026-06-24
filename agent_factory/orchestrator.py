import json
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, Tuple, List
from agent_factory.config import MAX_AUDIT_ITERATIONS
from agent_factory.agents import get_agent
from agent_factory.memory import IterationMemory
from agent_factory.project_state import ProjectState
import sys
from agent_factory.tools import (
    list_project_files, check_python_syntax, run_project_tests, lint_code,
    install_dependencies,
)


def _balanced_json(text: str, start: int) -> str | None:
    """Extracts the JSON object starting at `start` by counting braces."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_block(text: str) -> dict | None:
    """Finds the auditor verdict JSON: prefers fenced blocks, then largest bare block with 'status'."""
    # 1. Try ```json ... ``` fenced blocks (last fence first — verdict goes at the end)
    for raw in reversed(re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)):
        try:
            data = json.loads(raw)
            if "status" in data:
                return data
        except Exception:
            continue

    # 2. Fall back to bare balanced { } blocks; sort largest→smallest (outermost first)
    bare: List[str] = []
    for m in re.finditer(r"\{", text):
        block = _balanced_json(text, m.start())
        if block:
            bare.append(block)

    for block in sorted(bare, key=len, reverse=True):
        try:
            data = json.loads(block)
            if "status" in data:
                return data
        except Exception:
            continue

    return None


def _extract_json_array(text: str) -> list:
    """Extracts a JSON array of objects from model text (the architect's build plan)."""
    for raw in reversed(re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            continue
    start = text.find("[")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, list):
                            return data
                    except Exception:
                        break
        start = text.find("[", start + 1)
    return []


def parse_auditor_response(text: str) -> Dict[str, Any]:
    """Extracts the structured audit JSON from model output."""
    # Detect truncated response: agent ran out of tool rounds before producing verdict
    if "maximum tool" in text.lower() or (
        text.strip().startswith("{") and '"function"' in text and '"status"' not in text
    ):
        return {
            "status": "REJECTED",
            "summary": "Auditor ran out of tool rounds before producing a verdict.",
            "feedback": "Auditor exhausted tool call budget. Increase max_tool_rounds or reduce files to audit.",
            "issues": [{
                "file": "system",
                "severity": "HIGH",
                "problem": "Auditor did not complete its analysis.",
                "why": "The agent hit the tool call limit before reading all files and emitting a verdict.",
                "fix": "Reduce the number of files in output/ or increase max_tool_rounds for the auditor.",
                "expected": "A structured JSON verdict with status, summary, issues[], and feedback.",
            }],
        }

    data = _extract_json_block(text)
    if data is not None:
        data.setdefault("feedback", data.get("summary", text))
        data.setdefault("issues", [])
        return data

    # Fallback: keyword scan
    up = text.upper()
    status = "APPROVED" if ("APPROVED" in up and "REJECTED" not in up) else "REJECTED"
    return {"status": status, "feedback": text, "issues": []}


def _format_audit_brief(audit: Dict[str, Any], auditor_name: str) -> str:
    """Formats a rich audit result into a clear, actionable developer brief."""
    lines = [f"### {auditor_name} — {audit.get('status', 'REJECTED')}"]
    summary = audit.get("summary") or audit.get("feedback", "")
    if summary:
        lines.append(f"**Verdict:** {summary}\n")

    issues = audit.get("issues", [])
    if issues:
        lines.append(f"**{len(issues)} issue(s) found:**\n")
        for i, issue in enumerate(issues, 1):
            sev = issue.get("severity", "?")
            # technical auditor uses 'file', business uses 'area'
            location = issue.get("file") or issue.get("area", "General")
            lines.append(f"#### Issue {i} [{sev}] — `{location}`")
            lines.append(f"**What is wrong:** {issue.get('problem', '')}")
            lines.append(f"**Why it matters:** {issue.get('why', '')}")
            lines.append(f"**How to fix it:** {issue.get('fix', '')}")
            lines.append(f"**Expected result:** {issue.get('expected', '')}\n")
    else:
        lines.append(audit.get("feedback", ""))

    positives = audit.get("positive", [])
    if positives:
        lines.append("**What was done well:**")
        for p in positives:
            lines.append(f"- {p}")

    return "\n".join(lines)

class EnterpriseOrchestrator:
    """Orchestrates the build-review-fix-audit loop for Agent Factory Enterprise."""
    
    def __init__(self, run_id: str, project_prompt: str):
        self.run_id = run_id
        self.project_prompt = project_prompt
        self.memory = IterationMemory(run_id)
        self.requirements_brief = ""
        self.build_plan = []
        from agent_factory.config import OUTPUT_DIR
        from agent_factory.tools import set_active_output
        self.output_dir = OUTPUT_DIR / run_id
        set_active_output(self.output_dir)
        self.state = None   # initialized in run() once requirements are gathered

    async def run(self) -> Tuple[bool, str]:
        """Runs the orchestrator loop. Returns (is_approved, summary_report)."""
        iteration = 1
        approved = False
        latest_feedback = ""
        self._tech_latched = False
        self._bus_latched = False

        print(f"[*] Starting Agent Factory Enterprise pipeline for Run: {self.run_id}")
        print(f"[*] Project Prompt: {self.project_prompt}")
        print(f"[*] Output dir: {self.output_dir}")
        await self._phase_discovery()
        self.state = ProjectState(self.output_dir, self.project_prompt, self.requirements_brief)

        while not approved and iteration <= MAX_AUDIT_ITERATIONS:
            print(f"\n=================== ITERATION {iteration} ===================")
            self.state.set_iteration(iteration)

            # Step 1: Build Phase
            deliverables = await self._phase_build(iteration, latest_feedback)

            # Install deps deterministically so review, audit, and backstop all use a live venv
            if any(f == "requirements.txt" for f in list_project_files()):
                print("[*] Installing dependencies into the run venv...")
                print("    " + install_dependencies())

            # Step 2: Review / Analyze Phase
            reviews = await self._phase_review(iteration, deliverables)
            
            # Step 3: Audit Phase
            tech_audit, bus_audit = await self._phase_audit(iteration)
            
            # Record audit results in shared project state
            self.state.record_audit(iteration, "technical", tech_audit.get("status"), tech_audit.get("issues", []))
            self.state.record_audit(iteration, "business", bus_audit.get("status"), bus_audit.get("issues", []))

            # Save results to memory
            self.memory.log_iteration(
                iteration=iteration,
                deliverables=deliverables,
                reviews=reviews,
                audits={
                    "technical_auditor": tech_audit,
                    "business_auditor": bus_audit
                }
            )
            
            # Step 4: Backstop — objective verification regardless of auditor verdict
            backstop_ok, backstop_report = self._run_backstop()

            # Check Approval
            tech_ok = tech_audit.get("status") == "APPROVED"
            bus_ok  = bus_audit.get("status") == "APPROVED"

            # If auditors approved but objective checks fail, force rejection
            if tech_ok and not backstop_ok:
                tech_audit["status"] = "REJECTED"
                tech_audit.setdefault("issues", []).insert(0, {
                    "file": "system-backstop",
                    "severity": "CRITICAL",
                    "problem": "Objective verification failed despite auditor approval.",
                    "why": "Syntax errors or test failures detected by direct pipeline checks.",
                    "fix": backstop_report,
                    "expected": "All .py files parse without errors and all tests pass.",
                })
                tech_ok = False
                print(f"[!] Backstop OVERRODE auditor approval — objective checks failed.")

            tech_issues = tech_audit.get("issues", [])
            bus_issues  = bus_audit.get("issues", [])
            print(f"[*] Iteration {iteration} Audit Results:")
            print(f"    - Technical Auditor: {tech_audit.get('status')} | {len(tech_issues)} issue(s) | {tech_audit.get('summary', tech_audit.get('feedback', ''))[:120]}")
            print(f"    - Business Auditor:  {bus_audit.get('status')} | {len(bus_issues)} issue(s) | {bus_audit.get('summary', bus_audit.get('feedback', ''))[:120]}")
            if backstop_ok:
                print(f"    - Backstop:          PASSED")
            else:
                print(f"    - Backstop:          FAILED — {backstop_report[:120]}")

            # Latch approvals so the loop converges instead of oscillating between auditors.
            # Technical approval persists ONLY while the objective backstop keeps passing;
            # an objective regression (backstop fail) un-latches it. Business has no objective
            # guard, so once given it stays (the backstop still guarantees the code runs).
            if tech_ok and backstop_ok:
                self._tech_latched = True
            if not backstop_ok:
                self._tech_latched = False
            if bus_ok:
                self._bus_latched = True

            effective_tech = tech_ok or (self._tech_latched and backstop_ok)
            effective_bus  = bus_ok or self._bus_latched

            if effective_tech and effective_bus:
                approved = True
                why = []
                if not tech_ok:
                    why.append("technical approval latched (backstop still passing)")
                if not bus_ok:
                    why.append("business approval latched")
                note = f" ({'; '.join(why)})" if why else ""
                print(f"[+] PROJECT APPROVED at iteration {iteration}!{note}")
                break

            # Feed back ONLY the auditors that still reject, so the developer does not
            # rework already-approved code and regress it.
            pending_tech = None if effective_tech else tech_audit
            pending_bus  = None if effective_bus else bus_audit
            latest_feedback = self._build_feedback_brief(iteration, pending_tech, pending_bus)
            
            iteration += 1
            
        summary = self._generate_final_summary(approved, iteration - 1)
        return approved, summary

    def _extract_build_plan(self, text: str) -> list:
        """Parses the architect's [{file, purpose}] build plan from its output."""
        plan = []
        for item in _extract_json_array(text):
            if isinstance(item, dict) and item.get("file"):
                plan.append({
                    "file": str(item["file"]).strip(),
                    "purpose": str(item.get("purpose", "")).strip(),
                })
        return plan

    def _with_state(self, instruction: str) -> str:
        """Prepends the shared project state to an agent instruction."""
        if self.state is None:
            return instruction
        return self.state.as_briefing() + "\n" + instruction

    async def _phase_build(self, iteration: int, audit_feedback: str) -> Dict[str, str]:
        """Runs the build phase where PM, Researchers, Architects, and Developers write output."""
        deliverables = {}
        
        if iteration == 1:
            print("[*] Phase: Build (Initial Specification & Coding)")

            # CEO / PM initial spec
            async with get_agent("pm") as pm:
                response = await pm.chat(self._with_state(
                    f"The user wants to build the following project: '{self.project_prompt}'.\n\n"
                    f"Requirements gathered during discovery:\n{self.requirements_brief}\n\n"
                    "Analyze the requirements, define the scope, and create a specification in "
                    "'spec.md'. Honor the user's answers; where an answer says 'no preference', "
                    "choose sensibly and note the decision in the spec."
                ))
                deliverables["pm"] = await response.text()

            # Research
            async with get_agent("research") as research:
                response = await research.chat(self._with_state(
                    "Research the best technologies and libraries to fulfill 'spec.md'.\n"
                    "Write your conclusions in 'research.md'."
                ))
                deliverables["research"] = await response.text()

            # Architect — designs the architecture AND the concrete file plan for THIS project
            async with get_agent("architect") as arch:
                response = await arch.chat(self._with_state(
                    f"The user's actual request is: '{self.project_prompt}'.\n"
                    "Design the system that fulfills THAT request specifically — NOT a generic "
                    "agent template. Read 'spec.md' and 'requirements.md' first and ground every "
                    "decision in what the user actually asked for.\n\n"
                    "Save the architecture in 'architecture.md'. Then decide the exact set of "
                    "source files the developers must create to implement THIS specific project, "
                    "derived from the requirement — NOT a fixed template. Do NOT assume the project "
                    "needs a database, RAG, or a memory module unless the spec requires it.\n"
                    "Every file in your plan must be a REAL component of the user's system. Do NOT "
                    "include demo/sample tools (calculators, example fetchers) or simulated/mock "
                    "LLM clients — those are placeholders, not deliverables.\n"
                    "At the END of your response, output ONLY a JSON array of the files to build, "
                    'each as {"file": "<path>", "purpose": "<what this file does>"}. Example: '
                    '[{"file":"src/main.py","purpose":"CLI entry point and main loop"},'
                    '{"file":"src/auditor.py","purpose":"tool-based checks returning a verdict"}]. '
                    "Include the entry point and every file the project needs — source modules, and "
                    "ONLY IF genuinely required, deployment files or analysis docs (most local CLI "
                    "tools need neither)."
                ))
                arch_text = await response.text()
                deliverables["architect"] = arch_text
                self.build_plan = self._extract_build_plan(arch_text)
                self.state.set_architecture(arch_text, self.build_plan)

            # Prompt Engineer
            async with get_agent("prompt") as pe:
                response = await pe.chat(self._with_state(
                    "Design the prompt strategy and system instructions required for the project and save them in 'prompts.md'."
                ))
                deliverables["prompt"] = await response.text()

            # Developers: build each file from the architect's plan (generalist developer per module)
            print("[*] Phase: Coding (per architecture plan)")
            if not self.build_plan:
                print("[!] No structured build plan from architect; using single-file fallback.")
                self.build_plan = [{"file": "src/main.py", "purpose": "Entry point implementing the spec"}]

            for module in self.build_plan:
                f, purpose = module["file"], module["purpose"]
                print(f"    - building {f}")
                async with get_agent("backend") as dev:
                    response = await dev.chat(self._with_state(
                        f"Implement the file '{f}' for this project.\n"
                        f"Purpose of this file: {purpose}\n\n"
                        "Read 'spec.md' and 'architecture.md' first, and read any already-created source files "
                        "this one depends on. Write complete, runnable code — no placeholders, no TODOs, no "
                        "NotImplementedError, no 'for demonstration' or 'this would invoke ...' comments in place "
                        "of real wiring (if this file coordinates other modules, actually import and call them), "
                        "no mock/simulated LLM clients, and no empty tool schemas (build tool "
                        "parameters from the function signature; json.loads tool-call arguments before calling). "
                        "If this file needs third-party packages, add them to "
                        "'requirements.txt' (real pip packages only, never stdlib modules like json/os/typing)."
                    ))
                    deliverables[f"dev::{f}"] = await response.text()
                    self.state.record_contribution(
                        f"dev:{f}",
                        f"Implemented {f}: {module['purpose']}"
                    )

        else:
            # Fix phase
            print(f"[*] Phase: Fix & Correct (Iteration {iteration})")

            # PM reviews the full audit brief and creates a correction plan
            async with get_agent("pm") as pm:
                response = await pm.chat(self._with_state(
                    f"The auditors rejected the deliverable at iteration {iteration - 1}.\n\n"
                    f"{audit_feedback}\n\n"
                    "Your tasks:\n"
                    "1. Read the current project files using read_project_file and list_project_files.\n"
                    "2. Update 'spec.md' with a correction plan that assigns each issue to the responsible specialist.\n"
                    "3. At the end of your response, write a '## TASKS PER SPECIALIST' section with concrete, "
                    "specific instructions for: Backend Engineer, RAG Specialist, and Memory Engineer. "
                    "Include the exact files to modify and the changes required based on the auditor feedback."
                ))
                deliverables["pm"] = await response.text()
                pm_instructions = deliverables["pm"]
                self.state.record_contribution(
                    f"pm:fix_iter_{iteration}",
                    f"[fix iter {iteration}] PM wrote correction plan"
                )

            # One generalist developer applies ALL fixes across whatever files are affected
            async with get_agent("backend") as dev:
                response = await dev.chat(self._with_state(
                    f"## PM correction plan\n{pm_instructions}\n\n"
                    f"## Full audit report\n{audit_feedback}\n\n"
                    "Apply ALL fixes listed. For EACH file you change: FIRST read its current contents "
                    "with read_project_file. For a small or localized fix (a syntax error, wrong "
                    "indentation, a few bad lines), use str_replace_in_file to change ONLY those exact "
                    "lines — do NOT rewrite the whole file. Only when changes are extensive, write back "
                    "the COMPLETE file. CRITICAL: preserve every existing function, class, import, and line that is "
                    "NOT part of the fix. NEVER shorten a file, gut it, or replace working code with stubs, "
                    "'pass', or 'for demonstration' comments — a file must only become MORE correct between "
                    "iterations, never lose functionality. If a file orchestrates other modules, actually "
                    "import and call them — no 'this would invoke ...' placeholder comments. No TODOs, no mock logic."
                ))
                deliverables["developer"] = await response.text()
                self.state.record_contribution(
                    f"dev:fix_iter_{iteration}",
                    f"[fix iter {iteration}] applied corrections per audit feedback"
                )

        return deliverables

    async def _phase_review(self, iteration: int, deliverables: Dict[str, str]) -> Dict[str, str]:
        """Runs the analyst review phase (QA, Security, DevOps, Cost)."""
        print("[*] Phase: Review & Analysis")
        reviews = {}
        
        # QA creates test suite
        async with get_agent("qa") as qa:
            response = await qa.chat(self._with_state(
                "First call list_project_files to see what source files actually exist. Then write or "
                "UPDATE automated tests in a SINGLE file 'tests/test_app.py' that exercise the ACTUAL "
                "modules in src/ — never assumed modules like backend/RAG/memory if they don't exist. "
                "Do NOT create new or duplicate test files (no *_updated, no temp_* files); edit "
                "tests/test_app.py in place — read its current contents first and preserve existing "
                "passing tests. Use unittest. Then run the run_project_tests tool."
            ))
            reviews["qa"] = await response.text()

        # Security review
        async with get_agent("security") as sec:
            response = await sec.chat(self._with_state(
                "Perform a security review of the current code and write 'security_review.md'. "
                "Look for credential leaks, command injection vulnerabilities, and insecure dependencies."
            ))
            reviews["security"] = await response.text()

        return reviews

    async def _phase_audit(self, iteration: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Runs the dual auditors to approve or reject the deliverables."""
        print("[*] Phase: Audit & Compliance")
        files = list_project_files()
        files_str = "\n".join(f"  - {f}" for f in files)

        # Technical Auditor
        async with get_agent("technical_auditor") as ta:
            response = await ta.chat(self._with_state(
                f"## Original user requirement\n{self.project_prompt}\n\n"
                f"## Files generated in this iteration ({iteration})\n{files_str}\n\n"
                "## Instructions\n"
                "1. Call read_project_file on EVERY file listed — do not skip any.\n"
                "2. Call check_python_syntax on every .py file.\n"
                "3. Call run_project_tests and analyze the full output.\n"
                "4. For each issue found, document: exact file, what is wrong, "
                "why it matters, and how to fix it with concrete code.\n"
                "5. Output your verdict using the required structured JSON (status, summary, issues[], positive[], feedback)."
            ))
            ta_text = await response.text()
            ta_audit = parse_auditor_response(ta_text)

        # Business Auditor
        async with get_agent("business_auditor") as ba:
            response = await ba.chat(self._with_state(
                f"## Original user requirement\n{self.project_prompt}\n\n"
                f"## Files generated in this iteration ({iteration})\n{files_str}\n\n"
                "## Instructions\n"
                "1. Call read_project_file on spec.md, architecture.md, prompts.md, and all source files.\n"
                "2. Compare EACH implemented feature against the original user requirement.\n"
                "3. Identify: missing requirements, unnecessary complexity, misaligned agent behavior.\n"
                "4. For each issue, specify: affected area, what is missing or wrong, "
                "why it matters to the user, and exactly how to fix it.\n"
                "5. Output your verdict using the required structured JSON (status, summary, issues[], positive[], feedback)."
            ))
            ba_text = await response.text()
            ba_audit = parse_auditor_response(ba_text)

        return ta_audit, ba_audit

    def _parse_questions(self, raw: str) -> list:
        """Extracts a JSON array of questions from PM output."""
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
            return [str(q).strip() for q in data if str(q).strip()]
        except Exception:
            return []

    async def _ask_questions(self, questions: list) -> list:
        """Prints questions and collects answers from stdin without blocking the event loop."""
        qa = []
        for i, q in enumerate(questions, 1):
            try:
                ans = await asyncio.to_thread(input, f"\n  [{i}/{len(questions)}] {q}\n  > ")
            except EOFError:
                ans = ""
            qa.append((q, ans.strip() or "(no preference — use best judgment)"))
        return qa

    async def _phase_discovery(self) -> None:
        """Interactive discovery: the PM interviews the user before the build phase."""
        if not sys.stdin.isatty():
            self.requirements_brief = "(Non-interactive run — building from the initial prompt only.)"
            return

        print("\n=================== DISCOVERY ===================")
        print("[*] The PM will ask clarifying questions before writing any spec.")

        transcript, MAX_ROUNDS = [], 1
        ctx = f"User's initial idea: '{self.project_prompt}'"

        for _ in range(MAX_ROUNDS):
            async with get_agent("pm_interviewer") as pm:
                response = await pm.chat(
                    f"{ctx}\n\n"
                    "You are interviewing the user to fully understand what they want to build "
                    "BEFORE any spec is written. Ask every clarifying question you genuinely need "
                    "(scope, target users, must-have features, tech/runtime constraints, data "
                    "sources, integrations, success criteria).\n"
                    "Output ONLY a JSON array of question strings, e.g. "
                    '["Question 1?", "Question 2?"]. If you already have enough info, output exactly [].'
                )
                raw = await response.text()

            questions = self._parse_questions(raw)[:5]   # tope duro de 5 preguntas totales
            if not questions:
                break
            qa = await self._ask_questions(questions)
            transcript.extend(qa)
            answered = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa)
            ctx = f"User's initial idea: '{self.project_prompt}'\n\nAnswers so far:\n{answered}"

        if transcript:
            brief = "\n".join(f"- {q}\n  -> {a}" for q, a in transcript)
        else:
            brief = "(PM had enough information from the initial idea — no questions needed.)"
        self.requirements_brief = brief

        from agent_factory.tools import write_project_file
        write_project_file(
            "requirements.md",
            f"# Requirements (discovery)\n\n## Initial idea\n{self.project_prompt}\n\n## Q&A\n{brief}\n",
        )
        print("\n[+] Discovery complete. Requirements saved to requirements.md\n")

    def _build_feedback_brief(
        self, iteration: int, tech_audit: Dict[str, Any] = None, bus_audit: Dict[str, Any] = None
    ) -> str:
        """Builds a developer-ready brief from the auditors that still REJECT.
        An auditor passed as None has already approved and is omitted, so the developer
        does not touch already-approved work."""
        briefs, all_issues = [], []
        if tech_audit is not None:
            briefs.append(_format_audit_brief(tech_audit, "Technical Auditor"))
            all_issues += tech_audit.get("issues", [])
        if bus_audit is not None:
            briefs.append(_format_audit_brief(bus_audit, "Business Auditor"))
            all_issues += bus_audit.get("issues", [])

        critical = [i for i in all_issues if i.get("severity") == "CRITICAL"]
        high = [i for i in all_issues if i.get("severity") == "HIGH"]

        only_note = ""
        if tech_audit is None:
            only_note = ("The Technical Auditor already APPROVED — do NOT modify working code or "
                         "tests; fix ONLY the business issues below.\n")
        elif bus_audit is None:
            only_note = ("The Business Auditor already APPROVED — do NOT change scope or files it "
                         "accepted; fix ONLY the technical issues below.\n")

        header = (
            f"# AUDIT REJECTED — Iteration {iteration}\n\n"
            f"**Executive summary:** {len(all_issues)} total issue(s) — "
            f"{len(critical)} CRITICAL, {len(high)} HIGH.\n"
            f"{only_note}"
            "Resolve the issues below WITHOUT touching code unrelated to them.\n\n"
            "---\n"
        )
        return header + "\n\n" + "\n\n---\n\n".join(briefs)

    def _run_backstop(self) -> Tuple[bool, str]:
        """Objectively verifies output: syntax-checks all .py files and runs tests.
        Returns (passed, report). Does not call any LLM."""
        failures = []
        py_files = [f for f in list_project_files() if f.endswith(".py")]
        for f in py_files:
            result = check_python_syntax(f)
            if "Syntax Error" in result:
                failures.append(result)

        lint_result = lint_code(".")
        if "issues" in lint_result.lower() and "no issues" not in lint_result.lower():
            failures.append(lint_result[:400])

        test_result = run_project_tests()
        if "does not exist" in test_result:
            failures.append("No tests/ directory found — core functionality must have automated tests.")
        elif "FAILED" in test_result or "Execution error" in test_result:
            failures.append(test_result[:500])

        if failures:
            return False, " | ".join(failures)
        return True, "All syntax checks, linting, and tests passed."

    def _generate_final_summary(self, approved: bool, total_iterations: int) -> str:
        """Generates a summary markdown report of the pipeline run."""
        status_str = "APPROVED" if approved else "REJECTED"
        history = self.memory.load_history()
        
        report_lines = [
            f"# Agent Factory Enterprise Pipeline Summary",
            f"**Run ID:** {self.run_id}",
            f"**Project Prompt:** {self.project_prompt}",
            f"**Final Verdict:** {status_str}",
            f"**Total Iterations executed:** {total_iterations}",
            "",
            "## Iteration History",
        ]
        
        for record in history:
            it = record.get("iteration")
            audits = record.get("audits", {})
            ta = audits.get("technical_auditor", {})
            ba = audits.get("business_auditor", {})
            
            report_lines.append(f"### Iteration {it}")
            report_lines.append(f"- **Technical Auditor:** {ta.get('status')}")
            report_lines.append(f"- **Business Auditor:** {ba.get('status')}")
            report_lines.append("")
            
        # Write report to log folder
        report = "\n".join(report_lines)
        report_path = self.memory.run_dir / "summary_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
            
        # Also write summary into the project output dir
        try:
            summary_out = self.output_dir / "enterprise_summary.md"
            summary_out.parent.mkdir(exist_ok=True, parents=True)
            with open(summary_out, "w", encoding="utf-8") as f:
                f.write(report)
        except Exception:
            pass
            
        return report
