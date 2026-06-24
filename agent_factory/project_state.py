import json
from pathlib import Path
from typing import Dict, Any, List


class ProjectState:
    """Shared, evolving project state passed to every agent across iterations.
    Holds architect decisions, the file plan, per-agent contributions, the audit
    issue history, and a living summary. Persisted to project_state.json."""

    def __init__(self, output_dir: Path, prompt: str, requirements: str):
        self.path = Path(output_dir) / "project_state.json"
        self.data: Dict[str, Any] = {
            "prompt": prompt,
            "requirements": requirements,
            "architecture": "",          # architect's decisions (text)
            "file_plan": [],             # [{file, purpose}]
            "contributions": {},         # role -> short summary of what it did (latest)
            "audit_history": [],         # [{iteration, auditor, status, issues:[...]}]
            "iteration": 0,
        }
        self._save()

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def set_architecture(self, text: str, file_plan: List[dict]) -> None:
        self.data["architecture"] = text[:4000]
        self.data["file_plan"] = file_plan
        self._save()

    def record_contribution(self, role: str, summary: str) -> None:
        self.data["contributions"][role] = summary[:600]
        self._save()

    def record_audit(self, iteration: int, auditor: str, status: str, issues: List[dict]) -> None:
        self.data["audit_history"].append({
            "iteration": iteration,
            "auditor": auditor,
            "status": status,
            "issues": [
                {"severity": i.get("severity"), "where": i.get("file") or i.get("area"),
                 "problem": i.get("problem", "")[:200]}
                for i in issues
            ],
        })
        self._save()

    def set_iteration(self, n: int) -> None:
        self.data["iteration"] = n
        self._save()

    def as_briefing(self) -> str:
        """Compact, token-bounded snapshot injected into every agent prompt."""
        d = self.data
        plan = "\n".join(f"  - {m.get('file')}: {m.get('purpose','')}" for m in d["file_plan"]) or "  (not decided yet)"
        contribs = "\n".join(f"  - {r}: {s}" for r, s in d["contributions"].items()) or "  (none yet)"
        # only the issues from the most recent iteration, to bound size
        last_it = d["iteration"]
        recent = [a for a in d["audit_history"] if a["iteration"] == last_it - 1]
        issues_txt = ""
        for a in recent:
            for i in a["issues"]:
                issues_txt += f"  - [{i['severity']}] {i['where']}: {i['problem']}\n"
        issues_txt = issues_txt or "  (none)"
        return (
            "# SHARED PROJECT STATE (read this before doing your task — stay consistent with it)\n"
            f"## User request\n{d['prompt'][:800]}\n\n"
            f"## Architecture decisions\n{d['architecture'][:1500] or '(not decided yet)'}\n\n"
            f"## File plan\n{plan}\n\n"
            f"## What each agent has done\n{contribs}\n\n"
            f"## Open issues from the last audit\n{issues_txt}\n"
            "---\n"
        )
