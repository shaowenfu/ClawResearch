import subprocess
import re
from pathlib import Path


from typing import Optional

def _sanitize_llm_stdout(text: str) -> str:
    """Sanitize common CLI noise and formatting wrappers.

    Why: some CLIs (notably gemini) may emit credential / hook logs to STDOUT,
    which then pollute markdown and break downstream Notion rendering.

    We keep this conservative: only strip known boilerplate at the very top,
    and optionally unwrap a *single* outer fenced code block.
    """
    if not text:
        return text

    lines = text.splitlines()

    # 1) Strip known Gemini CLI boilerplate if it appears at the beginning.
    boilerplate = {
        "Loaded cached credentials.",
        "Hook registry initialized with 0 hook entries",
    }
    while lines and lines[0].strip() in boilerplate:
        lines.pop(0)

    # Also strip a single leading empty line after boilerplate.
    while lines and not lines[0].strip():
        lines.pop(0)

    cleaned = "\n".join(lines).strip("\n")

    # 2) Unwrap a single outer fenced code block (common when model wraps the whole answer).
    #    Example: ```chinese\n...content...\n```
    m = re.match(r"^```[^\n]*\n([\s\S]*?)\n```\s*$", cleaned)
    if m:
        cleaned = m.group(1).strip("\n")

    return cleaned + "\n"


def run_llm(prompt: str, *, model: Optional[str] = None, prefer: str = "gemini") -> str:
    """Run an LLM in headless mode and return text.

    IMPORTANT: prompts can be very large (hundreds of KB). Passing them as argv
    will hit OS ARG_MAX. Therefore we always send prompt via STDIN.

    prefer: 'gemini' or 'claude'
    """
    if prefer not in ("claude", "gemini"):
        prefer = "gemini"

    if prefer == "claude":
        # Claude CLI availability/auth may vary. Use stdin to avoid ARG_MAX.
        cmd = ["claude", "-p"]
        if model:
            cmd += ["--model", model]
        out = subprocess.check_output(cmd, input=prompt, universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)
        return _sanitize_llm_stdout(out)

    # prefer gemini (default)
    # Gemini CLI requires an argument after -p; stdin is appended to that prompt.
    cmd = ["gemini", "-p", ""]
    if model:
        cmd += ["-m", model]
    out = subprocess.check_output(cmd, input=prompt, universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)
    return _sanitize_llm_stdout(out)
