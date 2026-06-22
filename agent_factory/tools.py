import os
import subprocess
import py_compile
from pathlib import Path
from typing import List

from agent_factory.config import OUTPUT_DIR


def _safe_target(filepath: str) -> Path:
    """Resolves filepath inside OUTPUT_DIR and raises if it escapes the sandbox."""
    base = OUTPUT_DIR.resolve()
    target = (base / filepath).resolve()
    if target == base or base not in target.parents:
        raise ValueError(f"Path outside output/: {filepath!r}")
    return target


_CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".yaml", ".yml", ".toml", ".json"}

def _strip_markdown_fences(content: str, filepath: str) -> str:
    """Strips ```lang ... ``` fences that local LLMs sometimes write into source files."""
    ext = Path(filepath).suffix.lower()
    if ext not in _CODE_EXTENSIONS:
        return content
    stripped = content.strip()
    # Match opening fence: ```python, ```py, ```yaml, ``` alone, etc.
    first_newline = stripped.find("\n")
    if stripped.startswith("```") and first_newline != -1:
        first_line = stripped[:first_newline].strip()
        # Validate it looks like a fence line (``` optionally followed by a lang identifier)
        if first_line == "```" or (first_line.startswith("```") and first_line[3:].isalpha()):
            body = stripped[first_newline + 1:]
            if body.rstrip().endswith("```"):
                body = body.rstrip()[:-3].rstrip()
            return body
    return content


def write_project_file(filepath: str, content: str) -> str:
    """Writes content to a file in the generated project directory.

    Args:
        filepath: Relative path to the file from the project root (e.g. 'src/main.py').
        content: The text/code contents of the file.
    """
    try:
        target = _safe_target(filepath)
    except ValueError as e:
        return f"Error: {e}"
    content = _strip_markdown_fences(content, filepath)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"File successfully written to: {filepath}"


def read_project_file(filepath: str) -> str:
    """Reads the contents of a file in the generated project directory.

    Args:
        filepath: Relative path to the file (e.g. 'src/main.py').
    """
    try:
        target = _safe_target(filepath)
    except ValueError as e:
        return f"Error: {e}"
    if not target.exists():
        return f"Error: File {filepath} does not exist."
    return target.read_text(encoding="utf-8")


def list_project_files() -> List[str]:
    """Lists all files in the generated project directory (excluding system/virtualenv folders)."""
    files = []
    if not OUTPUT_DIR.exists():
        return files
    for root, _, filenames in os.walk(OUTPUT_DIR):
        for name in filenames:
            path = Path(root) / name
            rel = path.relative_to(OUTPUT_DIR)
            if "venv" in rel.parts or "__pycache__" in rel.parts or ".git" in rel.parts:
                continue
            files.append(str(rel))
    return files


def check_python_syntax(filepath: str) -> str:
    """Performs a Python syntax compilation check on the file.

    Args:
        filepath: Relative path to the Python file (e.g. 'src/main.py').
    """
    try:
        target = _safe_target(filepath)
    except ValueError as e:
        return f"Error: {e}"
    if not target.exists():
        return f"Error: File {filepath} does not exist."
    try:
        py_compile.compile(str(target), doraise=True)
        return f"Syntax OK for {filepath}."
    except py_compile.PyCompileError as e:
        return f"Syntax Error in {filepath}:\n{str(e)}"


def install_dependencies(requirements_file: str = "requirements.txt") -> str:
    """Installs Python packages listed in a requirements file found inside output/.

    Args:
        requirements_file: Relative path to the requirements file (default: 'requirements.txt').
    """
    try:
        target = _safe_target(requirements_file)
    except ValueError as e:
        return f"Error: {e}"
    if not target.exists():
        return f"Error: {requirements_file} does not exist in output/."
    try:
        res = subprocess.run(
            ["pip", "install", "-r", str(target), "--quiet", "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if res.returncode == 0:
            return f"Dependencies installed successfully from {requirements_file}."
        return f"Dependency installation failed:\n{res.stderr[:600]}"
    except subprocess.TimeoutExpired:
        return "Error: dependency installation timed out after 180s."
    except Exception as e:
        return f"Error installing dependencies: {e}"


def lint_code(filepath: str = ".") -> str:
    """Runs ruff (fallback: flake8) on a file or directory inside output/.

    Args:
        filepath: Relative path to lint, or '.' to lint the entire output/ directory.
    """
    if filepath == ".":
        target = OUTPUT_DIR
    else:
        try:
            target = _safe_target(filepath)
        except ValueError as e:
            return f"Error: {e}"
    if not target.exists():
        return f"Error: {filepath} does not exist in output/."

    for linter_cmd in [["ruff", "check", str(target)], ["flake8", str(target)]]:
        try:
            res = subprocess.run(linter_cmd, capture_output=True, text=True, timeout=30)
            tool = linter_cmd[0]
            if res.returncode == 0:
                return f"{tool}: No issues found in {filepath}."
            return f"{tool} issues in {filepath}:\n{(res.stdout + res.stderr)[:1000]}"
        except FileNotFoundError:
            continue
        except Exception as e:
            return f"Linter error: {e}"
    return "Error: neither ruff nor flake8 is installed. Run: pip install ruff"


def run_program(entrypoint: str = "src/main.py", args: str = "") -> str:
    """Executes the generated program and captures its output (30s timeout).

    NOTE: runs LLM-generated code directly — use inside a container for production.

    Args:
        entrypoint: Relative path to the Python entry point (e.g. 'src/main.py').
        args: Optional space-separated CLI arguments to pass to the program.
    """
    try:
        target = _safe_target(entrypoint)
    except ValueError as e:
        return f"Error: {e}"
    if not target.exists():
        return f"Error: {entrypoint} does not exist in output/."

    cmd = ["python3", str(target)]
    if args:
        cmd.extend(args.split())

    try:
        res = subprocess.run(
            cmd,
            cwd=str(OUTPUT_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (res.stdout + res.stderr)[:1200]
        if res.returncode == 0:
            return f"Program exited 0 (success).\nOutput:\n{output}"
        return f"Program exited {res.returncode}.\nOutput:\n{output}"
    except subprocess.TimeoutExpired:
        return "Error: program timed out after 30s (server/blocking I/O? Use a non-blocking entry point for smoke tests)."
    except Exception as e:
        return f"Error running program: {e}"


def run_project_tests(test_script: str = "tests") -> str:
    """Runs tests for the generated project using unittest.

    Args:
        test_script: Directory or module containing tests, default is 'tests'.
    """
    try:
        test_path = _safe_target(test_script)
    except ValueError as e:
        return f"Error: {e}"
    if not test_path.exists():
        return f"Error: Test folder '{test_script}' does not exist in output/. Can't run tests."
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", test_script],
            cwd=str(OUTPUT_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = f"Stdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        if res.returncode == 0:
            return f"Tests PASSED successfully.\n{output}"
        return f"Tests FAILED (Exit Code {res.returncode}).\n{output}"
    except Exception as e:
        return f"Execution error while running tests: {str(e)}"
