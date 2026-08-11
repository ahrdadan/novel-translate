from ..utils import BOLD, CYAN, GREEN, MAGENTA, RED, RESET, YELLOW


def menu_view_translated_chapters(api_client) -> None:
    print(f"\n{BOLD}{CYAN}[ 📖 6. Lihat Chapter & Hasil Terjemahan ]{RESET}")
    series_list = api_client.fetch_series()
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

    while True:
        chapters = api_client.fetch_chapters(series_id)
        if not chapters:
            print(f"{YELLOW}Belum ada chapter terdaftar untuk series '{series_name}'.{RESET}")
            break

        jobs = api_client.fetch_jobs(series_id=series_id)
        job_by_chap = {}
        for j in jobs:
            c_num = j.get("chapter_number")
            if c_num is not None and c_num not in job_by_chap:
                job_by_chap[c_num] = j

        print(f"\n{BOLD}{CYAN}Daftar Chapter untuk Series '{series_name}' (ID: {series_id}):{RESET}")
        for c in chapters:
            c_num = c.get("chapter_number")
            c_title = c.get("title") or f"Chapter {c_num}"
            status = c.get("status", "unknown")
            job_info = job_by_chap.get(c_num)

            if job_info and job_info.get("status") == "failed":
                status = "failed"

            status_color = GREEN if status in ("completed", "translated") else (YELLOW if status in ("processing", "queued", "pending") else RED)
            model_name = c.get("translated_by_model_name") or "-"
            
            queue_badge = ""
            if job_info and job_info.get("status") in ("queued", "processing") and job_info.get("queue_position"):
                queue_badge = f" {CYAN}(Antrean ke-{job_info.get('queue_position')} dari {job_info.get('total_in_queue')} total job){RESET}"

            err_summary = ""
            if status == "failed":
                err_text = c.get("error") or (job_info and job_info.get("error"))
                err_str = (str(err_text) if err_text else "").strip()
                if not err_str:
                    err_str = "Unknown"
                elif len(err_str) > 45:
                    err_str = err_str[:45] + "..."
                err_summary = f" {RED}(Error: {err_str}){RESET}"

            print(f"  [{c_num}] {c_title} | Status: {status_color}{status}{RESET} | Model: {model_name}{queue_badge}{err_summary}")

        print(f"\n{BOLD}Opsi Tambahan:{RESET}")
        print(f"  {YELLOW}[R] Retry SEMUA Chapter yang Failed di Series ini{RESET}")
        chap_choice = input(f"\n{BOLD}Masukkan Nomor Chapter / Opsi (Enter untuk kembali): {RESET}").strip()
        if not chap_choice:
            break

        if chap_choice.upper() == "R":
            failed_chaps = []
            for c in chapters:
                c_num = c.get("chapter_number")
                status = c.get("status", "unknown")
                job_info = job_by_chap.get(c_num)
                if job_info and job_info.get("status") == "failed":
                    status = "failed"
                if status == "failed":
                    failed_chaps.append(c_num)
            
            if not failed_chaps:
                print(f"{YELLOW}Tidak ada chapter yang failed di series ini.{RESET}")
            else:
                print(f"\n{BOLD}Pilih Mode Retry:{RESET}")
                print(f"  {GREEN}[D]{RESET} Default (Gunakan model bawaan series/global)")
                print(f"  {GREEN}[M]{RESET} Multi-Model (Distribusi ke beberapa model secara paralel)")
                mode_choice = input("Pilihan Anda [D/M]: ").strip().upper()

                model_ids = []
                if mode_choice == "M":
                    ids_input = input(f"{BOLD}Masukkan ID Model yang ingin dipakai (pisahkan dengan koma, misal: 1,4,5): {RESET}").strip()
                    for x in ids_input.split(","):
                        if x.strip().isdigit():
                            model_ids.append(int(x.strip()))
                    if not model_ids:
                        print(f"{YELLOW}Tidak ada ID Model valid. Menggunakan Default.{RESET}")

                print(f"\n{BOLD}{CYAN}Mengirim Request Retranslate untuk {len(failed_chaps)} chapter...{RESET}")
                for idx, c_num in enumerate(failed_chaps):
                    payload = {"mode": "async", "forceTranslate": True}
                    assigned_model_id = None
                    if model_ids:
                        assigned_model_id = model_ids[idx % len(model_ids)]
                        payload["translationModel"] = {"modelId": assigned_model_id}

                    try:
                        retry_res = api_client.post(
                            f"{api_client.api_v1}/series/{series_id}/chapters/{c_num}/retranslate",
                            json=payload
                        )
                        if retry_res.status_code in (200, 201, 202):
                            msg_model = f" dengan Model ID {assigned_model_id}" if assigned_model_id else ""
                            print(f"  {GREEN}✅ Ch #{c_num} di-retry{msg_model}!{RESET}")
                        else:
                            print(f"  {RED}❌ Ch #{c_num} gagal retry: {retry_res.text}{RESET}")
                    except Exception as e:  # noqa: BLE001
                        print(f"  {RED}Error koneksi pada Ch #{c_num}: {e}{RESET}")
            continue

        try:
            val = float(chap_choice)
            chap_num = int(val) if val.is_integer() else val
        except ValueError:
            print(f"{RED}Nomor chapter tidak valid.{RESET}")
            continue

        _show_chapter_detail(api_client, series_id, chap_num, job_by_chap)

def _show_chapter_detail(api_client, series_id: int, chap_num: float, job_by_chap: dict):
    detail = api_client.fetch_chapter_detail(series_id, chap_num)
    if not detail:
        print(f"{RED}Chapter {chap_num} tidak ditemukan untuk series ID {series_id}.{RESET}")
        return

    matching_job = job_by_chap.get(chap_num)
    if not matching_job:
        job_res = api_client.fetch_jobs(series_id=series_id, status=None)
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

    err_detail = detail.get("error") or (matching_job and matching_job.get("error"))
    if chap_status == "failed" and err_detail:
        print(f"\n{BOLD}{RED}❌ DETAIL ERROR PENYEBAB GAGAL:{RESET}")
        print(f"{RED}{err_detail}{RESET}")
    elif chap_status == "failed":
        print(f"\n{BOLD}{RED}❌ STATUS CHAPTER GAGAL (FAILED){RESET}")

    print(f"\n{BOLD}{CYAN}Pilih Konten Yang Ingin Dilihat:{RESET}")
    print(f"  {GREEN}[1]{RESET} 📖 Hasil Terjemahan Saja (Translated Text)")
    print(f"  {GREEN}[2]{RESET} 📝 Ringkasan Chapter Saja (Chapter Summary)")
    print(f"  {GREEN}[3]{RESET} 📄 Teks Sumber Saja (Original Source Text)")
    print(f"  {GREEN}[4]{RESET} 📊 Lihat Semua Detail (Metadata + Summary + Terjemahan) [Default]")
    print(f"  {GREEN}[R]{RESET} 🔄 Retranslate / Retry Chapter Ini (Proses Ulang)")
    print(f"  {RED}[Enter]{RESET} 🔙 Kembali ke Daftar Chapter")

    view_mode = input(f"\n{BOLD}Pilihan Tampilan [1-4 / R / Enter] (Default: 4): {RESET}").strip().upper()

    if view_mode == "R":
        print(f"\n{BOLD}{CYAN}Mengirim Request Retranslate untuk Chapter #{chap_num}...{RESET}")
        try:
            retry_res = api_client.post(
                f"{api_client.api_v1}/series/{series_id}/chapters/{chap_num}/retranslate",
                json={"mode": "async", "forceTranslate": True}
            )
            if retry_res.status_code in (200, 201, 202):
                res_data = retry_res.json()
                job_id = res_data.get("job_id") or res_data.get("id")
                print(f"{GREEN}✅ Berhasil mengirim request Retry! Job ID: #{job_id}{RESET}")
            else:
                print(f"{RED}❌ Gagal Request Retry [{retry_res.status_code}]: {retry_res.text}{RESET}")
        except Exception as e:  # noqa: BLE001
            print(f"{RED}Error koneksi: {e}{RESET}")
        return

    if not view_mode:
        view_mode = "4"
        
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

    elif view_mode == "4":
        if detail.get("chapter_summary"):
            print(f"\n{BOLD}{YELLOW}--- Ringkasan Chapter (Summary) ---{RESET}")
            print(detail.get("chapter_summary"))

        translated = detail.get("translated_text")
        if translated:
            print(f"\n{BOLD}{GREEN}--- Hasil Terjemahan (Translated Text) ---{RESET}")
            print(translated)
        else:
            print(f"\n{YELLOW}⚠️ Teks terjemahan belum tersedia. (Status: {chap_status}){RESET}")
