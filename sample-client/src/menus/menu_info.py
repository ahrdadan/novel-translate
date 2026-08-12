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
            "id": p.get("id"),
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
    print("  [AP]  Add Platform (via JSON)")
    print("  [DP]  Delete Platform")
    print("  [DM]  Delete Model")
    print("  [Enter] Kembali")

    user_act = input(f"\n{BOLD}Pilihan Anda [P / AP / DP / DM / Enter]: {RESET}").strip()
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
    elif user_act.upper() == "AP":
        print(f"\n{BOLD}Masukkan JSON konfigurasi platform (Bisa berupa object/array).")
        print(f"Ketik 'EOF' di baris baru lalu Enter untuk selesai:{RESET}")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "EOF":
                    break
                lines.append(line)
            except EOFError:
                break
        
        json_str = "\n".join(lines).strip()
        if not json_str:
            print(f"{YELLOW}Input kosong, dibatalkan.{RESET}")
            return

        # Try to parse
        json_str = json_str.removesuffix(",")
        
        import json
        data = None
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # Attempt to wrap with braces in case user copied '"platform": {...}'
                data = json.loads(f"{{{json_str}}}")
            except json.JSONDecodeError as e:
                print(f"{RED}Error: JSON tidak valid. Pastikan format benar. ({e}){RESET}")
                return

        def create_platform(p_data):
            res = api_client.post(f"{api_client.api_v1}/platforms", json=p_data)
            if res.status_code == 201:
                p = res.json()
                print(f"{GREEN}✅ Platform '{p.get('name')}' berhasil ditambahkan (ID: {p.get('id')}).{RESET}")
            else:
                print(f"{RED}❌ Gagal menambahkan platform '{p_data.get('name')}'. [{res.status_code}]: {res.text}{RESET}")

        if isinstance(data, list):
            for item in data:
                if "platform" in item and isinstance(item["platform"], dict):
                    create_platform(item["platform"])
                else:
                    create_platform(item)
        elif isinstance(data, dict):
            # Check if it's wrapped in {"platform": ...} or {"translationModel": {"platform": ...}}
            if "translationModel" in data and isinstance(data["translationModel"], dict):
                data = data["translationModel"]
            if "platform" in data and isinstance(data["platform"], dict):
                data = data["platform"]
            create_platform(data)
        else:
            print(f"{RED}Error: Format data tidak dikenali. Harus berupa object atau array.{RESET}")

    elif user_act.upper() == "DP":
        p_id = input(f"{BOLD}Masukkan ID Platform yang akan dihapus: {RESET}").strip()
        if p_id.isdigit():
            confirm = input(f"{YELLOW}Yakin ingin menghapus Platform ID {p_id} beserta semua modelnya? (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                res = api_client.delete(f"{api_client.api_v1}/platforms/{p_id}")
                if res.status_code == 204:
                    print(f"{GREEN}✅ Platform ID {p_id} berhasil dihapus.{RESET}")
                else:
                    print(f"{RED}❌ Gagal menghapus Platform ID {p_id}. [{res.status_code}]: {res.text}{RESET}")
    elif user_act.upper() == "DM":
        p_id = input(f"{BOLD}Masukkan ID Platform dari model tersebut: {RESET}").strip()
        m_id = input(f"{BOLD}Masukkan ID Model yang akan dihapus: {RESET}").strip()
        if p_id.isdigit() and m_id.isdigit():
            confirm = input(f"{YELLOW}Yakin ingin menghapus Model ID {m_id} di Platform ID {p_id}? (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                res = api_client.delete(f"{api_client.api_v1}/platforms/{p_id}/models/{m_id}")
                if res.status_code == 204:
                    print(f"{GREEN}✅ Model ID {m_id} berhasil dihapus.{RESET}")
                else:
                    print(f"{RED}❌ Gagal menghapus Model ID {m_id}. [{res.status_code}]: {res.text}{RESET}")

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
