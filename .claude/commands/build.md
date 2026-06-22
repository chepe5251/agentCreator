# /build — Run the Agent Factory Enterprise pipeline

Build a complete AI agent project from a natural language description.

**User's project description:** $ARGUMENTS

## Steps

1. **Validate configuration** — Read `/home/chepe52/projectAgent/agentCreator/.env` and check that at least one provider key is set and valid:
   - `OPENAI_API_KEY` must start with `sk-`
   - OR `ANTHROPIC_API_KEY` must be non-empty
   - OR `GEMINI_API_KEY` must be non-empty
   - If none are valid, stop and tell the user to run `/set-key` first.

2. **Run the pipeline** — Execute this command (stream output so the user can follow progress):
   ```
   cd /home/chepe52/projectAgent/agentCreator && source venv/bin/activate && python main.py --prompt "$ARGUMENTS"
   ```

3. **Show results** — After the run finishes:
   - Print the final verdict (APPROVED or REJECTED) with the run ID
   - List all files generated under `/home/chepe52/projectAgent/agentCreator/output/`
   - If REJECTED, show the last audit feedback so the user knows what failed

If `$ARGUMENTS` is empty, ask the user: "What project do you want to build?"
