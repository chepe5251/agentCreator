import unittest
import shutil
import tempfile
import os
from pathlib import Path
from agent_factory.orchestrator import parse_auditor_response
from agent_factory.memory import IterationMemory
from agent_factory.tools import write_project_file, read_project_file, check_python_syntax

class TestOrchestratorUtilities(unittest.TestCase):
    
    def test_parse_auditor_response_json(self):
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
        
    def test_parse_auditor_response_fallback_approved(self):
        text = "This project is APPROVED. Great work."
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "APPROVED")
        
    def test_parse_auditor_response_fallback_rejected(self):
        text = "There are bugs. REJECTED."
        res = parse_auditor_response(text)
        self.assertEqual(res["status"], "REJECTED")

class TestIterationMemory(unittest.TestCase):
    
    def setUp(self):
        self.run_id = "test_run_123"
        self.memory = IterationMemory(self.run_id)
        
    def tearDown(self):
        # Clean up test directories
        run_dir = Path("/home/chepe52/projectAgent/agentCreator/logs") / self.run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
            
    def test_log_and_load(self):
        deliverables = {"pm": "spec contents", "backend": "print('ok')"}
        reviews = {"qa": "all clear"}
        audits = {
            "technical_auditor": {"status": "REJECTED", "feedback": "Fix syntax"},
            "business_auditor": {"status": "APPROVED", "feedback": "Looks good"}
        }
        
        self.memory.log_iteration(1, deliverables, reviews, audits)
        history = self.memory.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["iteration"], 1)
        
        feedback = self.memory.get_accumulated_feedback()
        self.assertIn("Fix syntax", feedback)
        self.assertIn("Auditoría Técnica: REJECTED", feedback)

class TestTools(unittest.TestCase):
    
    def test_file_io(self):
        test_file = "test_io_temp.py"
        content = "print('hello io')"
        
        # Write
        res_write = write_project_file(test_file, content)
        self.assertIn("successfully written", res_write)
        
        # Read
        res_read = read_project_file(test_file)
        self.assertEqual(res_read, content)
        
        # Check syntax
        res_syntax = check_python_syntax(test_file)
        self.assertEqual(res_syntax, "Syntax OK for test_io_temp.py.")
        
        # Clean up
        out_path = Path("/home/chepe52/projectAgent/agentCreator/output") / test_file
        if out_path.exists():
            os.remove(out_path)

if __name__ == "__main__":
    unittest.main()
