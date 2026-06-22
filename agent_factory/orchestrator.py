import json
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, Tuple
from agent_factory.config import MAX_AUDIT_ITERATIONS, WORKSPACE_DIR
from agent_factory.agents import get_agent
from agent_factory.memory import IterationMemory
from agent_factory.tools import list_project_files

def parse_auditor_response(text: str) -> Dict[str, Any]:
    """Extracts JSON block from the auditor response with regex fallbacks."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\{.*?\})", text, re.DOTALL)

    if match:
        try:
            data = json.loads(match.group(1))
            # Normalize: always keep a flat 'feedback' string even with rich format
            if "feedback" not in data:
                data["feedback"] = data.get("summary", text)
            return data
        except Exception:
            pass

    # Fallback to keyword matching
    status = "REJECTED"
    clean_text = text.upper()
    if "APPROVED" in clean_text and "REJECTED" not in clean_text:
        status = "APPROVED"
    elif '"STATUS": "APPROVED"' in clean_text or '"STATUS":"APPROVED"' in clean_text:
        status = "APPROVED"

    return {"status": status, "feedback": text, "issues": []}


def _format_audit_brief(audit: Dict[str, Any], auditor_name: str) -> str:
    """Formats a rich audit result into a clear, actionable developer brief."""
    lines = [f"### {auditor_name} — {audit.get('status', 'REJECTED')}"]
    summary = audit.get("summary") or audit.get("feedback", "")
    if summary:
        lines.append(f"**Verdict:** {summary}\n")

    issues = audit.get("issues", [])
    if issues:
        lines.append(f"**{len(issues)} issue(s) found:**\n")
        for i, issue in enumerate(issues, 1):
            sev = issue.get("severity", "?")
            # technical auditor uses 'file', business uses 'area'
            location = issue.get("file") or issue.get("area", "General")
            lines.append(f"#### Issue {i} [{sev}] — `{location}`")
            lines.append(f"**What is wrong:** {issue.get('problem', '')}")
            lines.append(f"**Why it matters:** {issue.get('why', '')}")
            lines.append(f"**How to fix it:** {issue.get('fix', '')}")
            lines.append(f"**Expected result:** {issue.get('expected', '')}\n")
    else:
        lines.append(audit.get("feedback", ""))

    positives = audit.get("positive", [])
    if positives:
        lines.append("**What was done well:**")
        for p in positives:
            lines.append(f"- {p}")

    return "\n".join(lines)

class EnterpriseOrchestrator:
    """Orchestrates the build-review-fix-audit loop for Agent Factory Enterprise."""
    
    def __init__(self, run_id: str, project_prompt: str):
        self.run_id = run_id
        self.project_prompt = project_prompt
        self.memory = IterationMemory(run_id)
        
    async def run(self) -> Tuple[bool, str]:
        """Runs the orchestrator loop. Returns (is_approved, summary_report)."""
        iteration = 1
        approved = False
        latest_feedback = ""
        
        print(f"[*] Starting Agent Factory Enterprise pipeline for Run: {self.run_id}")
        print(f"[*] Project Prompt: {self.project_prompt}")
        
        while not approved and iteration <= MAX_AUDIT_ITERATIONS:
            print(f"\n=================== ITERATION {iteration} ===================")
            
            # Step 1: Build Phase
            deliverables = await self._phase_build(iteration, latest_feedback)
            
            # Step 2: Review / Analyze Phase
            reviews = await self._phase_review(iteration, deliverables)
            
            # Step 3: Audit Phase
            tech_audit, bus_audit = await self._phase_audit(iteration)
            
            # Save results to memory
            self.memory.log_iteration(
                iteration=iteration,
                deliverables=deliverables,
                reviews=reviews,
                audits={
                    "technical_auditor": tech_audit,
                    "business_auditor": bus_audit
                }
            )
            
            # Check Approval
            tech_ok = tech_audit.get("status") == "APPROVED"
            bus_ok = bus_audit.get("status") == "APPROVED"
            
            tech_issues = tech_audit.get("issues", [])
            bus_issues = bus_audit.get("issues", [])
            print(f"[*] Iteration {iteration} Audit Results:")
            print(f"    - Technical Auditor: {tech_audit.get('status')} | {len(tech_issues)} issue(s) | {tech_audit.get('summary', tech_audit.get('feedback', ''))[:120]}")
            print(f"    - Business Auditor:  {bus_audit.get('status')} | {len(bus_issues)} issue(s) | {bus_audit.get('summary', bus_audit.get('feedback', ''))[:120]}")
            
            if tech_ok and bus_ok:
                approved = True
                print(f"[+] PROJECT APPROVED at iteration {iteration}!")
                break

            # Build a structured, developer-ready brief from the rich audit results
            latest_feedback = self._build_feedback_brief(iteration, tech_audit, bus_audit)
            
            iteration += 1
            
        summary = self._generate_final_summary(approved, iteration - 1)
        return approved, summary

    async def _phase_build(self, iteration: int, audit_feedback: str) -> Dict[str, str]:
        """Runs the build phase where PM, Researchers, Architects, and Developers write output."""
        deliverables = {}
        
        if iteration == 1:
            print("[*] Phase: Build (Initial Specification & Coding)")
            
            # CEO / PM initial spec
            async with get_agent("pm") as pm:
                response = await pm.chat(
                    f"The user wants to build the following project: '{self.project_prompt}'.\n"
                    "Analyze the requirements, define the scope, and create a specification in 'spec.md'."
                )
                deliverables["pm"] = await response.text()

            # Research
            async with get_agent("research") as research:
                response = await research.chat(
                    "Research the best technologies and libraries to fulfill 'spec.md'.\n"
                    "Write your conclusions in 'research.md'."
                )
                deliverables["research"] = await response.text()

            # Architect
            async with get_agent("architect") as arch:
                response = await arch.chat(
                    "Based on 'spec.md' and 'research.md', design the overall architecture and save it in 'architecture.md'."
                )
                deliverables["architect"] = await response.text()

            # Prompt Engineer
            async with get_agent("prompt") as pe:
                response = await pe.chat(
                    "Design the prompt strategy and system instructions required for the project and save them in 'prompts.md'."
                )
                deliverables["prompt"] = await response.text()

            # Developers: Backend, RAG, Memory
            print("[*] Phase: Coding (Backend, RAG, Memory)")
            async with get_agent("backend") as backend:
                response = await backend.chat(
                    "Create the runnable backend code (e.g. 'src/main.py', 'requirements.txt') based on the architecture."
                )
                deliverables["backend"] = await response.text()

            async with get_agent("rag") as rag:
                response = await rag.chat(
                    "If the project requires document search or retrieval, write the RAG module (e.g. 'src/rag.py')."
                )
                deliverables["rag"] = await response.text()

            async with get_agent("memory") as memory:
                response = await memory.chat(
                    "If the project requires state persistence or memory, write the memory module (e.g. 'src/memory.py')."
                )
                deliverables["memory"] = await response.text()
                
        else:
            # Fix phase
            print(f"[*] Phase: Fix & Correct (Iteration {iteration})")

            # PM reviews the full audit brief and creates a correction plan
            async with get_agent("pm") as pm:
                response = await pm.chat(
                    f"The auditors rejected the deliverable at iteration {iteration - 1}.\n\n"
                    f"{audit_feedback}\n\n"
                    "Your tasks:\n"
                    "1. Read the current project files using read_project_file and list_project_files.\n"
                    "2. Update 'spec.md' with a correction plan that assigns each issue to the responsible specialist.\n"
                    "3. At the end of your response, write a '## TASKS PER SPECIALIST' section with concrete, "
                    "specific instructions for: Backend Engineer, RAG Specialist, and Memory Engineer. "
                    "Include the exact files to modify and the changes required based on the auditor feedback."
                )
                deliverables["pm"] = await response.text()
                pm_instructions = deliverables["pm"]

            # Specialists correct code using both PM instructions AND the full audit brief
            async with get_agent("backend") as backend:
                response = await backend.chat(
                    f"## PM Instructions\n{pm_instructions}\n\n"
                    f"## Full Audit Report\n{audit_feedback}\n\n"
                    "Fix ONLY the issues that belong to the backend. "
                    "Read the current files before modifying them. "
                    "Implement ALL corrections listed for backend files, including "
                    "the exact code suggested by the auditors. Do not leave any TODOs unimplemented."
                )
                deliverables["backend"] = await response.text()

            async with get_agent("rag") as rag:
                response = await rag.chat(
                    f"## PM Instructions\n{pm_instructions}\n\n"
                    f"## Full Audit Report\n{audit_feedback}\n\n"
                    "Fix ONLY the issues that belong to the RAG module. "
                    "Read the current files before modifying them. "
                    "Implement ALL corrections listed for RAG files. Do not leave any TODOs unimplemented."
                )
                deliverables["rag"] = await response.text()

            async with get_agent("memory") as memory:
                response = await memory.chat(
                    f"## PM Instructions\n{pm_instructions}\n\n"
                    f"## Full Audit Report\n{audit_feedback}\n\n"
                    "Fix ONLY the issues that belong to the memory module. "
                    "Read the current files before modifying them. "
                    "Implement ALL corrections listed for memory files. Do not leave any TODOs unimplemented."
                )
                deliverables["memory"] = await response.text()
                
        return deliverables

    async def _phase_review(self, iteration: int, deliverables: Dict[str, str]) -> Dict[str, str]:
        """Runs the analyst review phase (QA, Security, DevOps, Cost)."""
        print("[*] Phase: Review & Analysis")
        reviews = {}
        
        # QA creates test suite
        async with get_agent("qa") as qa:
            response = await qa.chat(
                "Write and update automated tests (e.g. in 'tests/test_app.py') "
                "to cover backend, RAG, and memory functionality. Run the run_project_tests tool."
            )
            reviews["qa"] = await response.text()

        # Security review
        async with get_agent("security") as sec:
            response = await sec.chat(
                "Perform a security review of the current code and write 'security_review.md'. "
                "Look for credential leaks, command injection vulnerabilities, and insecure dependencies."
            )
            reviews["security"] = await response.text()

        # DevOps deployment setup
        async with get_agent("devops") as devops:
            response = await devops.chat(
                "Create and update infrastructure and deployment files (e.g. 'Dockerfile', "
                "'docker-compose.yml') to package the project."
            )
            reviews["devops"] = await response.text()

        # Cost Optimization analysis
        async with get_agent("cost") as cost:
            response = await cost.chat(
                "Analyze the estimated cost of running this agent system and save it in 'cost_analysis.md'."
            )
            reviews["cost"] = await response.text()
            
        return reviews

    async def _phase_audit(self, iteration: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Runs the dual auditors to approve or reject the deliverables."""
        print("[*] Phase: Audit & Compliance")
        files = list_project_files()
        files_str = "\n".join(f"  - {f}" for f in files)

        # Technical Auditor
        async with get_agent("technical_auditor") as ta:
            response = await ta.chat(
                f"## Original user requirement\n{self.project_prompt}\n\n"
                f"## Files generated in this iteration ({iteration})\n{files_str}\n\n"
                "## Instructions\n"
                "1. Call read_project_file on EVERY file listed — do not skip any.\n"
                "2. Call check_python_syntax on every .py file.\n"
                "3. Call run_project_tests and analyze the full output.\n"
                "4. For each issue found, document: exact file, what is wrong, "
                "why it matters, and how to fix it with concrete code.\n"
                "5. Output your verdict using the required structured JSON (status, summary, issues[], positive[], feedback)."
            )
            ta_text = await response.text()
            ta_audit = parse_auditor_response(ta_text)

        # Business Auditor
        async with get_agent("business_auditor") as ba:
            response = await ba.chat(
                f"## Original user requirement\n{self.project_prompt}\n\n"
                f"## Files generated in this iteration ({iteration})\n{files_str}\n\n"
                "## Instructions\n"
                "1. Call read_project_file on spec.md, architecture.md, prompts.md, and all source files.\n"
                "2. Compare EACH implemented feature against the original user requirement.\n"
                "3. Identify: missing requirements, unnecessary complexity, misaligned agent behavior.\n"
                "4. For each issue, specify: affected area, what is missing or wrong, "
                "why it matters to the user, and exactly how to fix it.\n"
                "5. Output your verdict using the required structured JSON (status, summary, issues[], positive[], feedback)."
            )
            ba_text = await response.text()
            ba_audit = parse_auditor_response(ba_text)

        return ta_audit, ba_audit

    def _build_feedback_brief(
        self, iteration: int, tech_audit: Dict[str, Any], bus_audit: Dict[str, Any]
    ) -> str:
        """Builds a structured, developer-ready brief from the rich audit results."""
        tech_brief = _format_audit_brief(tech_audit, "Technical Auditor")
        bus_brief = _format_audit_brief(bus_audit, "Business Auditor")

        all_issues = tech_audit.get("issues", []) + bus_audit.get("issues", [])
        critical = [i for i in all_issues if i.get("severity") == "CRITICAL"]
        high = [i for i in all_issues if i.get("severity") == "HIGH"]

        header = (
            f"# AUDIT REJECTED — Iteration {iteration}\n\n"
            f"**Executive summary:** {len(all_issues)} total issue(s) — "
            f"{len(critical)} CRITICAL, {len(high)} HIGH.\n"
            "All issues must be resolved before the next iteration.\n"
            "Each issue includes: what is wrong, why it matters, and exactly how to fix it.\n\n"
            "---\n"
        )

        return header + "\n\n" + tech_brief + "\n\n---\n\n" + bus_brief

    def _generate_final_summary(self, approved: bool, total_iterations: int) -> str:
        """Generates a summary markdown report of the pipeline run."""
        status_str = "APPROVED" if approved else "REJECTED"
        history = self.memory.load_history()
        
        report_lines = [
            f"# Agent Factory Enterprise Pipeline Summary",
            f"**Run ID:** {self.run_id}",
            f"**Project Prompt:** {self.project_prompt}",
            f"**Final Verdict:** {status_str}",
            f"**Total Iterations executed:** {total_iterations}",
            "",
            "## Iteration History",
        ]
        
        for record in history:
            it = record.get("iteration")
            audits = record.get("audits", {})
            ta = audits.get("technical_auditor", {})
            ba = audits.get("business_auditor", {})
            
            report_lines.append(f"### Iteration {it}")
            report_lines.append(f"- **Technical Auditor:** {ta.get('status')}")
            report_lines.append(f"- **Business Auditor:** {ba.get('status')}")
            report_lines.append("")
            
        # Write report to log folder
        report = "\n".join(report_lines)
        report_path = self.memory.run_dir / "summary_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
            
        # Also copy it to the project output root as 'enterprise_summary.md'
        try:
            summary_out = WORKSPACE_DIR / "output" / "enterprise_summary.md"
            summary_out.parent.mkdir(exist_ok=True, parents=True)
            with open(summary_out, "w", encoding="utf-8") as f:
                f.write(report)
        except Exception:
            pass
            
        return report
