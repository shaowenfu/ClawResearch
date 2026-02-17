import json
import os
import time
from pathlib import Path

from utils import load_state, save_state, log
from llm import run_llm


def read_all_texts(dir_path: Path, max_chars: int = 200_000) -> str:
    """Read multiple .md files with a hard cap (best-effort).

    Note: This is only used for already-distilled directories (small-ish).
    RawMaterials should go through spill+distill to avoid huge prompts.
    """
    parts = []
    total = 0
    for p in sorted(dir_path.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        parts.append(f"\n\n# FILE: {p.name}\n" + t)
        total += len(t)
        if total >= max_chars:
            break
    return "".join(parts)


def _ensure_dirs(topic_dir: Path):
    (topic_dir / "00_Brief" / "_spill").mkdir(parents=True, exist_ok=True)
    (topic_dir / "00_Brief" / "_prompts").mkdir(parents=True, exist_ok=True)
    (topic_dir / "02_Distilled" / "_raw_chunk_summaries").mkdir(parents=True, exist_ok=True)


def spill_rawmaterials(topic_dir: Path, *, chunk_chars: int = 22_000) -> list[Path]:
    """Spill 01_RawMaterials into chunk files on disk.

    Goal: never build a single massive in-memory prompt with hundreds of KB.
    """
    _ensure_dirs(topic_dir)
    raw_dir = topic_dir / "01_RawMaterials"
    spill_dir = topic_dir / "00_Brief" / "_spill"

    buf = []
    size = 0
    out_paths: list[Path] = []

    def flush(idx: int):
        nonlocal buf, size
        if not buf:
            return
        p = spill_dir / f"raw_chunk_{idx:03d}.md"
        p.write_text("".join(buf), encoding="utf-8")
        out_paths.append(p)
        buf = []
        size = 0

    idx = 1
    for p in sorted(raw_dir.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        piece = f"\n\n# FILE: {p.name}\n" + t
        if size + len(piece) > chunk_chars and buf:
            flush(idx)
            idx += 1
        buf.append(piece)
        size += len(piece)

    flush(idx)
    log(f"spill_rawmaterials: chunks={len(out_paths)} dir={spill_dir}")
    return out_paths


def distill_raw_chunks(topic: str, topic_dir: Path, chunk_paths: list[Path]) -> list[Path]:
    """Summarize each raw chunk into a compact evidence note (on disk)."""
    _ensure_dirs(topic_dir)
    out_dir = topic_dir / "02_Distilled" / "_raw_chunk_summaries"
    prompt_dir = topic_dir / "00_Brief" / "_prompts"

    out_paths: list[Path] = []
    for chunk in chunk_paths:
        heartbeat(f"distill:{chunk.name}")
        raw = chunk.read_text(encoding="utf-8", errors="ignore")
        prompt = (
            f"You are assisting a deep research report in Chinese about: {topic}.\n"
            f"Given the raw materials chunk below, produce a compact evidence memo in Chinese.\n"
            f"Rules:\n"
            f"- Focus on concrete facts, mechanisms, numbers, and claims.\n"
            f"- Keep it structured with bullet points and short paragraphs.\n"
            f"- Preserve traceability: when you mention a claim, include the source as (FILE: <name>).\n"
            f"- Target length: 800-1500 Chinese characters.\n\n"
            f"RAW CHUNK:\n{raw}"
        )

        prompt_path = prompt_dir / f"prompt_{chunk.stem}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")

        out = run_llm(prompt, prefer="gemini")
        out_path = out_dir / f"summary_{chunk.stem}.md"
        out_path.write_text(out, encoding="utf-8")
        out_paths.append(out_path)

    log(f"distill_raw_chunks: summaries={len(out_paths)} dir={out_dir}")
    return out_paths


def load_distilled_evidence(topic_dir: Path, *, max_chars: int = 80_000) -> str:
    """Load distilled evidence memos with a cap."""
    d = topic_dir / "02_Distilled" / "_raw_chunk_summaries"
    if not d.exists():
        return ""
    return read_all_texts(d, max_chars=max_chars)


def heartbeat(step: str, *, status: str = "running"):
    save_state({"status": status, "step": step})


def build_outline(topic: str, topic_dir: Path) -> str:
    heartbeat("outline")

    # Spill + distill raw sources first, so outline is based on compact evidence memos.
    chunks = spill_rawmaterials(topic_dir, chunk_chars=22_000)
    distill_raw_chunks(topic, topic_dir, chunks)
    evidence = load_distilled_evidence(topic_dir, max_chars=80_000)

    prompt = (
        f"You are writing a deep research report in Chinese about: {topic}.\n"
        f"Given the EVIDENCE MEMOS below (distilled from raw sources), produce a detailed outline with 6-10 sections.\n"
        f"For each section, include: key questions to answer + evidence needed.\n\n"
        f"EVIDENCE MEMOS:\n{evidence}"
    )
    (topic_dir / "00_Brief" / "_prompts" / "prompt_outline.txt").write_text(prompt, encoding="utf-8")

    out = run_llm(prompt, prefer="gemini")
    (topic_dir / "03_Synthesis" / "outline.md").write_text(out, encoding="utf-8")
    return out


def write_section(topic: str, topic_dir: Path, section_title: str, outline: str) -> str:
    # One section per call => more detail
    heartbeat(f"section:{section_title}")

    # Use distilled evidence memos; avoid raw material mega-prompts.
    evidence = load_distilled_evidence(topic_dir, max_chars=90_000)
    prompt = (
        f"Write ONLY the section '{section_title}' in Chinese for a deep research report about {topic}.\n"
        f"Requirements: detailed, concrete, include mechanisms, numbers when available, and cite which raw file each claim comes from (by FILE name).\n"
        f"Target length: >= 1200 Chinese characters.\n\n"
        f"OUTLINE:\n{outline}\n\nEVIDENCE MEMOS (distilled from raw sources):\n{evidence}"
    )

    safe_name = section_title.strip().replace("/", "-").replace(" ", "_")
    (topic_dir / "00_Brief" / "_prompts" / f"prompt_section_{safe_name}.txt").write_text(prompt, encoding="utf-8")

    out = run_llm(prompt, prefer="gemini")
    (topic_dir / "02_Distilled" / f"section_{safe_name}.md").write_text(out, encoding="utf-8")
    return out


def assemble_report(topic: str, topic_dir: Path):
    heartbeat("assemble")
    outline = (topic_dir / "03_Synthesis" / "outline.md").read_text(encoding="utf-8")

    # Exclude internal evidence memos directory from assembly input.
    section_dir = topic_dir / "02_Distilled"
    sections = []
    total = 0
    for p in sorted(section_dir.glob("section_*.md")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        sections.append(f"\n\n# DRAFT: {p.name}\n" + t)
        total += len(t)
        if total >= 220_000:
            break
    sections_txt = "".join(sections)

    prompt = (
        f"Assemble a final Chinese report about {topic} with the following structure:\n"
        f"- Title\n- Executive Summary\n- Main body (integrate sections, remove repetition)\n- Risks & Open Questions\n- Actionable next steps\n\n"
        f"Use the outline and section drafts below. Ensure the final report is >= 3500 Chinese characters.\n\n"
        f"OUTLINE:\n{outline}\n\nSECTION DRAFTS:\n{sections_txt}"
    )

    (topic_dir / "00_Brief" / "_prompts" / "prompt_assemble.txt").write_text(prompt, encoding="utf-8")

    out = run_llm(prompt, prefer="gemini")
    (topic_dir / "report.md").write_text(out, encoding="utf-8")
    return out
