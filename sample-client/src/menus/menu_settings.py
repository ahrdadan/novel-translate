from ..utils import BOLD, CYAN, GREEN, RED, RESET, YELLOW


def menu_view_settings(api_client) -> None:
    while True:
        try:
            res = api_client.get(f"{api_client.api_v1}/settings")
            if res.status_code == 200:
                settings = res.json()
                print(f"\n{BOLD}{CYAN}=== SYSTEM SETTINGS ==={RESET}")
                
                # Check Pause status
                is_paused = settings.get("is_paused", 0)
                status_text = f"{RED}PAUSED{RESET}" if is_paused else f"{GREEN}ACTIVE{RESET}"
                
                print(f"  Max Concurrent Jobs : {BOLD}{YELLOW}{settings.get('max_concurrent_jobs')}{RESET}")
                print(f"  System Status       : {BOLD}{status_text}")
                print(f"  Default Trans Model : {settings.get('default_translation_model_id')}")
                print(f"  Default Extr Model  : {settings.get('default_extraction_model_id')}")
                print(f"  Default Prompt ID   : {settings.get('default_system_prompt_id')}")
                print(f"  Last Updated        : {settings.get('updated_at')}")
                
                print(f"\n{BOLD}Pilihan Aksi:{RESET}")
                print("  [C] Ubah Max Concurrent Jobs (Concurrency)")
                if is_paused:
                    print("  [R] Resume System (Unpause)")
                else:
                    print("  [P] Pause System (Hentikan eksekusi antrean)")
                print("  [M] Ubah Default Translation Model ID")
                print("  [Enter] Kembali ke Menu Utama")
                
                user_input = input(f"\n{BOLD}Pilihan Anda: {RESET}").strip().upper()
                
                if not user_input:
                    break
                    
                if user_input == 'C':
                    new_val = input("Masukkan jumlah max concurrent jobs baru [1-10]: ").strip()
                    if new_val.isdigit() and 1 <= int(new_val) <= 10:
                        patch_res = api_client.patch(f"{api_client.api_v1}/settings", json={"max_concurrent_jobs": int(new_val)})
                        if patch_res.status_code == 200:
                            print(f"{GREEN}✅ Berhasil mengubah Max Concurrent Jobs menjadi {new_val}{RESET}")
                        else:
                            print(f"{RED}❌ Gagal mengubah: {patch_res.text}{RESET}")
                    else:
                        print(f"{RED}Input tidak valid.{RESET}")
                        
                elif user_input == 'P' and not is_paused:
                    patch_res = api_client.patch(f"{api_client.api_v1}/settings", json={"is_paused": 1})
                    if patch_res.status_code == 200:
                        print(f"{GREEN}✅ System berhasil di-pause.{RESET}")
                    else:
                        print(f"{RED}❌ Gagal mempause system: {patch_res.text}{RESET}")
                        
                elif user_input == 'R' and is_paused:
                    patch_res = api_client.patch(f"{api_client.api_v1}/settings", json={"is_paused": 0})
                    if patch_res.status_code == 200:
                        print(f"{GREEN}✅ System berhasil di-resume.{RESET}")
                    else:
                        print(f"{RED}❌ Gagal me-resume system: {patch_res.text}{RESET}")
                        
                elif user_input == 'M':
                    new_val = input("Masukkan ID Model Default (angka, kosongkan untuk batal): ").strip()
                    if new_val.isdigit():
                        patch_res = api_client.patch(f"{api_client.api_v1}/settings", json={"default_translation_model_id": int(new_val)})
                        if patch_res.status_code == 200:
                            print(f"{GREEN}✅ Berhasil mengubah Default Translation Model ID menjadi {new_val}{RESET}")
                        else:
                            print(f"{RED}❌ Gagal mengubah: {patch_res.text}{RESET}")
                    else:
                        print(f"{YELLOW}Dibatalkan.{RESET}")
            else:
                print(f"{RED}Gagal mengambil settings: {res.text}{RESET}")
                break
        except Exception as e:  # noqa: BLE001
            print(f"{RED}Error: {e}{RESET}")
            break
