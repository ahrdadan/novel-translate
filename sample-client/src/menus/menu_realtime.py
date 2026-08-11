import time
import json
from ..utils import BOLD, CYAN, GREEN, RED, YELLOW, RESET, MAGENTA

def menu_realtime_websocket_monitor(api_client):
    print(f"\n{BOLD}{CYAN}[ 📡 7. Realtime Live WebSocket Monitor ]{RESET}")
    ws_url = api_client.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/v1/ws/jobs"
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
                    except Exception:
                        print(f"[{time.strftime('%H:%M:%S')}] {raw}")
        except Exception as e:
            print(f"\n{RED}Koneksi WebSocket terputus: {e}{RESET}")

    try:
        asyncio.run(listen_ws())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Berhenti memantau WebSocket.{RESET}")
