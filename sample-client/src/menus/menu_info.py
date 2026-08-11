from ..utils import BOLD, CYAN, GREEN, RED, YELLOW, RESET, MAGENTA, print_json

def menu_list_models(api_client) -> None:
    print(f"\n{BOLD}{CYAN}[ 🤖 3. Models & Platforms List ]{RESET}")
    models = api_client.fetch_models()
    print_json("Registered Models", models if models else "Tidak ada model terdaftar.")

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
