from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def load_skill(name: str) -> str:
    """Returns the body of skills/<name>/SKILL.md, or '' if it doesn't exist."""
    path = SKILLS_DIR / name / "SKILL.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


# Which skills each role receives, injected into its system prompt.
# Auditors are intentionally excluded: they already carry the rubric in their prompt.
ROLE_SKILLS = {
    # architect intentionally excluded: it must decompose the USER's request,
    # not be primed to build a generic agent.
    "backend":   ["building-an-agent"],
    "prompt":    ["building-an-agent"],
    "rag":       ["building-an-agent"],
    "memory":    ["building-an-agent"],
}


def skills_for(role: str) -> str:
    """Concatenates the SKILL.md bodies mapped to a role. Missing skills are skipped."""
    blocks = []
    for name in ROLE_SKILLS.get(role, []):
        body = load_skill(name)
        if body:
            blocks.append(f"# SKILL: {name}\n{body}")
    return "\n\n---\n\n".join(blocks)
