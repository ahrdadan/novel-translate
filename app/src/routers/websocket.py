"""WebSocket router — GET /ws/jobs for real-time background job monitoring."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.repositories import job_repo
from src.services.ws_manager import ws_manager

router = APIRouter(tags=["jobs"])


@router.websocket("/ws/jobs")
async def websocket_jobs_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time monitoring of translation job execution."""
    await ws_manager.connect(websocket)
    try:
        # Send welcome & initial status summary
        unfinished_jobs = await job_repo.list_jobs(status="queued,processing,failed", limit=20)
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to Novel Translation Real-time Monitor",
            "active_jobs_count": len(unfinished_jobs),
            "jobs": unfinished_jobs,
        })

        # Keep connection open and receive optional ping messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        ws_manager.disconnect(websocket)
