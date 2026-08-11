from ..utils import BOLD, CYAN, GREEN, MAGENTA, RED, RESET, YELLOW, print_json


def menu_list_models(api_client) -> None:
    print(f"\n{BOLD}{CYAN}[ 🤖 3. Platforms & Models List ]{RESET}")
    platforms = api_client.fetch_platforms()
    if not platforms:
        print_json("Registered Platforms", "Tidak ada platform terdaftar.")
        return

    # Refine output format for platforms to display models nicely
    formatted_output = []
    for p in platforms:
        platform_data = {
            "name": p.get("name"),
            "apiKey": p.get("api_key"),
            "apiType": p.get("api_type"),
            "models": [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "url": m.get("url")
                } for m in p.get("models", [])
            ]
        }
        formatted_output.append(platform_data)
        
    print_json("Registered Platforms & Models", formatted_output)

    print(f"\n{BOLD}Pilihan Aksi:{RESET}")
    print("  [P]   Ping / Test Model Endpoint (Check Streaming)")
    print("  [Enter] Kembali")

    user_act = input(f"\n{BOLD}Pilihan Anda [P / Enter]: {RESET}").strip()
    if user_act.upper() == "P":
        m_id = input(f"{BOLD}Masukkan ID Model untuk di-test: {RESET}").strip()
        if m_id.isdigit():
            print(f"\n{YELLOW}Menjalankan Ping Test untuk Model ID {m_id}...{RESET}")
            try:
                # Normal ping
                res_ping = api_client.post(f"{api_client.api_v1}/models/{m_id}/ping")
                if res_ping.status_code == 200:
                    print(f"{GREEN}✅ Normal Ping Success!{RESET}")
                    print_json("Ping Response", res_ping.json())
                else:
                    print(f"{RED}❌ Ping Failed! [{res_ping.status_code}]: {res_ping.text}{RESET}")

                print(f"\n{YELLOW}Menjalankan Streaming Test untuk Model ID {m_id}...{RESET}")
                res_stream = api_client.post(f"{api_client.api_v1}/models/{m_id}/check-streaming")
                if res_stream.status_code == 200:
                    print(f"{GREEN}✅ Streaming Test Success!{RESET}")
                    print_json("Streaming Response", res_stream.json())
                else:
                    print(f"{RED}❌ Streaming Test Failed! [{res_stream.status_code}]: {res_stream.text}{RESET}")

            except Exception as e:  # noqa: BLE001
                print(f"{RED}Error koneksi: {e}{RESET}\n")

def menu_list_series(api_client) -> None:
    print(f"\n{BOLD}{CYAN}[ 📚 4. Daftar & Detail Series (Termasuk Plot Summary Memory) ]{RESET}")
    series_list = api_client.fetch_series()
    if not series_list:
        print(f"{YELLOW}Belum ada series terdaftar di database.{RESET}")
        return

    print_json("Series List", series_list)

    s_id_input = input(f"\n{BOLD}Masukkan ID Series untuk melihat Detail Lengkap & Cumulative Plot Summary (Enter untuk kembali): {RESET}").strip()
    if s_id_input.isdigit():
        res = api_client.get(f"{api_client.api_v1}/series/{s_id_input}")
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
