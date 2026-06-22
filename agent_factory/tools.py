import os
import subprocess
import py_compile
from pathlib import Path
from typing import List

OUTPUT_DIR = Path("/home/chepe52/projectAgent/agentCreator/output")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def write_project_file(filepath: str, content: str) -> str:
    """Writes content to a file in the generated project directory.

    Args:
        filepath: Relative path to the file from the project root (e.g. 'src/main.py').
        content: The text/code contents of the file.
    """
    target = OUTPUT_DIR / filepath
    target.parent.mkdir(exist_ok=True, parents=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"File successfully written to: {filepath}"

def read_project_file(filepath: str) -> str:
    """Reads the contents of a file in the generated project directory.

    Args:
        filepath: Relative path to the file (e.g. 'src/main.py').
    """
    target = OUTPUT_DIR / filepath
    if not target.exists():
        return f"Error: File {filepath} does not exist."
    with open(target, "r", encoding="utf-8") as f:
        return f.read()

def list_project_files() -> List[str]:
    """Lists all files in the generated project directory (excluding system/virtualenv folders)."""
    files = []
    for root, _, filenames in os.walk(OUTPUT_DIR):
        for name in filenames:
            path = Path(root) / name
            rel = path.relative_to(OUTPUT_DIR)
            # Skip virtual environments and cached pyc
            if "venv" in rel.parts or "__pycache__" in rel.parts or ".git" in rel.parts:
                continue
            files.append(str(rel))
    return files

def check_python_syntax(filepath: str) -> str:
    """Performs a Python syntax compilation check on the file.

    Args:
        filepath: Relative path to the Python file (e.g. 'src/main.py').
    """
    target = OUTPUT_DIR / filepath
    if not target.exists():
        return f"Error: File {filepath} does not exist."
    try:
        py_compile.compile(str(target), doraise=True)
        return f"Syntax OK for {filepath}."
    except py_compile.PyCompileError as e:
        return f"Syntax Error in {filepath}:\n{str(e)}"

def run_project_tests(test_script: str = "tests") -> str:
    """Runs tests for the generated project using unittest.

    Args:
        test_script: Directory or module containing tests, default is 'tests'.
    """
    test_path = OUTPUT_DIR / test_script
    if not test_path.exists():
        return f"Error: Test folder '{test_script}' does not exist in output. Can't run tests."
    
    # Run python -m unittest in the output directory
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", test_script],
            cwd=str(OUTPUT_DIR),
            capture_output=True,
            text=True,
            timeout=15
        )
        output = f"Stdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        if res.returncode == 0:
            return f"Tests PASSED successfully.\n{output}"
        else:
            return f"Tests FAILED (Exit Code {res.returncode}).\n{output}"
    except Exception as e:
        return f"Execution error while running tests: {str(e)}"
