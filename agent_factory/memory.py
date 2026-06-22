import json
import os
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

    def _atomic_write(self, data: list) -> None:
        """Writes data to history_file atomically via a temp file + os.replace."""
        tmp = self.history_file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.history_file)

    def _init_history(self) -> None:
        if not self.history_file.exists():
            self._atomic_write([])

    def load_history(self) -> List[Dict[str, Any]]:
        """Loads the full iteration history."""
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def log_iteration(
        self,
        iteration: int,
        deliverables: Dict[str, Any],
        reviews: Dict[str, Any],
        audits: Dict[str, Any],
    ) -> None:
        """Logs a complete iteration cycle (overwrites same iteration if retried)."""
        history = self.load_history()
        history = [h for h in history if h.get("iteration") != iteration]
        history.append({
            "iteration": iteration,
            "deliverables": deliverables,
            "reviews": reviews,
            "audits": audits,
        })
        self._atomic_write(history)

    def get_accumulated_feedback(self) -> str:
        """Returns all audit feedback concatenated — useful for cross-iteration context."""
        history = self.load_history()
        if not history:
            return "No previous history."

        lines = []
        for h in history:
            it = h.get("iteration")
            lines.append(f"--- Iteration {it} ---")
            audits = h.get("audits", {})
            tech = audits.get("technical_auditor", {})
            bus  = audits.get("business_auditor", {})
            lines.append(f"Technical Audit: {tech.get('status', 'PENDING')}")
            lines.append(f"Technical Feedback:\n{tech.get('feedback', 'None')}")
            lines.append(f"Business Audit: {bus.get('status', 'PENDING')}")
            lines.append(f"Business Feedback:\n{bus.get('feedback', 'None')}")
        return "\n".join(lines)
