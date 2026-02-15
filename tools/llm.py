import subprocess
from pathlib import Path


from typing import Optional

def run_llm(prompt: str, *, model: Optional[str] = None, prefer: str = "claude") -> str:
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
            return subprocess.check_output(cmd, input="\n", universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)
        except Exception:
            # fallback
            return subprocess.check_output(["gemini", "--output-format", "text", "-p", prompt], input="\n", universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)

    # prefer gemini
    cmd = ["gemini", "-p", prompt]
    if model:
        cmd += ["-m", model]
    try:
        return subprocess.check_output(cmd, input="\n", universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)
    except Exception:
        return subprocess.check_output(["claude", "-p", prompt], input="\n", universal_newlines=True, stderr=subprocess.STDOUT, timeout=900)
