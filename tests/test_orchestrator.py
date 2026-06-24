import unittest
import shutil
import os
from pathlib import Path
from agent_factory.orchestrator import parse_auditor_response
from agent_factory.memory import IterationMemory
from agent_factory.project_state import ProjectState
from agent_factory.tools import write_project_file, read_project_file, check_python_syntax
from agent_factory.config import OUTPUT_DIR, LOGS_DIR


class TestParseAuditorResponse(unittest.TestCase):

    def test_simple_json_fence(self):
        text = """Here is my review:
```json
{
  "status": "APPROVED",
  "feedback": "Code is solid."
}
```
Thank you."""
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "APPROVED")
        self.assertEqual(res["feedback"], "Code is solid.")

    def test_nested_json_with_issues(self):
        """Balanced-brace extractor must handle nested objects (issues array)."""
        text = """Analysis done.
```json
{
  "status": "REJECTED",
  "summary": "Two issues found.",
  "issues": [
    {
      "file": "src/main.py",
      "severity": "HIGH",
      "problem": "Missing auth.",
      "why": "Anyone can call the endpoint.",
      "fix": "Add JWT middleware.",
      "expected": "401 on unauthenticated requests."
    }
  ],
  "positive": ["Good structure"],
  "feedback": "Fix auth before approval."
}
```"""
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "REJECTED")
        self.assertEqual(len(res["issues"]), 1)
        self.assertEqual(res["issues"][0]["severity"], "HIGH")

    def test_fallback_approved(self):
        text = "This project is APPROVED. Great work."
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "APPROVED")

    def test_fallback_rejected(self):
        text = "There are bugs. REJECTED."
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "REJECTED")

    def test_json_without_fence(self):
        """Parser should find JSON even without ```json``` fence."""
        text = 'Some preamble. {"status": "APPROVED", "feedback": "All good."} trailing text'
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "APPROVED")


class TestIterationMemory(unittest.TestCase):

    def setUp(self):
        self.run_id = "test_run_123"
        self.memory = IterationMemory(self.run_id)

    def tearDown(self):
        run_dir = LOGS_DIR / self.run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

    def test_log_and_load(self):
        deliverables = {"pm": "spec contents", "backend": "print('ok')"}
        reviews = {"qa": "all clear"}
        audits = {
            "technical_auditor": {"status": "REJECTED", "feedback": "Fix syntax"},
            "business_auditor":  {"status": "APPROVED", "feedback": "Looks good"},
        }
        self.memory.log_iteration(1, deliverables, reviews, audits)
        history = self.memory.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["iteration"], 1)

    def test_accumulated_feedback(self):
        audits = {
            "technical_auditor": {"status": "REJECTED", "feedback": "Fix syntax"},
            "business_auditor":  {"status": "APPROVED", "feedback": "Looks good"},
        }
        self.memory.log_iteration(1, {}, {}, audits)
        feedback = self.memory.get_accumulated_feedback()
        self.assertIn("Fix syntax", feedback)
        self.assertIn("Technical Audit: REJECTED", feedback)  # English

    def test_atomic_write_survives_overwrite(self):
        """Writing the same iteration twice should not corrupt history."""
        audits = {"technical_auditor": {"status": "APPROVED", "feedback": "ok"},
                  "business_auditor":  {"status": "APPROVED", "feedback": "ok"}}
        self.memory.log_iteration(1, {}, {}, audits)
        self.memory.log_iteration(1, {"updated": True}, {}, audits)
        history = self.memory.load_history()
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["deliverables"].get("updated"))


class TestTools(unittest.TestCase):

    def test_file_io(self):
        test_file = "test_io_temp.py"
        content = "print('hello io')"

        res_write = write_project_file(test_file, content)
        self.assertIn("successfully written", res_write)

        res_read = read_project_file(test_file)
        self.assertEqual(res_read, content)

        res_syntax = check_python_syntax(test_file)
        self.assertEqual(res_syntax, f"Syntax OK for {test_file}.")

        out_path = OUTPUT_DIR / test_file
        if out_path.exists():
            os.remove(out_path)

    def test_path_traversal_blocked(self):
        """Absolute paths and ../ escapes must be rejected."""
        res_abs = write_project_file("/etc/passwd", "evil")
        self.assertIn("Error", res_abs)

        res_rel = write_project_file("../../etc/shadow", "evil")
        self.assertIn("Error", res_rel)

        res_read = read_project_file("../config.py")
        self.assertIn("Error", res_read)

    def test_syntax_error_detected(self):
        bad_file = "test_bad_syntax.py"
        write_project_file(bad_file, "def foo(:\n    pass")
        res = check_python_syntax(bad_file)
        self.assertIn("Syntax Error", res)
        out_path = OUTPUT_DIR / bad_file
        if out_path.exists():
            os.remove(out_path)

    def test_markdown_fence_stripped(self):
        """Local LLMs often wrap file content in ```python ... ``` — must be stripped."""
        fence_file = "test_fence.py"
        content_with_fence = "```python\nprint('hello')\n```"
        write_project_file(fence_file, content_with_fence)
        result = read_project_file(fence_file)
        self.assertNotIn("```", result)
        self.assertIn("print('hello')", result)
        # Must be valid Python after stripping
        self.assertEqual(check_python_syntax(fence_file), f"Syntax OK for {fence_file}.")
        out_path = OUTPUT_DIR / fence_file
        if out_path.exists():
            os.remove(out_path)


class TestProjectState(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.state = ProjectState(self.tmp, "build a calculator", "no extra requirements")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_initial_briefing_contains_prompt(self):
        briefing = self.state.as_briefing()
        self.assertIn("build a calculator", briefing)

    def test_set_architecture_reflected_in_briefing(self):
        self.state.set_architecture("Use clean architecture", [{"file": "src/main.py", "purpose": "entry point"}])
        briefing = self.state.as_briefing()
        self.assertIn("src/main.py", briefing)
        self.assertIn("Use clean architecture", briefing)

    def test_record_contribution_reflected_in_briefing(self):
        self.state.record_contribution("dev:src/main.py", "Implemented src/main.py: entry point")
        briefing = self.state.as_briefing()
        self.assertIn("dev:src/main.py", briefing)

    def test_record_audit_reflected_in_next_iteration_briefing(self):
        self.state.set_iteration(1)
        self.state.record_audit(1, "technical", "REJECTED", [
            {"severity": "HIGH", "file": "src/main.py", "problem": "Missing error handling"}
        ])
        self.state.set_iteration(2)
        briefing = self.state.as_briefing()
        self.assertIn("Missing error handling", briefing)


if __name__ == "__main__":
    unittest.main()
