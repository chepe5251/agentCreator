# /status — Check recent pipeline runs

Show the status of recent Agent Factory Enterprise runs.

## Steps

1. List all run directories inside `/home/chepe52/projectAgent/agentCreator/logs/`, sorted by most recent first (limit to last 10).

2. For each run directory found, read its `summary_report.md` (if it exists) and extract:
   - Run ID
   - Final verdict (APPROVED / REJECTED)
   - Total iterations executed
   - The project prompt that was used

3. Display a clean summary table like this:
   ```
   RUN ID                          VERDICT    ITERATIONS  PROJECT
   run_20260621_120000_abc12345    APPROVED   2           "a todo list API"
   run_20260621_115500_def67890    REJECTED   10          "a RAG chatbot"
   ```

4. At the end, show the path to the output directory and how many files are currently there:
   `/home/chepe52/projectAgent/agentCreator/output/` → N files

If there are no runs yet, tell the user to run `/build` first.
