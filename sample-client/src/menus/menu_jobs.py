from ..utils import BOLD, CYAN, GREEN, RED, YELLOW, RESET

def menu_check_jobs(api_client) -> None:
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

    jobs = api_client.fetch_jobs(status=status_filter)
    # Exclude jobs cancelled by user
    if jobs:
        jobs = [j for j in jobs if j.get("error") != "Cancelled by user"]

    if jobs:
        processing = [j for j in jobs if j.get("status") == "processing"]
        queued = [j for j in jobs if j.get("status") == "queued"]
        failed = [j for j in jobs if j.get("status") == "failed"]
        completed = [j for j in jobs if j.get("status") == "completed"]

        print(f"\n{BOLD}{CYAN}=== DAFTAR JOB AKTIF ==={RESET}")
        if processing:
            print(f"\n{BOLD}{GREEN}▶ SEDANG BERJALAN (PROCESSING):{RESET}")
            for j in processing:
                print(f"  - Job #{j['id']} | Series #{j['series_id']} Ch #{j['chapter_number']} | Retry: {j.get('retry_count',0)}")
        
        if queued:
            print(f"\n{BOLD}{YELLOW}⏳ DALAM ANTREAN (QUEUED):{RESET}")
            for j in queued:
                print(f"  - Job #{j['id']} | Series #{j['series_id']} Ch #{j['chapter_number']} | Posisi: {j.get('queue_position', '-')}")
        
        if failed:
            print(f"\n{BOLD}{RED}❌ GAGAL (FAILED):{RESET}")
            for j in failed:
                print(f"  - Job #{j['id']} | Series #{j['series_id']} Ch #{j['chapter_number']} | Error: {str(j.get('error'))[:50]}...")

        if completed:
            print(f"\n{BOLD}{GREEN}✅ SELESAI (COMPLETED):{RESET}")
            for j in completed:
                print(f"  - Job #{j['id']} | Series #{j['series_id']} Ch #{j['chapter_number']}")

        print(f"\n{BOLD}Total Ditampilkan: {len(jobs)} Job (Mengecualikan yang di-cancel user){RESET}")

        print(f"\n{BOLD}Pilihan Aksi:{RESET}")
        print("  [ID]  Masukkan Job ID untuk detail status")
        print("  [R]   Retry / Retranslate Job Gagal")
        print("  [C]   Cancel Semua Job yang Sedang Berjalan / Antrean")
        print("  [Enter] Kembali")

        user_act = input(f"\n{BOLD}Pilihan Anda [Job ID / R / C / Enter]: {RESET}").strip()
        if user_act.isdigit():
            j_res = api_client.get(f"{api_client.api_v1}/jobs/{user_act}")
            if j_res.status_code == 200:
                from ..utils import print_json
                print_json(f"Job #{user_act} Detail", j_res.json())
            else:
                print(f"{RED}Job tidak ditemukan.{RESET}")
        elif user_act.upper() == "R":
            retry_job_id = input(f"{BOLD}Masukkan ID Job Gagal yang ingin di-retry: {RESET}").strip()
            if retry_job_id.isdigit():
                try:
                    r_res = api_client.post(f"{api_client.api_v1}/jobs/{retry_job_id}/retry")
                    if r_res.status_code == 200:
                        print(f"{GREEN}✅ Job #{retry_job_id} berhasil di-retry & masuk ke antrean!{RESET}")
                        print(f"{YELLOW}Buka Menu [7] Realtime Monitor untuk memantau pengerjaan.{RESET}\n")
                    else:
                        print(f"{RED}❌ Gagal retry Job #{retry_job_id} [{r_res.status_code}]: {r_res.text}{RESET}\n")
                except Exception as e:
                    print(f"{RED}Error koneksi: {e}{RESET}\n")
        elif user_act.upper() == "C":
            confirm = input(f"{BOLD}{YELLOW}Yakin ingin membatalkan semua job yang queued/processing? [y/N]: {RESET}").strip().lower()
            if confirm == 'y':
                try:
                    c_res = api_client.post(f"{api_client.api_v1}/jobs/cancel-all")
                    if c_res.status_code == 200:
                        data = c_res.json()
                        count = data.get("cancelled_count", 0)
                        if count > 0:
                            print(f"\n{GREEN}✅ Selesai membatalkan {count} job secara massal.{RESET}\n")
                        else:
                            print(f"\n{YELLOW}Tidak ada job yang sedang berjalan/antre untuk dibatalkan.{RESET}\n")
                    else:
                        print(f"{RED}❌ Gagal membatalkan job: {c_res.text}{RESET}")
                except Exception as e:
                    print(f"{RED}Error koneksi: {e}{RESET}\n")
    else:
        print(f"{YELLOW}Tidak ada background job yang cocok dengan filter ({status_filter or 'semua'}).{RESET}")
