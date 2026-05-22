from pathlib import Path
import re

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def load_prompt(name: str) -> str:
    if not isinstance(name, str) or not PROMPT_NAME_PATTERN.match(name):
        raise ValueError("prompt name must contain only letters, numbers, underscores, and hyphens")

    path = (PROMPT_DIR / f"{name}.md").resolve()
    if path.parent != PROMPT_DIR:
        raise ValueError("prompt path must stay inside the prompts directory")
    return path.read_text(encoding="utf-8")
