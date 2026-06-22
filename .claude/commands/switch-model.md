# /switch-model — Switch the LLM provider

Change which AI models the pipeline uses by updating `.env`.

**Usage:** `/switch-model <provider>`
**Available providers:** `openai`, `anthropic`, `gemini`, `ollama`

**Arguments received:** $ARGUMENTS

## Provider → Model mapping

| Provider   | LLM_FAST_MODEL                        | LLM_REASONING_MODEL                   | LLM_ANALYSIS_MODEL                    | Key needed          |
|------------|---------------------------------------|---------------------------------------|---------------------------------------|---------------------|
| openai     | gpt-4o-mini                           | gpt-4o                                | gpt-4o-mini                           | OPENAI_API_KEY      |
| anthropic  | anthropic/claude-haiku-4-5-20251001   | anthropic/claude-sonnet-4-6           | anthropic/claude-haiku-4-5-20251001   | ANTHROPIC_API_KEY   |
| gemini     | gemini/gemini-2.0-flash               | gemini/gemini-2.5-pro                 | gemini/gemini-2.0-flash               | GEMINI_API_KEY      |
| ollama     | ollama/qwen2.5-coder:7b               | ollama/qwen2.5-coder:14b              | ollama/mistral:7b                     | none (local)        |

## Agent → Model assignment (ollama)
- **mistral:7b** (ANALYSIS) → PM, Research, Security, Cost, Business Auditor
- **qwen2.5-coder:7b** (FAST) → Prompt Engineer, RAG, Memory, QA, DevOps
- **qwen2.5-coder:14b** (REASONING) → Architect, Backend, Technical Auditor

## Steps

1. Parse `$ARGUMENTS` to get the provider name. If empty or unknown, show the table above and stop.

2. Read `/home/chepe52/projectAgent/agentCreator/.env`.

3. Update `LLM_FAST_MODEL`, `LLM_REASONING_MODEL`, and `LLM_ANALYSIS_MODEL` to the values from the table above.

4. For `ollama`, also set `OLLAMA_API_BASE=http://192.168.100.216:11434`.

5. Write the updated `.env` back. Do NOT touch any other lines.

6. Check whether the required API key for the chosen provider is already set in `.env`:
   - If yes (or provider is ollama): "✓ Switched to `<provider>`. Models updated. Ready to `/build`."
   - If no: "✓ Models updated. You still need to set `<KEY_NAME>` — run `/set-key <provider> <your-key>` first."
