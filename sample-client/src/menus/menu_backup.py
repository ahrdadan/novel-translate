import re
from datetime import UTC, datetime
from pathlib import Path

from ..utils import BOLD, CYAN, GREEN, RED, RESET, YELLOW


def menu_database_backup(api_client) -> None:
    while True:
        print(f"\n{BOLD}{CYAN}=== DATABASE BACKUP & RESTORE ==={RESET}")
        print(f"  {YELLOW}Catatan: Fitur ini akan mendownload/merestore snapshot dari server backend ({api_client.base_url}){RESET}")
        
        backup_dir = Path("backup")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        snapshots = sorted(backup_dir.glob("*.zip"), reverse=True)
        
        print(f"\n{BOLD}Snapshots Tersedia:{RESET}")
        if not snapshots:
            print("  (Tidak ada snapshot ZIP)")
        else:
            for i, snap in enumerate(snapshots):
                size_kb = snap.stat().st_size / 1024
                print(f"  {GREEN}[{i+1}]{RESET} {snap.name} ({size_kb:.1f} KB)")
                
        print(f"\n{BOLD}Pilihan Aksi:{RESET}")
        print("  [B] Buat Backup (Snapshot) Baru dari Server")
        print("  [R] Restore Database ke Server dari Snapshot")
        print("  [Enter] Kembali ke Menu Utama")
        
        user_input = input(f"\n{BOLD}Pilihan Anda [B / R / Enter]: {RESET}").strip().upper()
        
        if not user_input:
            break
            
        if user_input == 'B':
            try:
                print(f"\n{CYAN}Meminta snapshot zip dari server...{RESET}")
                res = api_client.get(f"{api_client.api_v1}/snapshots/export", params={"format": "zip"})
                
                if res.status_code == 200:
                    # Parse filename from Content-Disposition if available, or generate one
                    cd = res.headers.get('content-disposition', '')
                    match = re.search(r'filename="(.+?)"', cd)
                    if match:
                        filename = match.group(1)
                    else:
                        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                        filename = f"snapshot_{timestamp}.zip"
                        
                    backup_path = backup_dir / filename
                    with open(backup_path, "wb") as f:
                        f.write(res.content)
                    
                    print(f"{BOLD}{GREEN}✅ Backup berhasil didownload dan disimpan ke: {backup_path}{RESET}")
                else:
                    print(f"{BOLD}{RED}❌ Gagal membuat backup (Status {res.status_code}): {res.text}{RESET}")
            except Exception as e:  # noqa: BLE001
                print(f"{BOLD}{RED}❌ Error saat membuat backup: {e}{RESET}")
                
        elif user_input == 'R':
            if not snapshots:
                print(f"{RED}Tidak ada snapshot ZIP yang bisa di-restore.{RESET}")
                continue
                
            idx_str = input(f"Masukkan nomor snapshot yang ingin di-restore [1-{len(snapshots)}]: ").strip()
            if not idx_str.isdigit() or not (1 <= int(idx_str) <= len(snapshots)):
                print(f"{RED}Nomor tidak valid.{RESET}")
                continue
                
            selected_snap = snapshots[int(idx_str) - 1]
            
            print(f"\n{BOLD}{RED}⚠️  PERINGATAN KRITIS ⚠️{RESET}")
            print(f"{YELLOW}Proses restore akan MENIMPA database utama di server backend saat ini!{RESET}")
            
            confirm = input("Apakah Anda yakin ingin restore snapshot ini ke server? (ketik 'YA' untuk lanjut): ").strip()
            if confirm == "YA":
                try:
                    print(f"\n{CYAN}Mengupload snapshot {selected_snap.name} ke server...{RESET}")
                    with open(selected_snap, "rb") as f:
                        files = {"file": (selected_snap.name, f, "application/zip")}
                        res = api_client.post(f"{api_client.api_v1}/snapshots/restore", files=files)
                        
                    if res.status_code == 200:
                        data = res.json()
                        print(f"{BOLD}{GREEN}✅ Restore berhasil! Pesan server: {data.get('message', '')}{RESET}")
                    else:
                        print(f"{BOLD}{RED}❌ Gagal me-restore database (Status {res.status_code}): {res.text}{RESET}")
                except Exception as e:  # noqa: BLE001
                    print(f"{BOLD}{RED}❌ Error saat me-restore database: {e}{RESET}")
            else:
                print("Restore dibatalkan.")
