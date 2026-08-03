"""
PrintBar Backend — Upload API Endpoints

POST   /api/v1/uploads         — Upload a PDF file.
GET    /api/v1/uploads/{id}    — Get upload metadata.
DELETE /api/v1/uploads/{id}    — Delete an upload.

All endpoints require a valid guest session JWT.
File size limits are enforced at both Nginx and FastAPI levels.
Business logic lives in UploadService — this layer only handles HTTP concerns.
"""


import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.database.session import get_db
from app.dependencies import get_current_guest_session
from app.exceptions.base import UploadNotFoundError
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.services.upload_service import UploadService

logger = get_logger(__name__)
router = APIRouter(prefix="/uploads", tags=["Upload"])
settings = get_settings()

# Maximum upload size: enforced here in addition to Nginx.
_MAX_UPLOAD_BYTES = settings.max_file_size_bytes


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF file",
    description=(
        "Uploads a PDF file for printing. "
        "The file is validated through 10 steps before being stored. "
        "Returns the file ID and page count. "
        "Requires a valid guest session token."
    ),
)
@limiter.limit("5/10minutes")
async def upload_file(
    request: Request,
    file: UploadFile = File(..., description="PDF file to upload"),
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Accepts a multipart file upload, validates it, and stores it in Supabase Storage.

    The response includes:
        - fileId: UUID to reference in subsequent API calls.
        - pageCount: Total pages in the PDF.
        - fileSizeBytes: Actual file size.
        - sha256: Checksum for integrity verification.
        - expiresAt: When the file will be auto-deleted if not printed.

    Raises:
        422: Validation failure with specific error code.
        413: File exceeds size limit.
        401: Invalid or missing session token.
    """
    # Read file bytes with size guard.
    file_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)

    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "success": False,
                "error": {
                    "code": "UPLOAD_002",
                    "message": f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit.",
                },
            },
        )

    logger.info(
        "upload_request_received",
        session_id=session_id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(file_bytes),
    )

    service = UploadService(db)

    correlation_id = getattr(request.state, "correlation_id", "unknown")

    uploaded_file = await service.upload_pdf(
        session_id=session_id,
        filename=file.filename or "unknown.pdf",
        content_type=file.content_type or "application/pdf",
        file_bytes=file_bytes,
        correlation_id=correlation_id,
    )

    from app.core.metrics import UPLOADS_TOTAL
    UPLOADS_TOTAL.inc()

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "success": True,
            "data": {
                "fileId": str(uploaded_file.id),
                "pageCount": uploaded_file.page_count,
                "fileSizeBytes": uploaded_file.file_size_bytes,
                "sha256": uploaded_file.sha256_checksum,
                "expiresAt": uploaded_file.expires_at,
                "originalFilename": uploaded_file.original_filename,
            },
        },
    )


@router.get(
    "/{file_id}",
    summary="Get upload metadata",
    description="Returns metadata for an uploaded file. Only the owning session can access.",
)
async def get_upload(
    file_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns metadata for a specific uploaded file.

    The file must belong to the requesting session.
    Storage paths and filenames are not included in the response
    if the file has been deleted.

    Raises:
        404: File not found or belongs to a different session.
    """
    repo = UploadedFileRepository(db)
    uploaded_file = await repo.get_by_id_and_session(file_id, session_id)

    if not uploaded_file:
        raise UploadNotFoundError()

    return {
        "success": True,
        "data": {
            "fileId": str(uploaded_file.id),
            "pageCount": uploaded_file.page_count,
            "fileSizeBytes": uploaded_file.file_size_bytes,
            "isDeleted": uploaded_file.is_deleted,
            "expiresAt": uploaded_file.expires_at,
            "createdAt": uploaded_file.created_at.isoformat() if uploaded_file.created_at else None,
        },
    }


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an upload",
    description=(
        "Deletes a file from Supabase Storage and marks the database record as deleted. "
        "Only the owning session can delete the file."
    ),
)
async def delete_upload(
    file_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Permanently deletes a file from storage and nulls PII in the database.

    Per privacy policy (doc 36), the database record is retained
    but storage_path and original_filename are set to NULL.

    Raises:
        404: File not found or already deleted.
    """
    service = UploadService(db)
    deleted = await service.delete_upload(session_id=session_id, file_id=file_id)

    if not deleted:
        raise UploadNotFoundError()

    return {"success": True, "message": "File deleted successfully."}
