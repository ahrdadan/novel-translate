import sys
from .api_client import APIClient
from .utils import print_banner, BOLD, CYAN, GREEN, RED, YELLOW, RESET
from .menus.menu_import import menu_import_config, menu_translate_novel_interactive
from .menus.menu_info import menu_list_models, menu_list_series
from .menus.menu_jobs import menu_check_jobs
from .menus.menu_chapters import menu_view_translated_chapters
from .menus.menu_realtime import menu_realtime_websocket_monitor
from .menus.menu_settings import menu_view_settings
from .menus.menu_backup import menu_database_backup

class NovelTranslatorCLI:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.api_client = APIClient(base_url)

    def check_server(self) -> bool:
        return self.api_client.check_server()
        
    def print_banner(self):
        print_banner(self.api_client.base_url)

    def run_interactive(self):
        if not self.check_server():
            print(f"{RED}Error: Tidak bisa terhubung ke server backend di {self.api_client.base_url}{RESET}")
            print(f"{YELLOW}Pastikan server FastAPI sudah berjalan (uv run uvicorn src.main:app){RESET}")
            sys.exit(1)

        self.print_banner()
        while True:
            print(f"\n{BOLD}{CYAN}=== MAIN MENU ==={RESET}")
            print(f"  {GREEN}[1]{RESET} Import Config (TOC JSON / Folder HTML)")
            print(f"  {GREEN}[2]{RESET} Manual Translate Chapter (Interactive Input)")
            print(f"  {GREEN}[3]{RESET} Lihat Daftar Model & Platform")
            print(f"  {GREEN}[4]{RESET} Lihat Daftar Series & Plot Summary")
            print(f"  {GREEN}[5]{RESET} Cek Status Background Jobs & Antrean")
            print(f"  {GREEN}[6]{RESET} Lihat Hasil Chapter Terjemahan")
            print(f"  {GREEN}[7]{RESET} Real-time Live Monitor (WebSocket)")
            print(f"  {GREEN}[9]{RESET} System Settings (Global Config)")
            print(f"  {GREEN}[10]{RESET} Database Backup & Restore")
            print(f"  {RED}[0]{RESET} Keluar")

            choice = input(f"\n{BOLD}Pilih menu [0-10]: {RESET}").strip()

            if choice == "1":
                menu_import_config(self.api_client)
            elif choice == "2":
                menu_translate_novel_interactive(self.api_client)
            elif choice == "3":
                menu_list_models(self.api_client)
            elif choice == "4":
                menu_list_series(self.api_client)
            elif choice == "5":
                menu_check_jobs(self.api_client)
            elif choice == "6":
                menu_view_translated_chapters(self.api_client)
            elif choice == "7":
                menu_realtime_websocket_monitor(self.api_client)
            elif choice == "9":
                menu_view_settings(self.api_client)
            elif choice == "10":
                menu_database_backup(self.api_client)
            elif choice == "0":
                print(f"{GREEN}Keluar dari CLI. Sampai jumpa!{RESET}")
                break
            else:
                print(f"{RED}Pilihan tidak valid.{RESET}")

    def run_batch_file(self, config_path: str):
        if not self.check_server():
            print(f"{RED}Error: Tidak bisa terhubung ke server di {self.api_client.base_url}{RESET}")
            sys.exit(1)
            
        from .menus.menu_import import process_config_file
        process_config_file(self.api_client, config_path)
