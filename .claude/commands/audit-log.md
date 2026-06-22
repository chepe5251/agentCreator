# /audit-log — Show the full audit report for a run

Display the detailed audit feedback (issues found, what was approved/rejected) for a pipeline run.

**Run ID (optional):** $ARGUMENTS

## Steps

1. If `$ARGUMENTS` is provided, look for that run directory under `/home/chepe52/projectAgent/agentCreator/logs/$ARGUMENTS/`.
   If not provided, use the most recently modified directory under `logs/`.

2. Read `history.json` from that run directory.

3. For each iteration in the history, display:
   - **Iteration number**
   - **Technical Auditor:** status + full feedback (including every issue with problem/why/fix/expected)
   - **Business Auditor:** status + full feedback (including every issue)

4. Read `summary_report.md` and show the final verdict.

If the run directory does not exist, list available runs from `logs/` so the user can pick the right one.
