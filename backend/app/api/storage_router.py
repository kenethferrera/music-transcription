"""
Local Storage Router for direct upload/download when testing without S3 presigned URLs.
"""
import io
import mimetypes
import os
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, Response

from backend.app.storage import get_storage_service
from backend.app.storage.local_storage import LocalStorage

router = APIRouter(prefix="/storage", tags=["storage"])


@router.put("/local-upload")
async def handle_local_upload(request: Request, key: str = Query(...)):
    storage = get_storage_service()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=400, detail="Local upload only available in local storage mode")

    body_bytes = await request.body()
    storage.upload_bytes(body_bytes, key)
    return {"status": "uploaded", "key": key, "size": len(body_bytes)}


@router.get("/local-download")
def handle_local_download(key: str = Query(...), filename: str = Query(None)):
    storage = get_storage_service()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=400, detail="Local download only available in local storage mode")

    if not storage.object_exists(key):
        raise HTTPException(status_code=404, detail="File not found")

    full_path = storage._full_path(key)
    media_type, _ = mimetypes.guess_type(full_path)

    headers = {}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return FileResponse(
        path=full_path,
        media_type=media_type or "application/octet-stream",
        headers=headers,
    )

