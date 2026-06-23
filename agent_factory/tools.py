import os
import sys
import subprocess
import py_compile
from pathlib import Path
from typing import List

from agent_factory.config import OUTPUT_DIR as _OUTPUT_ROOT

_ACTIVE_OUTPUT = _OUTPUT_ROOT  # replaced by the orchestrator per run

_VENV_EXCLUDE = {"venv", ".venv", "__pycache__", ".git"}


def set_active_output(path) -> None:
    """Points ALL file tools to the current run's output directory."""
    global _ACTIVE_OUTPUT
    _ACTIVE_OUTPUT = Path(path).resolve()
    _ACTIVE_OUTPUT.mkdir(parents=True, exist_ok=True)


def get_active_output() -> Path:
    return _ACTIVE_OUTPUT


def _safe_target(filepath: str) -> Path:
    """Resolves filepath inside _ACTIVE_OUTPUT and raises if it escapes the sandbox."""
    base = _ACTIVE_OUTPUT.resolve()
    target = (base / filepath).resolve()
    if target == base or base not in target.parents:
        raise ValueError(f"Path outside output/: {filepath!r}")
    return target


def _venv_python() -> str:
    """Returns the Python executable inside the output/.venv, creating it on first call."""
    venv_dir = _ACTIVE_OUTPUT / ".venv"
    py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        _ACTIVE_OUTPUT.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], timeout=60, check=True)
    return str(py)


_CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".yaml", ".yml", ".toml", ".json"}


def _strip_markdown_fences(content: str, filepath: str) -> str:
    """Strips ```lang ... ``` fences that local LLMs sometimes write into source files."""
    ext = Path(filepath).suffix.lower()
    if ext not in _CODE_EXTENSIONS:
        return content
    stripped = content.strip()
    first_newline = stripped.find("\n")
    if stripped.startswith("```") and first_newline != -1:
        first_line = stripped[:first_newline].strip()
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
    if not _ACTIVE_OUTPUT.exists():
        return files
    for root, dirs, filenames in os.walk(_ACTIVE_OUTPUT):
        dirs[:] = [d for d in dirs if d not in _VENV_EXCLUDE]
        for name in filenames:
            path = Path(root) / name
            rel = path.relative_to(_ACTIVE_OUTPUT)
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
    """Installs Python packages into the isolated output/.venv (never the host env).

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
        py = _venv_python()
        res = subprocess.run(
            [py, "-m", "pip", "install", "-r", str(target), "--quiet", "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if res.returncode == 0:
            return f"Dependencies installed into output/.venv from {requirements_file}."
        return f"Dependency installation failed:\n{res.stderr[:600]}"
    except subprocess.TimeoutExpired:
        return "Error: dependency installation timed out after 180s."
    except Exception as e:
        return f"Error installing dependencies: {e}"


def lint_code(filepath: str = ".") -> str:
    """Runs ruff (fallback: flake8) checking only real errors (F-rules: undefined names, broken imports).

    Args:
        filepath: Relative path to lint, or '.' to lint the entire output/ directory.
    """
    if filepath == ".":
        target = _ACTIVE_OUTPUT
    else:
        try:
            target = _safe_target(filepath)
        except ValueError as e:
            return f"Error: {e}"
    if not target.exists():
        return f"Error: {filepath} does not exist in output/."

    for linter_cmd in [
        ["ruff", "check", "--select", "F", str(target)],
        ["flake8", "--select=F", str(target)],
    ]:
        try:
            res = subprocess.run(linter_cmd, capture_output=True, text=True, timeout=30)
            tool = linter_cmd[0]
            if res.returncode == 0:
                return f"{tool}: No errors found in {filepath}."
            return f"{tool} errors in {filepath}:\n{(res.stdout + res.stderr)[:1000]}"
        except FileNotFoundError:
            continue
        except Exception as e:
            return f"Linter error: {e}"
    return "Error: neither ruff nor flake8 is installed."


def run_program(entrypoint: str = "src/main.py", args: str = "") -> str:
    """Runs the generated entry point inside the isolated output/.venv (5s timeout).

    A TimeoutExpired after 5s means the program started and kept running — this counts
    as SUCCESS for long-running services (bots, servers). An immediate non-zero exit
    or crash is a real failure.

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

    cmd = [_venv_python(), str(target)]
    if args:
        cmd.extend(args.split())

    try:
        res = subprocess.run(
            cmd,
            cwd=str(_ACTIVE_OUTPUT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (res.stdout + res.stderr)[:1200]
        if res.returncode == 0:
            return f"Program exited 0 (success).\nOutput:\n{output}"
        return f"Program exited {res.returncode} (error).\nOutput:\n{output}"
    except subprocess.TimeoutExpired:
        return "Program started successfully and kept running (long-running service — expected for bots/servers)."
    except Exception as e:
        return f"Error running program: {e}"


def run_project_tests(test_script: str = "tests") -> str:
    """Runs the project's unittest suite inside the isolated output/.venv.

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
            [_venv_python(), "-m", "unittest", "discover", "-s", test_script],
            cwd=str(_ACTIVE_OUTPUT),
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
