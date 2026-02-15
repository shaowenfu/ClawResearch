import json
import os
import time
from pathlib import Path

from utils import load_state, save_state, log
from llm import run_llm


def read_all_texts(dir_path: Path, max_chars: int = 200_000) -> str:
    parts = []
    total = 0
    for p in sorted(dir_path.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        parts.append(f"\n\n# FILE: {p.name}\n" + t)
        total += len(t)
        if total >= max_chars:
            break
    return "".join(parts)


def heartbeat(step: str, *, status: str = "running"):
    save_state({"status": status, "step": step})


def build_outline(topic: str, topic_dir: Path) -> str:
    heartbeat("outline")
    raw = read_all_texts(topic_dir / "01_RawMaterials", max_chars=120_000)
    prompt = (
        f"You are writing a deep research report in Chinese about: {topic}.\n"
        f"Given the raw materials below, produce a detailed outline with 6-10 sections.\n"
        f"For each section, include: key questions to answer + evidence needed.\n\n"
        f"RAW MATERIALS:\n{raw}"
    )
    out = run_llm(prompt, prefer="gemini")
    (topic_dir / "03_Synthesis" / "outline.md").write_text(out, encoding="utf-8")
    return out


def write_section(topic: str, topic_dir: Path, section_title: str, outline: str) -> str:
    # One section per call => more detail
    heartbeat(f"section:{section_title}")
    raw = read_all_texts(topic_dir / "01_RawMaterials", max_chars=160_000)
    prompt = (
        f"Write ONLY the section '{section_title}' in Chinese for a deep research report about {topic}.\n"
        f"Requirements: detailed, concrete, include mechanisms, numbers when available, and cite which raw file each claim comes from (by FILE name).\n"
        f"Target length: >= 1200 Chinese characters.\n\n"
        f"OUTLINE:\n{outline}\n\nRAW MATERIALS:\n{raw}"
    )
    out = run_llm(prompt, prefer="gemini")
    fn = section_title.strip().replace(" ", "_")
    (topic_dir / "02_Distilled" / f"section_{fn}.md").write_text(out, encoding="utf-8")
    return out


def assemble_report(topic: str, topic_dir: Path):
    heartbeat("assemble")
    outline = (topic_dir / "03_Synthesis" / "outline.md").read_text(encoding="utf-8")
    sections = read_all_texts(topic_dir / "02_Distilled", max_chars=400_000)
    prompt = (
        f"Assemble a final Chinese report about {topic} with the following structure:\n"
        f"- Title\n- Executive Summary\n- Main body (integrate sections, remove repetition)\n- Risks & Open Questions\n- Actionable next steps\n\n"
        f"Use the outline and section drafts below. Ensure the final report is >= 3500 Chinese characters.\n\n"
        f"OUTLINE:\n{outline}\n\nSECTION DRAFTS:\n{sections}"
    )
    out = run_llm(prompt, prefer="gemini")
    (topic_dir / "report.md").write_text(out, encoding="utf-8")
    return out
