import subprocess
from pathlib import Path


from typing import Optional

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
        return subprocess.check_output(cmd, input=prompt, universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)

    # prefer gemini (default)
    # Gemini CLI requires an argument after -p; stdin is appended to that prompt.
    cmd = ["gemini", "-p", ""]
    if model:
        cmd += ["-m", model]
    return subprocess.check_output(cmd, input=prompt, universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)
