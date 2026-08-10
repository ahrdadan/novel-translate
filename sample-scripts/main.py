#!/usr/bin/env python3
"""
Novel Translation API — Client Runner & CLI Application
======================================================
Standalone script to translate novel chapters from JSON configs and HTML files.

Usage:
    # 1. Direct Batch Import from JSON Config File:
    uv run python sample-scripts/main.py sample-scripts/series.json

    # 2. Interactive CLI Menu:
    uv run python sample-scripts/main.py [--base-url http://localhost:8000]
"""

import argparse
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Reconfigure stdout for UTF-8 on Windows terminal
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', line_buffering=True)

try:
    import httpx
except ImportError:
    print("Error: 'httpx' library is required. Install via 'uv add httpx' or 'pip install httpx'.")
    sys.exit(1)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


class NovelTranslationRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.api_v1 = f"{self.base_url}/api/v1"
        self.client = httpx.Client(timeout=60.0)

    def print_banner(self):
        print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
        print(f"{BOLD}{MAGENTA} 📖  NOVEL TRANSLATION SYSTEM — CLIENT RUNNER & CLI{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")
        print(f" Connected Server Base URL: {YELLOW}{self.base_url}{RESET}")

    def print_json(self, label: str, data: Any):
        print(f"\n{BOLD}{YELLOW}--- {label} ---{RESET}")
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(data)

    def check_server(self) -> bool:
        try:
            res = self.client.get(f"{self.base_url}/")
            return res.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def fetch_models(self) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/models")
            if res.status_code == 200:
                return res.json()
        except Exception:  # noqa: BLE001, S110
            pass
        return []

    def fetch_series(self) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/series")
            if res.status_code == 200:
                return res.json()
        except Exception:  # noqa: BLE001, S110
            pass
        return []

    def fetch_jobs(self, series_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        try:
            url = f"{self.api_v1}/jobs"
            params = []
            if series_id:
                params.append(f"series_id={series_id}")
            if status:
                params.append(f"status={status}")
            if params:
                url += "?" + "&".join(params)
            res = self.client.get(url)
            if res.status_code == 200:
                return res.json()
        except Exception:  # noqa: BLE001, S110
            pass
        return []

    def fetch_chapters(self, series_id: int) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/series/{series_id}/chapters")
            if res.status_code == 200:
                return res.json()
        except Exception:  # noqa: BLE001, S110
            pass
        return []

    def fetch_chapter_detail(self, series_id: int, chapter_number: float) -> dict[str, Any] | None:
        try:
            res = self.client.get(f"{self.api_v1}/series/{series_id}/chapters/{chapter_number}")
            if res.status_code == 200:
                return res.json()
        except Exception:  # noqa: BLE001, S110
            pass
        return None

    def extract_chapter_number(self, filename: str, fallback_idx: float = 1) -> float | int:
        """Extract chapter number (int or float) from filenames like chapter_1.5.html -> 1.5 or response_chapter0006.html -> 6."""
        match = re.search(r'(\d+(?:\.\d+)?)', filename)
        if match:
            try:
                val = float(match.group(1))
                return int(val) if val.is_integer() else val
            except ValueError:
                pass
        return fallback_idx

    def process_config_file(self, config_path: str) -> bool:
        """Process series.json config file with single HTML file or multiple HTML folder."""
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

        # Determine target chapter HTML files
        tasks: list[dict[str, Any]] = []

        # Option A: Single Chapter File specified
        if "chapter" in config_data and isinstance(config_data["chapter"], dict):
            chap_cfg = config_data["chapter"]
            file_rel = chap_cfg.get("file") or chap_cfg.get("path")
            if file_rel:
                file_path = (base_dir / file_rel).resolve()
                if file_path.exists():
                    tasks.append({
                        "chapterNumber": chap_cfg.get("chapterNumber") or self.extract_chapter_number(file_path.name, 1),
                        "title": chap_cfg.get("title") or f"Chapter {file_path.stem}",
                        "file_path": file_path
                    })

        # Option B: Folder of HTML files specified (reads toc.json if present)
        folder_rel = config_data.get("chaptersFolder") or config_data.get("chapters_folder") or config_data.get("folder")
        if folder_rel:
            folder_path = (base_dir / folder_rel).resolve()
            if folder_path.exists() and folder_path.is_dir():
                # Search for TOC metadata file
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
                                        # Bulletproof path resolution
                                        candidates = [
                                            (folder_path / f_name).resolve(),
                                            (base_dir / f_name).resolve(),
                                            (folder_path / Path(f_name).name).resolve(),
                                        ]
                                        hp = next((c for c in candidates if c.exists()), None)
                                        if hp:
                                            c_num = entry.get("chapterNumber") or entry.get("chapter_number") or entry.get("number") or self.extract_chapter_number(hp.name, idx)
                                            c_title = entry.get("title") or f"Chapter {c_num}"
                                            tasks.append({
                                                "chapterNumber": c_num,
                                                "title": c_title,
                                                "file_path": hp
                                            })
                    except Exception as e:  # noqa: BLE001
                        print(f"{YELLOW}Warning: Gagal membaca {toc_path.name}: {e}. Memakai scan folder biasa.{RESET}")

                # Fallback if no tasks were added via toc.json
                if not tasks:
                    html_files = sorted(
                        list(folder_path.glob("*.html")) + list(folder_path.glob("*.htm")),
                        key=lambda p: self.extract_chapter_number(p.name)
                    )
                    for idx, hp in enumerate(html_files, 1):
                        chap_num = self.extract_chapter_number(hp.name, idx)
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

        # Submit translation requests for each HTML file
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

            print(f"  {CYAN}[{i}/{len(tasks)}] Submitting Chapter {task['chapterNumber']} ({hp.name})...{RESET}")
            try:
                res = self.client.post(f"{self.api_v1}/translate-novel", json=payload)
                if res.status_code in (200, 201, 202):
                    res_data = res.json()
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

    # --- Interactive CLI Options ---

    def menu_import_config(self):
        print(f"\n{BOLD}{CYAN}[ 📁 1. Import Series & HTML Chapter dari config JSON ]{RESET}")
        
        configs = []
        search_dirs = [Path("sample-scripts"), Path(".")]
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
                self.process_config_file(str(configs[int(choice) - 1]))
                return
            elif choice.upper() == "C":
                cfg_input = input(f"{BOLD}Masukkan Path Custom JSON Config: {RESET}").strip()
                if cfg_input:
                    self.process_config_file(cfg_input)
                    return

        default_config = "sample-scripts/series.json"
        if not os.path.exists(default_config) and os.path.exists("series.json"):
            default_config = "series.json"

        self.process_config_file(default_config)

    def menu_translate_novel_interactive(self):
        print(f"\n{BOLD}{CYAN}[ 🚀 2. Manual Translate Novel Chapter (Form Input) ]{RESET}")

        # Series Input
        existing_series = self.fetch_series()
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
        res = self.client.post(f"{self.api_v1}/translate-novel", json=payload)
        print(f"Status Code: {GREEN if res.status_code in (200, 201, 202) else RED}{res.status_code}{RESET}")
        self.print_json("Response API", res.json() if res.status_code in (200, 201, 202) else res.text)

    def menu_list_models(self):
        print(f"\n{BOLD}{CYAN}[ 🤖 3. Models & Platforms List ]{RESET}")
        models = self.fetch_models()
        self.print_json("Registered Models", models if models else "Tidak ada model terdaftar.")

    def menu_list_series(self):
        print(f"\n{BOLD}{CYAN}[ 📚 4. Daftar & Detail Series (Termasuk Plot Summary Memory) ]{RESET}")
        series_list = self.fetch_series()
        if not series_list:
            print(f"{YELLOW}Belum ada series terdaftar di database.{RESET}")
            return

        self.print_json("Series List", series_list)

        s_id_input = input(f"\n{BOLD}Masukkan ID Series untuk melihat Detail Lengkap & Cumulative Plot Summary (Enter untuk kembali): {RESET}").strip()
        if s_id_input.isdigit():
            res = self.client.get(f"{self.api_v1}/series/{s_id_input}")
            if res.status_code == 200:
                s_detail = res.json()
                print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
                print(f"{BOLD}{MAGENTA} 📚 DETAIL SERIES: {s_detail.get('name')} (ID: {s_detail.get('id')}){RESET}")
                print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")
                print(f"  Judul Asli       : {s_detail.get('original_title') or '-'}")
                print(f"  Penulis (Author) : {s_detail.get('author') or '-'}")
                print(f"  Status Novel     : {s_detail.get('status') or '-'}")
                print(f"  Deskripsi        : {s_detail.get('description') or '-'}")
                print(f"  Last Chapter     : #{s_detail.get('last_translated_chapter', 0)}")
                print(f"  Translation Model: {s_detail.get('translation_model_id') or 'Default'}")
                print(f"  Extraction Model : {s_detail.get('extraction_model_id') or 'Default'}")
                print(f"  System Prompt ID : {s_detail.get('system_prompt_id') or 'Default'}")
                print(f"  Tgl Dibuat       : {s_detail.get('created_at') or '-'}")

                summary = s_detail.get("summary")
                if summary:
                    print(f"\n{BOLD}{YELLOW}--- 📜 RINGKASAN ALUR CERITA KUMULATIF (Running Story Summary Memory) ---{RESET}")
                    print(f"{summary}")
                else:
                    print(f"\n{YELLOW}⚠️ Belum ada ringkasan alur cerita kumulatif (series summary belum terbentuk).{RESET}")

                print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}\n")
            else:
                print(f"{RED}Series ID {s_id_input} tidak ditemukan.{RESET}")

    def menu_check_jobs(self):
        print(f"\n{BOLD}{CYAN}[ 📊 5. Background Jobs Tracker ]{RESET}")
        print(f"{BOLD}Pilih filter status job yang ingin ditampilkan:{RESET}")
        print(f"  {GREEN}[1]{RESET} Job Unfinished / Bermasalah (Queued, Processing, Failed) [Default]")
        print(f"  {GREEN}[2]{RESET} Hanya Job yang GAGAL (Failed)")
        print(f"  {GREEN}[3]{RESET} Hanya Job yang Sedang Berjalan / Antrean (Processing, Queued)")
        print(f"  {GREEN}[4]{RESET} Semua Job (Termasuk Completed)")

        filter_choice = input(f"\n{BOLD}Pilihan Filter [1-4] (Default: 1): {RESET}").strip()

        status_filter = "queued,processing,failed"
        if filter_choice == "2":
            status_filter = "failed"
        elif filter_choice == "3":
            status_filter = "queued,processing"
        elif filter_choice == "4":
            status_filter = None

        jobs = self.fetch_jobs(status=status_filter)
        if jobs:
            filter_label = f"Filter: {status_filter}" if status_filter else "Semua Job"
            self.print_json(f"Job Queue List ({filter_label})", jobs)

            print(f"\n{BOLD}Pilihan Aksi:{RESET}")
            print("  [ID]  Masukkan Job ID untuk detail status")
            print("  [R]   Retry / Retranslate Job Gagal")
            print("  [Enter] Kembali")

            user_act = input(f"\n{BOLD}Pilihan Anda [Job ID / R / Enter]: {RESET}").strip()
            if user_act.isdigit():
                j_res = self.client.get(f"{self.api_v1}/jobs/{user_act}")
                if j_res.status_code == 200:
                    self.print_json(f"Job #{user_act} Details", j_res.json())
                else:
                    print(f"{RED}Job ID {user_act} tidak ditemukan.{RESET}")
            elif user_act.upper() == "R":
                retry_job_id = input(f"{BOLD}Masukkan Job ID yang ingin di-retry: {RESET}").strip()
                if retry_job_id.isdigit():
                    try:
                        r_res = self.client.post(f"{self.api_v1}/jobs/{retry_job_id}/retry")
                        if r_res.status_code == 200:
                            print(f"{GREEN}✅ Job #{retry_job_id} berhasil di-retry & masuk ke antrean!{RESET}")
                            print(f"{YELLOW}Buka Menu [7] Realtime Monitor untuk memantau pengerjaan.{RESET}\n")
                        else:
                            print(f"{RED}❌ Gagal retry Job #{retry_job_id} [{r_res.status_code}]: {r_res.text}{RESET}\n")
                    except Exception as e:  # noqa: BLE001
                        print(f"{RED}Error koneksi: {e}{RESET}\n")
        else:
            print(f"{YELLOW}Tidak ada background job yang cocok dengan filter ({status_filter or 'semua'}).{RESET}")

    def menu_view_translated_chapters(self):
        print(f"\n{BOLD}{CYAN}[ 📖 6. Lihat Chapter & Hasil Terjemahan ]{RESET}")
        series_list = self.fetch_series()
        if not series_list:
            print(f"{YELLOW}Belum ada series terdaftar di database.{RESET}")
            return

        print(f"\n{BOLD}Pilih Series:{RESET}")
        for idx, s in enumerate(series_list, 1):
            print(f"  [{idx}] {s.get('name')} (ID: {s.get('id')}) | Total/Last Chapter: #{s.get('last_translated_chapter', 0)}")

        choice = input(f"\n{BOLD}Pilihan Series [1-{len(series_list)}] (Enter untuk batal): {RESET}").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(series_list)):
            return

        selected_series = series_list[int(choice) - 1]
        series_id = selected_series["id"]
        series_name = selected_series["name"]

        chapters = self.fetch_chapters(series_id)
        if not chapters:
            print(f"{YELLOW}Belum ada chapter terdaftar untuk series '{series_name}'.{RESET}")
            return

        jobs = self.fetch_jobs(series_id=series_id)
        job_by_chap = {j.get("chapter_number"): j for j in jobs if j.get("chapter_number")}

        print(f"\n{BOLD}{CYAN}Daftar Chapter untuk Series '{series_name}' (ID: {series_id}):{RESET}")
        for c in chapters:
            c_num = c.get("chapter_number")
            c_title = c.get("title") or f"Chapter {c_num}"
            status = c.get("status", "unknown")
            job_info = job_by_chap.get(c_num)

            if job_info and job_info.get("status") == "failed":
                status = "failed"

            status_color = GREEN if status in ("completed", "translated") else (YELLOW if status == "processing" else RED)
            model_name = c.get("translated_by_model_name") or "-"
            
            queue_badge = ""
            if job_info and job_info.get("status") in ("queued", "processing") and job_info.get("queue_position"):
                queue_badge = f" {CYAN}(Antrean ke-{job_info.get('queue_position')} dari {job_info.get('total_in_queue')} total job){RESET}"

            err_summary = ""
            if (status == "failed" or (job_info and job_info.get("status") == "failed")) and job_info and job_info.get("error"):
                err_summary = f" {RED}(Error: {job_info.get('error')[:45]}...){RESET}"

            print(f"  [{c_num}] {c_title} | Status: {status_color}{status}{RESET} | Model: {model_name}{queue_badge}{err_summary}")

        chap_choice = input(f"\n{BOLD}Masukkan Nomor Chapter untuk membaca/melihat hasil (Enter untuk batal): {RESET}").strip()
        if not chap_choice:
            return

        try:
            val = float(chap_choice)
            chap_num = int(val) if val.is_integer() else val
        except ValueError:
            print(f"{RED}Nomor chapter tidak valid.{RESET}")
            return
        detail = self.fetch_chapter_detail(series_id, chap_num)
        if not detail:
            print(f"{RED}Chapter {chap_num} tidak ditemukan untuk series ID {series_id}.{RESET}")
            return

        matching_job = job_by_chap.get(chap_num)
        if not matching_job:
            job_res = self.fetch_jobs(series_id=series_id, status=None)
            matching_job = next((j for j in job_res if j.get("chapter_number") == chap_num), None)

        chap_status = detail.get('status')
        if matching_job and matching_job.get('status') == 'failed':
            chap_status = 'failed'

        print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
        print(f"{BOLD}{MAGENTA} 📜 DETAIL CHAPTER {detail.get('chapter_number')}: {detail.get('title') or ''}{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")
        print(f"  Status Terjemahan: {GREEN if chap_status in ('completed', 'translated') else (YELLOW if chap_status in ('processing', 'queued', 'pending') else RED)}{chap_status}{RESET}")
        print(f"  Status Ekstraksi : {detail.get('extract_status')}")
        print(f"  Model Translasi  : {detail.get('translated_by_model_name') or '-'}")
        print(f"  Waktu Translasi  : {detail.get('translated_at') or '-'}")

        if matching_job and matching_job.get("status") in ("queued", "processing") and matching_job.get("queue_position"):
            print(f"  Posisi Antrean   : {CYAN}Antrean ke-{matching_job.get('queue_position')} dari {matching_job.get('total_in_queue')} total job yang berjalan/antre{RESET}")

        if (chap_status == "failed" or (matching_job and matching_job.get("status") == "failed")) and matching_job and matching_job.get("error"):
            print(f"\n{BOLD}{RED}❌ DETAIL ERROR PENYEBAB GAGAL (JOB #{matching_job.get('id')}):{RESET}")
            print(f"{RED}{matching_job.get('error')}{RESET}")
        elif chap_status == "failed":
            print(f"\n{BOLD}{RED}❌ STATUS CHAPTER GAGAL (FAILED){RESET}")

        print(f"\n{BOLD}{CYAN}Pilih Konten Yang Ingin Dilihat:{RESET}")
        print(f"  {GREEN}[1]{RESET} 📖 Hasil Terjemahan Saja (Translated Text)")
        print(f"  {GREEN}[2]{RESET} 📝 Ringkasan Chapter Saja (Chapter Summary)")
        print(f"  {GREEN}[3]{RESET} 📄 Teks Sumber Saja (Original Source Text)")
        print(f"  {GREEN}[4]{RESET} 📊 Lihat Semua Detail (Metadata + Summary + Terjemahan) [Default]")

        view_mode = input(f"\n{BOLD}Pilihan Tampilan [1-4] (Default: 4): {RESET}").strip()

        if view_mode == "1":
            print(f"\n{BOLD}{GREEN}--- Hasil Terjemahan (Translated Text) ---{RESET}")
            if detail.get("translated_text"):
                print(detail.get("translated_text"))
            else:
                print(f"{YELLOW}⚠️ Teks terjemahan belum tersedia. (Status: {chap_status}){RESET}")

        elif view_mode == "2":
            print(f"\n{BOLD}{YELLOW}--- Ringkasan Chapter (Summary) ---{RESET}")
            if detail.get("chapter_summary"):
                print(detail.get("chapter_summary"))
            else:
                print(f"{YELLOW}⚠️ Ringkasan chapter belum tersedia.{RESET}")

        elif view_mode == "3":
            print(f"\n{BOLD}{CYAN}--- Teks Sumber (Original Source Text) ---{RESET}")
            if detail.get("source_text"):
                print(detail.get("source_text")[:3000])
                if len(detail.get("source_text", "")) > 3000:
                    print(f"... [{len(detail.get('source_text')) - 3000} karakter disembunyikan]")
            else:
                print(f"{YELLOW}⚠️ Teks sumber tidak tersedia.{RESET}")

        else:
            if detail.get("chapter_summary"):
                print(f"\n{BOLD}{YELLOW}--- Ringkasan Chapter (Summary) ---{RESET}")
                print(detail.get("chapter_summary"))

            translated = detail.get("translated_text")
            if translated:
                print(f"\n{BOLD}{GREEN}--- Hasil Terjemahan (Translated Text) ---{RESET}")
                print(translated)
            else:
                print(f"\n{YELLOW}⚠️ Teks terjemahan belum tersedia. (Status: {chap_status}){RESET}")

        print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
        print(" Pilihan Aksi:")
        print(f"  {GREEN}[R]{RESET} 🔄 Retranslate / Retry Chapter Ini (Proses Ulang)")
        print(f"  {RED}[Enter]{RESET} 🔙 Kembali ke Menu Utama")
        act_choice = input(f"\n{BOLD}Pilihan Anda [R / Enter]: {RESET}").strip().upper()

        if act_choice == "R":
            print(f"\n{BOLD}{CYAN}Mengirim Request Retranslate untuk Chapter #{chap_num}...{RESET}")
            try:
                retry_res = self.client.post(
                    f"{self.api_v1}/series/{series_id}/chapters/{chap_num}/retranslate",
                    json={"mode": "async", "forceTranslate": True}
                )
                if retry_res.status_code in (200, 201, 202):
                    res_data = retry_res.json()
                    job_id = res_data.get("job_id") or res_data.get("id")
                    print(f"{GREEN}✅ Berhasil mengirim request Retry! Job ID: #{job_id}{RESET}")
                    print(f"{YELLOW}Buka Menu [7] Realtime Monitor untuk memantau pengerjaan secara live.{RESET}\n")
                else:
                    print(f"{RED}❌ Gagal Retranslate [{retry_res.status_code}]: {retry_res.text}{RESET}\n")
            except Exception as e:  # noqa: BLE001
                print(f"{RED}Error koneksi: {e}{RESET}\n")

    def menu_realtime_websocket_monitor(self):
        print(f"\n{BOLD}{CYAN}[ 📡 7. Realtime Live WebSocket Monitor ]{RESET}")
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/v1/ws/jobs"
        print(f" Connecting to Realtime WebSocket: {YELLOW}{ws_url}{RESET}")
        print(f"{BOLD}Tekan Ctrl+C untuk keluar dari monitoring live.{RESET}\n")

        try:
            import asyncio

            import websockets
        except ImportError:
            print(f"{RED}Error: Package 'websockets' belum terinstall. Install dengan `uv add websockets`.{RESET}")
            return

        def render_ws_message(data: dict):
            msg_type = data.get("type", "event")
            msg = data.get("message") or data.get("details") or ""
            timestamp = data.get("timestamp") or time.strftime("%H:%M:%S")

            s_name = data.get("series_name") or f"Series #{data.get('series_id', '?')}"
            c_num = data.get("chapter_number") or "?"
            c_title = data.get("chapter_title") or f"Chapter #{c_num}"

            if msg_type == "job_started":
                print(f"[{timestamp}] ├── {BOLD}{CYAN}🚀 Memproses Series: '{s_name}' | {c_title} (Job #{data.get('job_id')}){RESET}")
            elif msg_type == "stage_progress":
                p_start = data.get("paragraph_start")
                p_end = data.get("paragraph_end")
                total_p = data.get("total_paragraphs")
                total_c = data.get("total_chunks")
                chunk = data.get("chunk")
                if total_c and total_c > 1:
                    print(f"[{timestamp}] │   ├── {BOLD}{YELLOW}✍️ Translating paragraph {p_start}-{p_end}/{total_p} (Chunk {chunk}/{total_c}){RESET}")
                else:
                    print(f"[{timestamp}] │   ├── {BOLD}{YELLOW}✍️ Translating {total_p} paragraphs ({s_name} - {c_title})...{RESET}")
            elif msg_type == "stage_update":
                stage = data.get("stage", "")
                if stage == "resolving_model":
                    print(f"[{timestamp}] │   ├── {BOLD}{CYAN}⚙️ Menyiapkan Model Translasi untuk '{s_name}'...{RESET}")
                elif stage == "translating":
                    print(f"[{timestamp}] │   ├── {BOLD}{YELLOW}✍️ Memulai Translasi Teks '{c_title}'...{RESET}")
                elif stage == "translating_complete":
                    print(f"[{timestamp}] │   ├── {BOLD}{GREEN}✅ Translasi Teks Selesai!{RESET}")
                elif stage == "summarizing":
                    print(f"[{timestamp}] │   ├── {BOLD}{MAGENTA}📝 Memperbarui Ringkasan Alur Cerita (Plot Summary)...{RESET}")
                elif stage == "summarizing_complete":
                    print(f"[{timestamp}] │   ├── {BOLD}{GREEN}✅ Ringkasan Alur Cerita Selesai!{RESET}")
                elif stage == "extracting":
                    print(f"[{timestamp}] │   ├── {BOLD}{CYAN}🔍 Mengekstrak Karakter & Glosarium Baru...{RESET}")
                elif stage == "extracting_complete":
                    print(f"[{timestamp}] │   ├── {BOLD}{GREEN}✅ Ekstraksi Entitas Selesai!{RESET}")
                else:
                    print(f"[{timestamp}] │   ├── {BOLD}{YELLOW}[{stage.upper()}]{RESET} {msg}")
            elif msg_type == "job_completed":
                print(f"[{timestamp}] └── {BOLD}{GREEN}🎉 Series '{s_name}' | {c_title} Selesai Sepenuhnya! (Job #{data.get('job_id')}){RESET}\n")
            elif msg_type == "job_failed":
                print(f"[{timestamp}] └── {BOLD}{RED}❌ Job #{data.get('job_id')} ({s_name} - {c_title}) Gagal!{RESET}")
                if data.get("error"):
                    print(f"         {RED}Penyebab Error: {data.get('error')}{RESET}\n")
            elif msg_type == "connection_established":
                print(f"[{timestamp}] {BOLD}{GREEN}🟢 [STATUS SISTEM]{RESET} {msg}")
                if data.get("jobs"):
                    print(f"         Total Job Belum Selesai (Queued/Processing/Failed): {len(data['jobs'])}")
            else:
                print(f"[{timestamp}] │   ├── {BOLD}{MAGENTA}[{msg_type.upper()}]{RESET} {msg}")

        async def listen_ws():
            try:
                async with websockets.connect(ws_url) as ws:
                    print(f"{GREEN}🟢 Connected! Mendengarkan real-time event background job...{RESET}\n")
                    while True:
                        raw = await ws.recv()
                        try:
                            data = json.loads(raw)
                            if data.get("type") == "history":
                                print(f"{BOLD}{CYAN}📜 --- HISTORI EVENT 5 JOB TERAKHIR ---{RESET}")
                                for ev in data.get("events", []):
                                    render_ws_message(ev)
                                print(f"{BOLD}{CYAN}---------------------------------------{RESET}\n")
                            else:
                                render_ws_message(data)
                        except Exception:  # noqa: BLE001
                            print(f"[{time.strftime('%H:%M:%S')}] {raw}")
            except Exception as e:  # noqa: BLE001
                print(f"\n{RED}Koneksi WebSocket terputus: {e}{RESET}")

        try:
            asyncio.run(listen_ws())
        except KeyboardInterrupt:
            print(f"\n{YELLOW}WebSocket monitoring dihentikan.{RESET}")

    def menu_manage_glossary_and_characters(self):
        print(f"\n{BOLD}{CYAN}[ 🔖 8. Kelola Glosarium & Karakter Series ]{RESET}")
        series_list = self.fetch_series()
        if not series_list:
            print(f"{YELLOW}Belum ada series terdaftar di database.{RESET}")
            return

        print(f"\n{BOLD}Pilih Series:{RESET}")
        for idx, s in enumerate(series_list, 1):
            print(f"  [{idx}] {s.get('name')} (ID: {s.get('id')})")

        choice = input(f"\n{BOLD}Pilihan Series [1-{len(series_list)}] (Enter untuk batal): {RESET}").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(series_list)):
            return

        selected_series = series_list[int(choice) - 1]
        series_id = selected_series["id"]
        series_name = selected_series["name"]

        while True:
            print(f"\n{BOLD}{CYAN}=== KELOLA GLOSARIUM & KARAKTER: {series_name} (ID: {series_id}) ==={RESET}")
            print(f"  {GREEN}[1]{RESET} 📖 Lihat Daftar Glosarium (Glossary Terms)")
            print(f"  {GREEN}[2]{RESET} ➕ Tambah Istilah Glosarium Baru")
            print(f"  {GREEN}[3]{RESET} 👤 Lihat Daftar Karakter (Characters)")
            print(f"  {GREEN}[4]{RESET} ➕ Tambah Karakter Baru")
            print(f"  {RED}[0]{RESET} 🔙 Kembali ke Menu Utama")

            sub_choice = input(f"\n{BOLD}Pilihan Anda [0-4]: {RESET}").strip()
            if sub_choice == "1":
                res = self.client.get(f"{self.api_v1}/series/{series_id}/glossary")
                if res.status_code == 200:
                    terms = res.json()
                    self.print_json(f"Glossary Terms — {series_name}", terms)
                else:
                    print(f"{RED}Gagal mengambil glosarium: {res.text}{RESET}")

            elif sub_choice == "2":
                print(f"\n{BOLD}{CYAN}--- Tambah Glosarium Baru ---{RESET}")
                t_src = input(f"{BOLD}Istilah Asal (term_source, misal: 'Heavenly Sword'): {RESET}").strip()
                t_trans = input(f"{BOLD}Terjemahan (term_translation, misal: 'Pedang Surgawi'): {RESET}").strip()
                notes = input(f"{BOLD}Catatan Tambahan (opsional): {RESET}").strip()

                if not t_src or not t_trans:
                    print(f"{RED}Istilah asal dan terjemahan wajib diisi!{RESET}")
                    continue

                payload = {"term_source": t_src, "term_translation": t_trans, "notes": notes or None}
                res = self.client.post(f"{self.api_v1}/series/{series_id}/glossary", json=payload)
                if res.status_code in (200, 201):
                    print(f"{GREEN}✅ Berhasil menambahkan glosarium baru!{RESET}")
                    self.print_json("New Glossary Term", res.json())
                else:
                    print(f"{RED}❌ Gagal membuat glosarium: {res.text}{RESET}")

            elif sub_choice == "3":
                res = self.client.get(f"{self.api_v1}/series/{series_id}/characters")
                if res.status_code == 200:
                    chars = res.json()
                    self.print_json(f"Character Entities — {series_name}", chars)
                else:
                    print(f"{RED}Gagal mengambil daftar karakter: {res.text}{RESET}")

            elif sub_choice == "4":
                print(f"\n{BOLD}{CYAN}--- Tambah Karakter Baru ---{RESET}")
                c_name = input(f"{BOLD}Nama Asal (name, misal: 'Lee Ha-young'): {RESET}").strip()
                c_trans = input(f"{BOLD}Nama Terjemahan (translated_name): {RESET}").strip()
                gender = input(f"{BOLD}Gender [male/female/unknown] (default: male): {RESET}").strip() or "male"
                speech = input(f"{BOLD}Gaya Bicara (speech_style, misal: polite/casual/archaic/rude): {RESET}").strip() or "casual"
                notes = input(f"{BOLD}Catatan Peran/Latar Belakang (opsional): {RESET}").strip()

                if not c_name or not c_trans:
                    print(f"{RED}Nama asal dan terjemahan wajib diisi!{RESET}")
                    continue

                payload = {
                    "name": c_name,
                    "translated_name": c_trans,
                    "gender": gender,
                    "speech_style": speech,
                    "notes": notes or None
                }
                res = self.client.post(f"{self.api_v1}/series/{series_id}/characters", json=payload)
                if res.status_code in (200, 201):
                    print(f"{GREEN}✅ Berhasil menambahkan karakter baru!{RESET}")
                    self.print_json("New Character Entity", res.json())
                else:
                    print(f"{RED}❌ Gagal membuat karakter: {res.text}{RESET}")

            elif sub_choice == "0":
                break

    def menu_system_settings_and_prompts(self):
        print(f"\n{BOLD}{CYAN}[ ⚙️ 9. System Settings & System Prompts ]{RESET}")
        print(f"  {GREEN}[1]{RESET} ⚙️ Lihat Global Settings (Max Concurrency & Defaults)")
        print(f"  {GREEN}[2]{RESET} 📝 Lihat Daftar System Prompts di Database")
        print(f"  {GREEN}[3]{RESET} ➕ Tambah System Prompt Baru")
        print(f"  {RED}[0]{RESET} 🔙 Kembali ke Menu Utama")

        choice = input(f"\n{BOLD}Pilihan Anda [0-3]: {RESET}").strip()
        if choice == "1":
            res = self.client.get(f"{self.api_v1}/settings")
            if res.status_code == 200:
                self.print_json("Global System Settings", res.json())
            else:
                print(f"{RED}Gagal mengambil settings: {res.text}{RESET}")

        elif choice == "2":
            res = self.client.get(f"{self.api_v1}/system-prompts")
            if res.status_code == 200:
                prompts = res.json()
                self.print_json("Database System Prompts", prompts)
            else:
                print(f"{RED}Gagal mengambil system prompts: {res.text}{RESET}")

        elif choice == "3":
            print(f"\n{BOLD}{CYAN}--- Tambah System Prompt Baru ---{RESET}")
            name = input(f"{BOLD}Nama Prompt Identifier (misal: 'fantasy_translator_v1'): {RESET}").strip()
            print(f"{BOLD}Masukkan Teks Prompt (Tekan Enter dua kali jika selesai):{RESET}")
            lines = []
            while True:
                line = input()
                if not line and lines:
                    break
                lines.append(line)
            prompt_text = "\n".join(lines).strip()
            is_def_str = input(f"{BOLD}Jadikan Default System Prompt Global? [y/N]: {RESET}").strip().lower()
            is_default = 1 if is_def_str == 'y' else 0

            if not name or not prompt_text:
                print(f"{RED}Nama dan teks prompt wajib diisi!{RESET}")
                return

            payload = {"name": name, "promptText": prompt_text, "isDefault": is_default}
            res = self.client.post(f"{self.api_v1}/system-prompts", json=payload)
            if res.status_code in (200, 201):
                print(f"{GREEN}✅ Berhasil menambahkan system prompt baru!{RESET}")
                self.print_json("New System Prompt", res.json())
            else:
                print(f"{RED}❌ Gagal menambahkan prompt: {res.text}{RESET}")

    def start_interactive_cli(self):
        self.print_banner()

        if not self.check_server():
            print(f"\n{RED}❌ Peringatan: Tidak dapat terhubung ke server API di {self.base_url}{RESET}")
            print(f"{YELLOW}Pastikan server FastAPI berjalan dengan `uv run uvicorn src.main:app --reload`{RESET}\n")

        while True:
            print(f"\n{BOLD}{CYAN}MENU UTAMA CLIENT APP:{RESET}")
            print(f"  {GREEN}[1]{RESET} 📁 Batch Import Series & Chapter dari HTML (via series.json)")
            print(f"  {GREEN}[2]{RESET} 🚀 Manual Input Form Translate Novel")
            print(f"  {GREEN}[3]{RESET} 🤖 Lihat Daftar LLM Models & Platforms")
            print(f"  {GREEN}[4]{RESET} 📚 Lihat Daftar & Detail Series (Termasuk Plot Summary Memory)")
            print(f"  {GREEN}[5]{RESET} 📊 Cek Status Async Background Jobs")
            print(f"  {GREEN}[6]{RESET} 📖 Lihat Chapter & Hasil Terjemahan")
            print(f"  {GREEN}[7]{RESET} 📡 Realtime Live WebSocket Monitor (Monitoring Backend Jobs)")
            print(f"  {GREEN}[8]{RESET} 🔖 Kelola Glosarium & Karakter Series")
            print(f"  {GREEN}[9]{RESET} ⚙️ Lihat System Settings & System Prompts")
            print(f"  {RED}[0]{RESET} ❌ Keluar / Exit")

            choice = input(f"\n{BOLD}Pilih Menu [0-9]: {RESET}").strip()

            if choice == "1":
                self.menu_import_config()
            elif choice == "2":
                self.menu_translate_novel_interactive()
            elif choice == "3":
                self.menu_list_models()
            elif choice == "4":
                self.menu_list_series()
            elif choice == "5":
                self.menu_check_jobs()
            elif choice == "6":
                self.menu_view_translated_chapters()
            elif choice == "7":
                self.menu_realtime_websocket_monitor()
            elif choice == "8":
                self.menu_manage_glossary_and_characters()
            elif choice == "9":
                self.menu_system_settings_and_prompts()
            elif choice == "0":
                print(f"\n{GREEN}Terima kasih telah menggunakan Novel Translation Client. Sampai jumpa!{RESET}\n")
                break
            else:
                print(f"{RED}Pilihan tidak valid. Silakan pilih 0-9.{RESET}")


def main():
    parser = argparse.ArgumentParser(description="Standalone Client Runner & Interactive CLI for Novel Translation API")
    parser.add_argument("config", nargs="?", help="Path ke file JSON config (misal: sample-scripts/series.json)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL API (default: http://localhost:8000)")
    args = parser.parse_args()

    runner = NovelTranslationRunner(base_url=args.base_url)

    # If config file path is passed as CLI argument, run directly
    if args.config:
        runner.print_banner()
        if not runner.check_server():
            print(f"{RED}Error: Server API di {args.base_url} offline.{RESET}")
            sys.exit(1)
        success = runner.process_config_file(args.config)
        sys.exit(0 if success else 1)
    else:
        # Otherwise start interactive CLI
        runner.start_interactive_cli()


if __name__ == "__main__":
    main()
