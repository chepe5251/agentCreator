import json
from pathlib import Path
from typing import Dict, Any, List
from agent_factory.config import LOGS_DIR

class IterationMemory:
    """Manages the history of project iterations, code updates, and auditor reviews."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_dir = LOGS_DIR / run_id
        self.run_dir.mkdir(exist_ok=True, parents=True)
        self.history_file = self.run_dir / "history.json"
        self._init_history()

    def _init_history(self):
        if not self.history_file.exists():
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def load_history(self) -> List[Dict[str, Any]]:
        """Loads the full iteration history."""
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_iteration_data(self, iteration: int) -> Dict[str, Any]:
        """Gets data for a specific iteration."""
        history = self.load_history()
        for record in history:
            if record.get("iteration") == iteration:
                return record
        return {}

    def get_latest_iteration(self) -> Dict[str, Any]:
        """Gets the most recent iteration data."""
        history = self.load_history()
        if history:
            return history[-1]
        return {}

    def log_iteration(self, iteration: int, deliverables: Dict[str, Any], reviews: Dict[str, Any], audits: Dict[str, Any]):
        """Logs a complete iteration cycle."""
        history = self.load_history()
        # Remove if iteration already exists (overwrite)
        history = [h for h in history if h.get("iteration") != iteration]
        
        record = {
            "iteration": iteration,
            "deliverables": deliverables,
            "reviews": reviews,
            "audits": audits
        }
        history.append(record)
        
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def get_accumulated_feedback(self) -> str:
        """Accumulates all feedback and audit findings for prompt injection to agents during fixes."""
        history = self.load_history()
        if not history:
            return "No previous history."
        
        summary_lines = []
        for h in history:
            it = h.get("iteration")
            summary_lines.append(f"--- Iteration {it} ---")

            audits = h.get("audits", {})
            tech_audit = audits.get("technical_auditor", {})
            bus_audit = audits.get("business_auditor", {})

            summary_lines.append(f"Technical Audit: {tech_audit.get('status', 'PENDING')}")
            summary_lines.append(f"Technical Feedback:\n{tech_audit.get('feedback', 'None')}")

            summary_lines.append(f"Business Audit: {bus_audit.get('status', 'PENDING')}")
            summary_lines.append(f"Business Feedback:\n{bus_audit.get('feedback', 'None')}")

        return "\n".join(summary_lines)
