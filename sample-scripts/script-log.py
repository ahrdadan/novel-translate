"""Execution Logger Script — Runs Novel Translation directly using Python services (no FastAPI HTTP server required)
and records full execution details, prompts, context, LLM responses, and DB states into Markdown log files.

Usage:
  python sample-scripts/script-log.py sample-scripts/series_new_platform.json
  python sample-scripts/script-log.py sample-scripts/series_new_platform_single.json
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure root workspace is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.database import init_db
from src.html_parser import convert_html_to_md
from src.repositories import (
    chapter_repo,
    character_repo,
    glossary_repo,
    platform_repo,
    series_repo,
)
from src.services import (
    model_resolver,
    single_pass,
    summarizer,
    translator,
)


async def run_and_log(config_path: str):
    """Execute translation directly via Python services and write full Markdown log."""
    print(f"📖 Reading config: {config_path}")
    if not os.path.exists(config_path):
        print(f"❌ Error: Config file not found at {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:  # noqa: ASYNC230
        config = json.load(f)

    strategy = config.get("strategy", "pipeline")
    output_md_filename = "execution_log_pipeline.md" if strategy == "pipeline" else "execution_log_single_pass.md"
    output_md_path = os.path.join(Path(__file__).resolve().parent, output_md_filename)

    # Initialize SQLite Database
    await init_db()

    # 1. Resolve Series
    series_data = config.get("series", {})
    series_name = series_data.get("name", f"Log Demo Series {int(time.time())}")
    series = await series_repo.get_series_by_name(series_name)
    if not series:
        series = await series_repo.create_series({
            "name": series_name,
            "original_title": series_data.get("originalTitle"),
            "author": series_data.get("author"),
            "description": series_data.get("description"),
            "status": "ongoing",
            "summary": "",
        })

    series_id = series["id"]

    # 2. Resolve Translation Model
    trans_model_ref = config.get("translationModel")
    resolved_model = await model_resolver.resolve_or_create_model(trans_model_ref)
    resolved_platform = await platform_repo.get_platform_by_id(resolved_model["platform_id"])

    # Prepare Markdown Log Buffer
    log_lines = []
    log_lines.append(f"# Novel Translation Execution Log — Strategy: `{strategy.upper()}`")
    log_lines.append(f"**Execution Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"**Config File**: `{os.path.basename(config_path)}`")
    log_lines.append(f"**Series**: `{series['name']}` (ID: `{series_id}`)")
    log_lines.append(f"**Model**: `{resolved_model['name']}` | **Platform**: `{resolved_platform['name']}`")
    log_lines.append(f"**Strategy**: `{strategy}`\n")
    log_lines.append("---\n")

    # 3. Locate Chapters
    chapters_folder = os.path.join(ROOT_DIR, "sample-scripts", config.get("chaptersFolder", "novel-html"))
    toc_file = os.path.join(chapters_folder, "toc.json")
    chapters_to_process = []

    if os.path.exists(toc_file):
        with open(toc_file, "r", encoding="utf-8") as f:  # noqa: ASYNC230
            toc = json.load(f)
            for item in toc:
                file_path = os.path.join(chapters_folder, item.get("file", ""))
                if os.path.exists(file_path):
                    chapters_to_process.append({
                        "chapter_number": item.get("chapterNumber", 1),
                        "title": item.get("title", f"Chapter {item.get('chapterNumber', 1)}"),
                        "file_path": file_path,
                    })

    if not chapters_to_process and os.path.exists(chapters_folder):
        for fname in sorted(os.listdir(chapters_folder)):
            if fname.endswith((".html", ".txt")):
                chapters_to_process.append({
                    "chapter_number": translator.extract_chapter_number(fname) if hasattr(translator, 'extract_chapter_number') else 1,
                    "title": fname,
                    "file_path": os.path.join(chapters_folder, fname),
                })

    log_lines.append(f"## 📚 Chapters Found ({len(chapters_to_process)} Total)\n")

    try:
        # Process Each Chapter
        for chap in chapters_to_process:
            c_num = chap["chapter_number"]
            c_title = chap["title"]
            f_path = chap["file_path"]

            with open(f_path, "r", encoding="utf-8") as f:  # noqa: ASYNC230
                raw_content = f.read()

            source_text = convert_html_to_md(raw_content)

            log_lines.append(f"### 📜 Chapter #{c_num}: {c_title}")
            log_lines.append(f"- **Source File**: `{os.path.basename(f_path)}` ({len(raw_content)} bytes raw, {len(source_text)} chars cleaned Markdown)")

            # Fetch Previous Context
            prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, c_num)
            glossary_terms = await glossary_repo.get_terms_by_series(series_id)
            character_entities = await character_repo.get_characters_by_series(series_id)

            log_lines.append(f"- **Injected Glossary Terms**: `{len(glossary_terms)}` entries")
            log_lines.append(f"- **Injected Characters**: `{len(character_entities)}` entries")
            log_lines.append(f"- **Previous Story Summary**: `{len(prev_summary or '')}` chars\n")

            if strategy == "single_pass":
                # SINGLE PASS EXECUTION
                log_lines.append("#### ⚡ Single-Pass Execution (1 LLM Call for Translation + Summary + Extraction)\n")
                t_start = time.time()
                res = await single_pass.translate_chapter_single_pass(
                    source_text=source_text,
                    series_id=series_id,
                    chapter_number=c_num,
                    model=resolved_model,
                    platform=resolved_platform,
                )
                elapsed = time.time() - t_start

                translated_text = res["translated_text"]
                chapter_summary = res["chapter_summary"]
                extract_status = res["extract_status"]
                ext_chars = res.get("extracted_characters", [])
                ext_terms = res.get("extracted_terms", [])
                sys_prompt = res.get("system_prompt", "")
                usr_prompt = res.get("user_prompt", "")
                raw_resp = res.get("raw_response", "")

                log_lines.append(f"- **Execution Time**: `{elapsed:.2f}s`")
                log_lines.append(f"- **Extract Status**: `{extract_status}`")
                log_lines.append(f"- **Extracted Characters**: `{len(ext_chars)}` | **Glossary Terms**: `{len(ext_terms)}`")

                log_lines.append("\n##### 🤖 Single-Pass System Prompt (Roles & Translation Rules):")
                log_lines.append("```text")
                log_lines.append(sys_prompt or "(None)")
                log_lines.append("```\n")

                log_lines.append("##### 💬 Single-Pass User Prompt (Sent Content & Context):")
                log_lines.append("```text")
                log_lines.append(usr_prompt[:1500] + ("\n... [truncated for log length]" if len(usr_prompt) > 1500 else ""))
                log_lines.append("```\n")

                log_lines.append("##### 📥 Raw LLM Adapter Response:")
                log_lines.append("```text")
                log_lines.append(raw_resp[:1500] + ("\n... [truncated for log length]" if len(raw_resp) > 1500 else ""))
                log_lines.append("```\n")

                log_lines.append("##### 📝 Parsed Chapter Summary Output:")
                log_lines.append("```markdown")
                log_lines.append(chapter_summary or "(No summary generated)")
                log_lines.append("```\n")

                log_lines.append("##### 📖 Parsed Translated Text Preview (First 1,000 Chars):")
                log_lines.append("```markdown")
                log_lines.append(translated_text[:1000] + ("..." if len(translated_text) > 1000 else ""))
                log_lines.append("```\n")

            else:
                # PIPELINE EXECUTION (Pass 1: Translate, Pass 2: Combined Summary & Extraction)
                log_lines.append("#### 🔄 Pipeline Execution (Pass 1: Translation -> Pass 2: Combined Summary & Extraction)\n")

                # Pass 1: Translation
                t1_start = time.time()
                trans_res = await translator.translate_chapter(
                    source_text=source_text,
                    series_id=series_id,
                    chapter_number=c_num,
                    model=resolved_model,
                    platform=resolved_platform,
                    return_details=True,
                )
                t1_elapsed = time.time() - t1_start

                translated_text = trans_res["translated_text"]
                p1_sys_prompt = trans_res.get("system_prompt", "")
                p1_usr_prompt = trans_res.get("user_prompt", "")
                p1_raw_resp = trans_res.get("raw_response", "")

                log_lines.append(f"- **Pass 1 (Translation) Time**: `{t1_elapsed:.2f}s` | Length: `{len(translated_text)}` chars")

                log_lines.append("\n##### 🤖 Pass 1 System Prompt (Roles & Translation Rules):")
                log_lines.append("```text")
                log_lines.append(p1_sys_prompt or "(None)")
                log_lines.append("```\n")

                log_lines.append("##### 💬 Pass 1 User Prompt (Sent Content & Context):")
                log_lines.append("```text")
                log_lines.append(p1_usr_prompt[:1500] + ("\n... [truncated for log length]" if len(p1_usr_prompt) > 1500 else ""))
                log_lines.append("```\n")

                log_lines.append("##### 📥 Pass 1 Raw LLM Adapter Response:")
                log_lines.append("```text")
                log_lines.append(p1_raw_resp[:1500] + ("\n... [truncated for log length]" if len(p1_raw_resp) > 1500 else ""))
                log_lines.append("```\n")

                log_lines.append("##### 📖 Pass 1 Parsed Translation Result Preview:")
                log_lines.append("```markdown")
                log_lines.append(translated_text[:1000] + ("..." if len(translated_text) > 1000 else ""))
                log_lines.append("```\n")

                # Pass 2: Summarization & Extraction Combined
                t2_start = time.time()
                sum_res = await summarizer.summarize_and_extract_chapter(
                    translated_text=translated_text,
                    previous_summary=prev_summary,
                    series_id=series_id,
                    model=resolved_model,
                    platform=resolved_platform,
                )
                t2_elapsed = time.time() - t2_start

                chapter_summary = sum_res["chapter_summary"]
                extract_status = sum_res["extract_status"]
                ext_chars = sum_res.get("extracted_characters", [])
                ext_terms = sum_res.get("extracted_terms", [])
                p2_sys_prompt = sum_res.get("system_prompt", "")
                p2_usr_prompt = sum_res.get("user_prompt", "")
                p2_raw_resp = sum_res.get("raw_response", "")

                log_lines.append(f"- **Pass 2 (Summary & Extract) Time**: `{t2_elapsed:.2f}s` | Extract Status: `{extract_status}`")
                log_lines.append(f"- **Extracted Characters**: `{len(ext_chars)}` | **Glossary Terms**: `{len(ext_terms)}`")

                log_lines.append("\n##### 🤖 Pass 2 System Prompt (Combined Rules & JSON Schema):")
                log_lines.append("```text")
                log_lines.append(p2_sys_prompt or "(None)")
                log_lines.append("```\n")

                log_lines.append("##### 💬 Pass 2 User Prompt (Sent Translated Chapter & Context):")
                log_lines.append("```text")
                log_lines.append(p2_usr_prompt[:1500] + ("\n... [truncated for log length]" if len(p2_usr_prompt) > 1500 else ""))
                log_lines.append("```\n")

                log_lines.append("##### 📥 Pass 2 Raw LLM Adapter Response:")
                log_lines.append("```text")
                log_lines.append(p2_raw_resp[:1500] + ("\n... [truncated for log length]" if len(p2_raw_resp) > 1500 else ""))
                log_lines.append("```\n")

                log_lines.append("##### 📝 Pass 2 Parsed Chapter Summary Result:")
                log_lines.append("```markdown")
                log_lines.append(chapter_summary or "(No summary generated)")
                log_lines.append("```\n")

            # Save / Update Chapter in SQLite DB
            existing_chap = await chapter_repo.get_chapter(series_id, c_num)
            chap_db_data = {
                "series_id": series_id,
                "chapter_number": c_num,
                "title": c_title,
                "source_text": source_text,
                "translated_text": translated_text,
                "chapter_summary": chapter_summary,
                "status": "translated",
                "extract_status": extract_status,
                "translated_by_model_name": resolved_model["name"],
                "translated_by_platform_name": resolved_platform["name"],
            }

            if existing_chap:
                await chapter_repo.update_chapter(existing_chap["id"], chap_db_data)
            else:
                await chapter_repo.create_chapter(chap_db_data)

            # Update Series Running Summary Memory
            new_cumulative_summary = (
                f"{prev_summary}\n\n{chapter_summary}".strip()
                if prev_summary
                else chapter_summary
            )
            await series_repo.update_series(series_id, {
                "summary": new_cumulative_summary,
                "last_translated_chapter": c_num,
            })

            log_lines.append("---\n")

    except Exception as exc:  # noqa: BLE001
        print(f"❌ Error during execution: {exc}")
        import traceback
        traceback.print_exc()
        log_lines.append(f"### ❌ Execution Exception:\n```text\n{traceback.format_exc()}\n```\n")

    # 4. Record Final Database State
    log_lines.append("## 🗄️ Final Database State Summary\n")

    # Running Series Memory
    updated_series = await series_repo.get_series_by_id(series_id)
    log_lines.append("### 📜 Cumulative Series Story Memory (`series.summary`):")
    log_lines.append("```markdown")
    log_lines.append((updated_series.get("summary") if updated_series else "") or "(Empty)")
    log_lines.append("```\n")

    # Characters Table
    final_chars = await character_repo.get_characters_by_series(series_id)
    log_lines.append(f"### 👤 Extracted Character Entities (`characters` Table: {len(final_chars)} Entries):\n")
    if final_chars:
        log_lines.append("| Name | Translated Name | Gender | Speech Style | Notes |")
        log_lines.append("|---|---|---|---|---|")
        for c in final_chars:
            log_lines.append(
                f"| `{c.get('name')}` | `{c.get('translated_name') or '-'}` | `{c.get('gender') or '-'}` | `{c.get('speech_style') or '-'}` | {c.get('notes') or '-'} |"
            )
    else:
        log_lines.append("_No character entities extracted yet._")

    log_lines.append("\n")

    # Glossary Table
    final_terms = await glossary_repo.get_terms_by_series(series_id)
    log_lines.append(f"### 🔖 Extracted Glossary Terms (`glossary_terms` Table: {len(final_terms)} Entries):\n")
    if final_terms:
        log_lines.append("| Term Source | Term Translation | Context Notes |")
        log_lines.append("|---|---|---|")
        for t in final_terms:
            log_lines.append(
                f"| `{t.get('term_source')}` | `{t.get('term_translation')}` | {t.get('notes') or '-'} |"
            )
    else:
        log_lines.append("_No glossary terms extracted yet._")

    log_lines.append("\n")

    # Write Markdown Document
    md_content = "\n".join(log_lines)
    with open(output_md_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
        f.write(md_content)

    print("\n✅ Execution completed cleanly!")
    print(f"📄 Full Markdown Log Saved To: {output_md_path}")


if __name__ == "__main__":
    target_config = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT_DIR, "sample-scripts", "series_new_platform.json")
    asyncio.run(run_and_log(target_config))
