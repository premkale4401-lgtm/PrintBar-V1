"""
PrintBar Backend — Kiosk WebSocket Endpoint

ws://backend/ws/kiosk/{kiosk_id}?api_key=<raw_key>

The Raspberry Pi kiosk connects here on startup and maintains the connection.
Messages are JSON with type and data fields.

Authentication:
    The kiosk passes its raw API key as a query parameter.
    The backend hashes it and compares to the stored hash.
    No JWT — kiosks use API keys.

Message handling:
    HEARTBEAT  → update DB metrics, log heartbeat
    JOB_STATUS → transition print job status
    JOB_COMPLETED → mark job COMPLETED, delete file from storage
    JOB_FAILED → mark job FAILED
    PONG → keepalive acknowledgement
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import AsyncSessionFactory
from app.models.kiosk import Kiosk
from app.repositories.kiosk_repository import KioskRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.storage.service import storage_service
from app.websocket.manager import ws_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])
settings = get_settings()


async def _authenticate_kiosk(
    kiosk_id: str,
    api_key: str,
    db: AsyncSession,
) -> Kiosk | None:
    """
    Authenticates a kiosk by hashing the provided API key and comparing.

    Returns:
        Kiosk instance if authenticated, None otherwise.
    """
    repo = KioskRepository(db)
    key_hash = KioskRepository.hash_api_key(api_key)
    kiosk = await repo.get_by_api_key_hash(key_hash)

    if kiosk is None:
        return None

    # Ensure the kiosk_id in the URL matches the kiosk for the key.
    try:
        if kiosk.id != uuid.UUID(kiosk_id):
            return None
    except ValueError:
        return None

    return kiosk


@router.websocket("/kiosk/{kiosk_id}")
async def kiosk_websocket(
    websocket: WebSocket,
    kiosk_id: str,
    api_key: str = Query(..., description="Raw kiosk API key"),
) -> None:
    """
    WebSocket endpoint for Raspberry Pi kiosk connections.

    Lifecycle:
        1. Authenticate API key.
        2. Accept connection and register with ws_manager.
        3. Update kiosk status to ONLINE in DB.
        4. Process incoming messages in loop.
        5. On disconnect: mark kiosk OFFLINE.
    """
    async with AsyncSessionFactory() as db:
        async with db.begin():
            kiosk = await _authenticate_kiosk(kiosk_id, api_key, db)

        if not kiosk:
            logger.warning("ws_auth_failed", kiosk_id=kiosk_id)
            await websocket.close(code=4001, reason="Authentication failed")
            return

        kiosk_uuid = kiosk.id

    # Accept and register connection.
    await ws_manager.connect(kiosk_id, websocket)

    # Update DB: kiosk is now online.
    async with AsyncSessionFactory() as db:
        async with db.begin():
            repo = KioskRepository(db)
            await repo.set_ws_connected(kiosk_uuid, True)

    logger.info("ws_kiosk_authenticated", kiosk_id=kiosk_id, kiosk_name=kiosk.name)

    # Send welcome message.
    await ws_manager.send_to_kiosk(kiosk_id, "CONNECTED", {
        "kioskId": kiosk_id,
        "message": "Connected to PrintBar backend",
        "serverTime": datetime.now(tz=UTC).isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("ws_invalid_json", kiosk_id=kiosk_id)
                continue

            msg_type = message.get("type", "")
            data = message.get("data", {})

            await _handle_message(kiosk_id, kiosk_uuid, msg_type, data)

    except WebSocketDisconnect:
        logger.info("ws_kiosk_disconnected_cleanly", kiosk_id=kiosk_id)
    except Exception as exc:
        logger.exception("ws_error", kiosk_id=kiosk_id, error=str(exc))
    finally:
        await ws_manager.disconnect(kiosk_id)
        async with AsyncSessionFactory() as db:
            async with db.begin():
                repo = KioskRepository(db)
                await repo.set_ws_connected(kiosk_uuid, False)


async def _handle_message(
    kiosk_id: str,
    kiosk_uuid: uuid.UUID,
    msg_type: str,
    data: dict,
) -> None:
    """Dispatches incoming WebSocket messages to the appropriate handler."""
    ws_manager.update_heartbeat(kiosk_id)

    async with AsyncSessionFactory() as db:
        async with db.begin():
            if msg_type == "HEARTBEAT":
                await _handle_heartbeat(kiosk_id, kiosk_uuid, data, db)
            elif msg_type == "JOB_STATUS":
                await _handle_job_status(kiosk_id, data, db)
            elif msg_type == "JOB_COMPLETED":
                await _handle_job_completed(kiosk_id, data, db)
            elif msg_type == "JOB_FAILED":
                await _handle_job_failed(kiosk_id, data, db)
            elif msg_type == "DOWNLOAD_URL_REQUEST":
                await _handle_download_url_request(kiosk_id, data, db)
            elif msg_type == "PONG":
                pass  # Keepalive — no action needed.
            else:
                logger.warning("ws_unknown_message_type", kiosk_id=kiosk_id, type=msg_type)


async def _handle_heartbeat(
    kiosk_id: str,
    kiosk_uuid: uuid.UUID,
    data: dict,
    db: AsyncSession,
) -> None:
    """Updates kiosk health metrics and logs the heartbeat."""
    repo = KioskRepository(db)
    await repo.update_heartbeat(
        kiosk_uuid,
        status="PRINTING" if data.get("printing") else "ONLINE",
        app_version=data.get("appVersion"),
        cpu_percent=data.get("cpuPercent"),
        ram_percent=data.get("ramPercent"),
        disk_percent=data.get("diskPercent"),
        temperature_c=data.get("temperatureC"),
        printer_status=data.get("printerStatus"),
    )
    await repo.log_heartbeat(kiosk_uuid, data)

    logger.debug("ws_heartbeat", kiosk_id=kiosk_id)


async def _handle_job_status(
    kiosk_id: str,
    data: dict,
    db: AsyncSession,
) -> None:
    """Handles intermediate job status updates from the kiosk."""
    job_id_str = data.get("jobId")
    new_status = data.get("status")

    if not job_id_str or not new_status:
        return

    try:
        job_uuid = uuid.UUID(job_id_str)
    except ValueError:
        return

    repo = PrintJobRepository(db)
    try:
        await repo.transition(job_uuid, new_status)
        logger.info("ws_job_status_update", job_id=job_id_str, status=new_status)
    except Exception as exc:
        logger.warning("ws_job_transition_failed", job_id=job_id_str, error=str(exc))


async def _handle_job_completed(
    kiosk_id: str,
    data: dict,
    db: AsyncSession,
) -> None:
    """Marks a job as COMPLETED and triggers file deletion."""
    job_id_str = data.get("jobId")
    if not job_id_str:
        return

    try:
        job_uuid = uuid.UUID(job_id_str)
    except ValueError:
        return

    job_repo = PrintJobRepository(db)
    file_repo = UploadedFileRepository(db)

    job = await job_repo.get_by_id(job_uuid)
    if not job:
        return

    await job_repo.mark_completed(job_uuid)

    # Privacy: delete the file from storage and null PII.
    if job.uploaded_file_id:
        uploaded_file = await file_repo.get_by_id(job.uploaded_file_id)
        if uploaded_file and not uploaded_file.is_deleted and uploaded_file.storage_path:
            await storage_service.delete_file(
                bucket=uploaded_file.storage_bucket,
                object_path=uploaded_file.storage_path,
            )
            await file_repo.mark_deleted(job.uploaded_file_id)

    from app.core.metrics import PRINT_JOB_DURATION
    if job.created_at:
        duration = (datetime.now(tz=UTC) - job.created_at).total_seconds()
        PRINT_JOB_DURATION.observe(duration)

    logger.info("ws_job_completed", job_id=job_id_str, kiosk_id=kiosk_id)


async def _handle_job_failed(
    kiosk_id: str,
    data: dict,
    db: AsyncSession,
) -> None:
    """Marks a job as FAILED."""
    job_id_str = data.get("jobId")
    reason = data.get("reason", "KIOSK_ERROR")

    if not job_id_str:
        return

    try:
        job_uuid = uuid.UUID(job_id_str)
    except ValueError:
        return

    repo = PrintJobRepository(db)
    try:
        await repo.mark_failed(job_uuid, reason)
        logger.info("ws_job_failed", job_id=job_id_str, reason=reason)
        
        from app.core.metrics import PRINT_JOBS_FAILED
        PRINT_JOBS_FAILED.inc()
    except Exception as exc:
        logger.warning("ws_job_fail_error", error=str(exc))


async def _handle_download_url_request(
    kiosk_id: str,
    data: dict,
    db: AsyncSession,
) -> None:
    """
    Generates a signed Supabase URL for the kiosk to download a print file.

    The kiosk requests a download URL after receiving a JOB_ASSIGNED message.
    The URL expires in settings.SIGNED_URL_EXPIRY_SECONDS.
    """
    job_id_str = data.get("jobId")
    if not job_id_str:
        return

    try:
        job_uuid = uuid.UUID(job_id_str)
    except ValueError:
        return

    job_repo = PrintJobRepository(db)
    file_repo = UploadedFileRepository(db)

    job = await job_repo.get_by_id(job_uuid)
    if not job:
        await ws_manager.send_to_kiosk(kiosk_id, "DOWNLOAD_URL_ERROR", {
            "jobId": job_id_str, "error": "JOB_NOT_FOUND"
        })
        return

    if not job.uploaded_file_id:
        return

    uploaded_file = await file_repo.get_by_id(job.uploaded_file_id)
    if not uploaded_file or uploaded_file.is_deleted or not uploaded_file.storage_path:
        await ws_manager.send_to_kiosk(kiosk_id, "DOWNLOAD_URL_ERROR", {
            "jobId": job_id_str, "error": "FILE_NOT_FOUND"
        })
        return

    # Transition job to DOWNLOADING.
    try:
        await job_repo.transition(job_uuid, "DOWNLOADING")
    except Exception:
        pass

    try:
        signed_url = await storage_service.create_signed_url(
            bucket=uploaded_file.storage_bucket,
            object_path=uploaded_file.storage_path,
        )
        await ws_manager.send_to_kiosk(kiosk_id, "DOWNLOAD_URL", {
            "jobId": job_id_str,
            "url": signed_url,
            "sha256": uploaded_file.sha256_checksum,
            "expiresIn": settings.SIGNED_URL_EXPIRY_SECONDS,
        })
        logger.info("ws_download_url_sent", job_id=job_id_str, kiosk_id=kiosk_id)
    except Exception as exc:
        logger.error("ws_download_url_error", error=str(exc))
        await ws_manager.send_to_kiosk(kiosk_id, "DOWNLOAD_URL_ERROR", {
            "jobId": job_id_str, "error": "STORAGE_ERROR"
        })
