import subprocess
from pathlib import Path


def run_llm(prompt: str, *, model: str | None = None, prefer: str = "claude") -> str:
    """Run an LLM in headless mode and return text.

    prefer: 'claude' or 'gemini'
    """
    if prefer not in ("claude", "gemini"):
        prefer = "claude"

    if prefer == "claude":
        # Claude CLI supports -p/--print for non-interactive output
        cmd = ["claude", "-p", prompt]
        if model:
            cmd += ["--model", model]
        try:
            return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        except Exception:
            # fallback
            return subprocess.check_output(["gemini", "-p", prompt], text=True, stderr=subprocess.STDOUT)

    # prefer gemini
    cmd = ["gemini", "-p", prompt]
    if model:
        cmd += ["-m", model]
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except Exception:
        return subprocess.check_output(["claude", "-p", prompt], text=True, stderr=subprocess.STDOUT)
