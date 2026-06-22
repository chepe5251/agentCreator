# /output — Browse the generated project files

Show the files the team generated in the last build.

**Optional filter:** $ARGUMENTS (e.g. a filename or extension like `.py` or `src/`)

## Steps

1. List all files under `/home/chepe52/projectAgent/agentCreator/output/` recursively (skip `__pycache__`, `venv`, `.git`).

2. If `$ARGUMENTS` is provided, filter the list to files that match (by path substring or extension).

3. For each file in the list, show its relative path and size in lines.

4. Ask the user: "Which file(s) do you want to read?" — then read and display the content of the requested files.

If the output directory is empty, tell the user to run `/build` first.
