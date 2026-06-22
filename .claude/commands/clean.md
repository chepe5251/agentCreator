# /clean — Clear the output directory for a fresh build

Delete all generated files so the next `/build` starts from scratch.

**What to clean (optional):** $ARGUMENTS
- `output` (default) — clears only the generated project files
- `logs` — clears only the run history logs
- `all` — clears both output and logs

## Steps

1. Determine what to clean based on `$ARGUMENTS` (default to `output` if empty).

2. **Always ask for confirmation before deleting anything.** Show the user exactly what will be deleted and how many files/directories are affected.

3. If confirmed:
   - For `output`: delete all contents of `/home/chepe52/projectAgent/agentCreator/output/` (not the directory itself)
   - For `logs`: delete all contents of `/home/chepe52/projectAgent/agentCreator/logs/` (not the directory itself)
   - For `all`: delete contents of both

4. Confirm deletion is complete and tell the user they can now run `/build` with a new prompt.
