# /set-key — Set or update an API key

Update an API key in `/home/chepe52/projectAgent/agentCreator/.env`.

**Usage:** `/set-key <provider> <key>`
**Examples:**
- `/set-key openai sk-proj-abc123...`
- `/set-key anthropic sk-ant-api03-abc123...`
- `/set-key gemini AIza...`

**Arguments received:** $ARGUMENTS

## Steps

1. Parse `$ARGUMENTS` — expect two tokens: `<provider>` and `<key>`.
   If either is missing, show the usage examples above and stop.

2. Map the provider to its `.env` variable:
   - `openai` → `OPENAI_API_KEY` (must start with `sk-`)
   - `anthropic` → `ANTHROPIC_API_KEY` (must start with `sk-ant-`)
   - `gemini` → `GEMINI_API_KEY`

3. Validate the key format for the given provider. If it looks wrong, warn the user but still allow them to confirm and save it.

4. Read `/home/chepe52/projectAgent/agentCreator/.env`, update (or add) the correct variable with the new key, and write it back. Do NOT modify any other lines.

5. Confirm: "✓ `<VARIABLE>` updated in .env. You can now run `/build`."

Never print the full key back to the user — only show the first 8 characters followed by `****`.
