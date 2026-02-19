"""Compatibility shim.

Historically, the ClawResearch pipeline entrypoint lived at repo root: `pipeline.py`.
It was moved to `tools/pipeline.py` during the 2026-02 relayout.

Some agents/tools may still try to read/import `VPS/repos/research/pipeline.py`.
Keep this thin wrapper to preserve backward compatibility.
"""

from tools.pipeline import *  # noqa: F401,F403
