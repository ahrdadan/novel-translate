import json
import os
import re
import time
from pathlib import Path
from typing import Any

from ..utils import BOLD, CYAN, GREEN, RED, RESET, YELLOW, print_json


def extract_chapter_number(filename: str, fallback_idx: float = 1) -> float | int:
    match = re.search(r'(\d+(?:\.\d+)?)', filename)
    if match:
        try:
            val = float(match.group(1))
            return int(val) if val.is_integer() else val
        except ValueError:
            pass
    return fallback_idx

def process_config_file(api_client, config_path: str) -> bool:
    cfg_file = Path(config_path).resolve()
    if not cfg_file.exists():
        print(f"{RED}Error: File config '{config_path}' tidak ditemukan.{RESET}")
        return False

    print(f"\n{BOLD}{CYAN}📂 Membaca Konfigurasi dari: {cfg_file}{RESET}")
    try:
        with open(cfg_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"{RED}Error membaca JSON config: {e}{RESET}")
        return False

    base_dir = cfg_file.parent
    series_info = config_data.get("series", {})
    translation_model = config_data.get("translationModel", 1)
    mode = config_data.get("mode", "async")
    strategy = config_data.get("strategy", "pipeline")
    extract = config_data.get("extract", True)

    tasks: list[dict[str, Any]] = []

    if "chapter" in config_data and isinstance(config_data["chapter"], dict):
        chap_cfg = config_data["chapter"]
        file_rel = chap_cfg.get("file") or chap_cfg.get("path")
        if file_rel:
            file_path = (base_dir / file_rel).resolve()
            if file_path.exists():
                tasks.append({
                    "chapterNumber": chap_cfg.get("chapterNumber") or extract_chapter_number(file_path.name, 1),
                    "title": chap_cfg.get("title") or f"Chapter {file_path.stem}",
                    "file_path": file_path
                })

    folder_rel = config_data.get("chaptersFolder") or config_data.get("chapters_folder") or config_data.get("folder")
    if folder_rel:
        folder_path = (base_dir / folder_rel).resolve()
        if folder_path.exists() and folder_path.is_dir():
            possible_tocs = [
                folder_path / "toc.json",
                folder_path / "TOC.json",
                folder_path / "chapters.json",
                base_dir / "toc.json",
            ]
            toc_path = next((p for p in possible_tocs if p.exists()), None)

            if toc_path:
                print(f"{GREEN}[OK] Membaca TOC Metadata dari: {toc_path}{RESET}")
                try:
                    with open(toc_path, 'r', encoding='utf-8') as tf:
                        toc_entries = json.load(tf)

                    if isinstance(toc_entries, dict):
                        toc_entries = (
                            toc_entries.get("chapters")
                            or toc_entries.get("toc")
                            or toc_entries.get("items")
                            or []
                        )

                    if isinstance(toc_entries, list):
                        for idx, entry in enumerate(toc_entries, 1):
                            if isinstance(entry, dict):
                                f_name = entry.get("file") or entry.get("path") or entry.get("filename")
                                if f_name:
                                    candidates = [
                                        (folder_path / f_name).resolve(),
                                        (base_dir / f_name).resolve(),
                                        (folder_path / Path(f_name).name).resolve(),
                                    ]
                                    hp = next((c for c in candidates if c.exists()), None)
                                    if hp:
                                        c_num = entry.get("chapterNumber") or entry.get("chapter_number") or entry.get("number") or extract_chapter_number(hp.name, idx)
                                        c_title = entry.get("title") or f"Chapter {c_num}"
                                        tasks.append({
                                            "chapterNumber": c_num,
                                            "title": c_title,
                                            "file_path": hp
                                        })
                except Exception as e:  # noqa: BLE001
                    print(f"{YELLOW}Warning: Gagal membaca {toc_path.name}: {e}. Memakai scan folder biasa.{RESET}")

            if not tasks:
                html_files = sorted(
                    list(folder_path.glob("*.html")) + list(folder_path.glob("*.htm")),
                    key=lambda p: extract_chapter_number(p.name)
                )
                for idx, hp in enumerate(html_files, 1):
                    chap_num = extract_chapter_number(hp.name, idx)
                    tasks.append({
                        "chapterNumber": chap_num,
                        "title": f"Chapter {chap_num}",
                        "file_path": hp
                    })

    if not tasks:
        print(f"{RED}Error: Tidak ada file HTML chapter yang ditemukan dari config '{config_path}'.{RESET}")
        print(f"{YELLOW}Pastikan field 'file' di 'chapter' atau 'chaptersFolder' diisi dengan path yang benar.{RESET}")
        return False

    print(f"{GREEN}[OK] Ditemukan {len(tasks)} chapter HTML untuk diproses.{RESET}\n")

    success_count = 0
    for i, task in enumerate(tasks, 1):
        hp = task["file_path"]
        try:
            with open(hp, 'r', encoding='utf-8') as hf:
                html_content = hf.read()
        except Exception as e:  # noqa: BLE001
            print(f"  {RED}[{i}/{len(tasks)}] Gagal membaca {hp.name}: {e}{RESET}")
            continue

        payload = {
            "series": series_info,
            "chapter": {
                "chapterNumber": task["chapterNumber"],
                "title": task["title"],
                "sourceText": html_content,
                "sourceLanguage": series_info.get("sourceLanguage", "auto")
            },
            "translationModel": translation_model,
            "mode": mode,
            "strategy": strategy,
            "extract": extract
        }
        if "summarizeModel" in config_data:
            payload["summarizeModel"] = config_data["summarizeModel"]
        if "extractionModel" in config_data:
            payload["extractionModel"] = config_data["extractionModel"]
        if "systemPrompt" in config_data:
            payload["systemPrompt"] = config_data["systemPrompt"]
            
        # Add force flags if they exist
        if "forceTranslate" in config_data:
            payload["forceTranslate"] = config_data["forceTranslate"]
        elif "force_translate" in config_data:
            payload["forceTranslate"] = config_data["force_translate"]
            
        if "forceSummary" in config_data:
            payload["forceSummary"] = config_data["forceSummary"]
        elif "force_summary" in config_data:
            payload["forceSummary"] = config_data["force_summary"]

        print(f"  {CYAN}[{i}/{len(tasks)}] Submitting Chapter {task['chapterNumber']} ({hp.name})...{RESET}")
        try:
            res = api_client.post(f"{api_client.api_v1}/translate-novel", json=payload)
            if res.status_code in (200, 201, 202):
                res_data = res.json()
                if "results" in res_data:
                    accepted = res_data.get("accepted_count", 0)
                    skipped = res_data.get("skipped_count", 0)
                    print(f"    {GREEN}+ Success [{res.status_code}]{RESET} | Queued {accepted} models (Skipped {skipped})")
                else:
                    job_id = res_data.get("job_id") or res_data.get("chapter", {}).get("id")
                    print(f"    {GREEN}+ Success [{res.status_code}]{RESET} | Job ID: {job_id} | Status: {res_data.get('status')}")
                success_count += 1
            else:
                print(f"    {RED}- Failed [{res.status_code}]{RESET} | {res.text[:120]}")
        except Exception as e:  # noqa: BLE001
            print(f"    {RED}- Connection Error: {e}{RESET}")

    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}HASIL BATCH IMPORT: {GREEN}{success_count}/{len(tasks)} Chapter Berhasil Dikirim.{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")
    return success_count > 0

def menu_import_config(api_client) -> None:
    print(f"\n{BOLD}{CYAN}[ 📁 1. Import Series & HTML Chapter dari config JSON ]{RESET}")
    
    configs = []
    search_dirs = [Path(".")]
    seen = set()
    for sd in search_dirs:
        if sd.exists() and sd.is_dir():
            for jf in sd.glob("*.json"):
                if jf.name not in seen:
                    seen.add(jf.name)
                    configs.append(jf)

    if configs:
        print(f"{BOLD}File JSON config yang tersedia:{RESET}")
        for idx, cfg in enumerate(configs, 1):
            print(f"  [{idx}] {cfg.name} ({cfg})")
        print("  [C] Input Custom Path")
        choice = input(f"{BOLD}Pilihan Anda [1-{len(configs)} / C] (Default: 1): {RESET}").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(configs):
            process_config_file(api_client, str(configs[int(choice) - 1]))
            return
        elif choice.upper() == "C":
            cfg_input = input(f"{BOLD}Masukkan Path Custom JSON Config: {RESET}").strip()
            if cfg_input:
                process_config_file(api_client, cfg_input)
                return

    default_config = "series.json"

    process_config_file(api_client, default_config)

def menu_translate_novel_interactive(api_client) -> None:
    print(f"\n{BOLD}{CYAN}[ 🚀 2. Manual Translate Novel Chapter (Form Input) ]{RESET}")

    existing_series = api_client.fetch_series()
    series_input = None

    if existing_series:
        print(f"\n{BOLD}Pilih Series terdaftar atau buat Series baru:{RESET}")
        for idx, s in enumerate(existing_series, 1):
            print(f"  [{idx}] {s.get('name')} (ID: {s.get('id')})")
        print("  [N] Input Nama Series Baru")
        
        choice = input(f"{BOLD}Pilihan Anda [1-{len(existing_series)} / N]: {RESET}").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(existing_series):
            series_input = {"id": existing_series[int(choice) - 1]["id"]}
    
    if not series_input:
        series_name = input(f"{BOLD}Nama Novel / Series: {RESET}").strip() or f"Demo Series {int(time.time())}"
        series_input = {"name": series_name}

    chap_num_str = input(f"{BOLD}Nomor Chapter [Default: 1]: {RESET}").strip()
    chap_num = 1
    if chap_num_str:
        try:
            v = float(chap_num_str)
            chap_num = int(v) if v.is_integer() else v
        except ValueError:
            chap_num = 1

    print(f"{BOLD}Masukkan Teks / Path HTML File (atau tekan Enter untuk teks demo):{RESET}")
    txt_input = input("> ").strip()
    
    source_text = txt_input
    if os.path.exists(txt_input):
        with open(txt_input, 'r', encoding='utf-8') as f:
            source_text = f.read()
        print(f"{GREEN}[OK] Membaca teks dari file: {txt_input}{RESET}")
    elif not source_text:
        source_text = "第一章 开局。在这个玄幻世界里，唯有实力才是根本。"

    payload = {
        "series": series_input,
        "chapter": {
            "chapterNumber": chap_num,
            "title": f"Chapter {chap_num}",
            "sourceText": source_text
        },
        "translationModel": 1,
        "mode": "async"
    }

    print(f"\n{BOLD}Mengirim request...{RESET}")
    res = api_client.post(f"{api_client.api_v1}/translate-novel", json=payload)
    print(f"Status Code: {GREEN if res.status_code in (200, 201, 202) else RED}{res.status_code}{RESET}")
    print_json("Response API", res.json() if res.status_code in (200, 201, 202) else res.text)
