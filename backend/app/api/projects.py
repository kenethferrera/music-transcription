"""
Projects API Router
"""
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from backend.app.jobs import ProjectJobOrchestrator
from backend.app.models.project_store import get_project_store
from backend.app.schemas.project import (
    ExportResponse,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectSummary,
    StemUrlsResponse,
)
from backend.app.storage import get_storage_service
from shared.music_schema.arrangement import Arrangement
from shared.processing_contracts.jobs import JobProgressEvent, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectCreateResponse)
def create_project(req: ProjectCreateRequest):
    store = get_project_store()
    storage = get_storage_service()

    record = store.create_project(
        title=req.title,
        artist=req.artist or "Unknown Artist",
        filename=req.filename,
    )

    upload_url = storage.generate_presigned_upload_url(
        object_key=record.upload_object_key,
        content_type=req.content_type,
    )

    return ProjectCreateResponse(
        project_id=record.project_id,
        title=record.title,
        upload_url=upload_url,
        upload_key=record.upload_object_key,
    )


@router.get("", response_model=List[ProjectSummary])
def list_projects():
    store = get_project_store()
    records = store.list_projects()
    return [
        ProjectSummary(
            id=r.project_id,
            title=r.title,
            artist=r.artist,
            original_filename=r.original_filename,
            created_at=r.created_at,
            status=r.status,
            stage=r.stage,
            progress_percent=r.progress_percent,
            duration_seconds=r.duration_seconds,
            total_notes=r.total_notes,
            tracks_count=r.tracks_count,
        )
        for r in records
    ]


@router.get("/{project_id}", response_model=ProjectSummary)
def get_project(project_id: str):
    store = get_project_store()
    record = store.get_project(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectSummary(
        id=record.project_id,
        title=record.title,
        artist=record.artist,
        original_filename=record.original_filename,
        created_at=record.created_at,
        status=record.status,
        stage=record.stage,
        progress_percent=record.progress_percent,
        duration_seconds=record.duration_seconds,
        total_notes=record.total_notes,
        tracks_count=record.tracks_count,
    )


@router.delete("/{project_id}")
def delete_project(project_id: str):
    store = get_project_store()
    storage = get_storage_service()

    record = store.get_project(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete all objects belonging to this project in storage
    storage.delete_prefix(f"uploads/{project_id}/")
    storage.delete_prefix(f"stems/{project_id}/")
    storage.delete_prefix(f"arrangements/{project_id}/")
    storage.delete_prefix(f"exports/{project_id}/")

    store.delete_project(project_id)
    return {"status": "deleted", "project_id": project_id}


@router.post("/{project_id}/process")
def start_processing(project_id: str, background_tasks: BackgroundTasks):
    store = get_project_store()
    record = store.get_project(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")

    if record.status == JobStatus.PROCESSING:
        return {"status": "already_processing", "project_id": project_id}

    orchestrator = ProjectJobOrchestrator(
        project_id=record.project_id,
        title=record.title,
        upload_object_key=record.upload_object_key,
        original_filename=record.original_filename,
        status_callback=store.update_progress,
    )

    background_tasks.add_task(orchestrator.run)
    return {"status": "started", "project_id": project_id}


@router.get("/{project_id}/events")
async def project_events_stream(project_id: str, request: Request):
    store = get_project_store()
    record = store.get_project(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")

    queue = asyncio.Queue()
    store.add_listener(project_id, queue)

    async def event_generator():
        try:
            # Emit current status immediately
            init_event = record.latest_event or JobProgressEvent(
                project_id=record.project_id,
                stage=record.stage,
                status=record.status,
                progress_percent=record.progress_percent,
                current_step=1,
                total_steps=9,
                stage_name=record.stage.value,
                message="Connected to job progress stream.",
                timestamp="",
            )
            yield f"data: {init_event.model_dump_json()}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event: JobProgressEvent = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {event.model_dump_json()}\n\n"
                    if event.status in (JobStatus.SUCCESS, JobStatus.FAILED):
                        break
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield ": keepalive\n\n"
        finally:
            store.remove_listener(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{project_id}/arrangement", response_model=Arrangement)
def get_arrangement(project_id: str):
    storage = get_storage_service()
    arr_key = f"arrangements/{project_id}/canonical.json"

    if not storage.object_exists(arr_key):
        raise HTTPException(status_code=404, detail="Arrangement not found or still processing.")

    data = storage.download_bytes(arr_key)
    return Arrangement.model_validate_json(data)


@router.put("/{project_id}/arrangement", response_model=Arrangement)
def update_arrangement(project_id: str, updated_arr: Arrangement):
    storage = get_storage_service()
    arr_key = f"arrangements/{project_id}/canonical.json"

    # Save edited arrangement
    json_bytes = updated_arr.model_dump_json(indent=2).encode("utf-8")
    storage.upload_bytes(json_bytes, arr_key, content_type="application/json")

    # Re-generate exports with updated arrangement in background
    from workers.export import KaraokeExporter, MidiExporter, MusicXMLExporter, PDFExporter

    midi_bytes = MidiExporter().export(updated_arr)
    storage.upload_bytes(midi_bytes, f"exports/{project_id}/multitrack.mid", content_type="audio/midi")

    kar_bytes = KaraokeExporter().export(updated_arr)
    storage.upload_bytes(kar_bytes, f"exports/{project_id}/karaoke.kar", content_type="audio/midi")

    xml_exporter = MusicXMLExporter()
    full_xml = xml_exporter.export_full_score(updated_arr)
    lead_xml = xml_exporter.export_lead_sheet(updated_arr)

    storage.upload_bytes(
        full_xml.encode("utf-8"),
        f"exports/{project_id}/full_score.musicxml",
        content_type="application/vnd.recordare.musicxml+xml",
    )
    storage.upload_bytes(
        lead_xml.encode("utf-8"),
        f"exports/{project_id}/lead_sheet.musicxml",
        content_type="application/vnd.recordare.musicxml+xml",
    )

    pdf_exporter = PDFExporter()
    full_pdf = pdf_exporter.render_musicxml_to_pdf(full_xml, updated_arr.metadata.title, "Full Score")
    lead_pdf = pdf_exporter.render_musicxml_to_pdf(lead_xml, updated_arr.metadata.title, "Lead Sheet")

    storage.upload_bytes(full_pdf, f"exports/{project_id}/full_score.pdf", content_type="application/pdf")
    storage.upload_bytes(lead_pdf, f"exports/{project_id}/lead_sheet.pdf", content_type="application/pdf")

    return updated_arr


@router.get("/{project_id}/stems", response_model=StemUrlsResponse)
def get_stem_urls(project_id: str):
    storage = get_storage_service()
    stems = ["vocals", "drums", "bass", "other"]
    urls: Dict[str, str] = {}

    for stem in stems:
        key = f"stems/{project_id}/{stem}.wav"
        if storage.object_exists(key):
            urls[stem] = storage.generate_presigned_download_url(key)

    # Also add original audio
    store = get_project_store()
    rec = store.get_project(project_id)
    if rec and storage.object_exists(rec.upload_object_key):
        urls["original"] = storage.generate_presigned_download_url(rec.upload_object_key)

    return StemUrlsResponse(project_id=project_id, stems=urls)


@router.get("/{project_id}/export/{export_format}", response_model=ExportResponse)
def get_export_url(project_id: str, export_format: str):
    storage = get_storage_service()
    format_map = {
        "midi": ("multitrack.mid", "audio/midi"),
        "kar": ("karaoke.kar", "audio/midi"),
        "musicxml": ("full_score.musicxml", "application/vnd.recordare.musicxml+xml"),
        "lead-musicxml": ("lead_sheet.musicxml", "application/vnd.recordare.musicxml+xml"),
        "pdf": ("full_score.pdf", "application/pdf"),
        "lead-pdf": ("lead_sheet.pdf", "application/pdf"),
        "lyrics-txt": ("lyrics.txt", "text/plain"),
        "lyrics-lrc": ("lyrics.lrc", "text/plain"),
    }

    if export_format not in format_map:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format '{export_format}'. Supported: {list(format_map.keys())}",
        )

    filename, _ = format_map[export_format]
    object_key = f"exports/{project_id}/{filename}"

    if not storage.object_exists(object_key):
        raise HTTPException(
            status_code=404,
            detail=f"Export {filename} not yet generated. Please wait for project processing to finish.",
        )

    download_url = storage.generate_presigned_download_url(object_key, filename=filename)
    return ExportResponse(
        project_id=project_id,
        format=export_format,
        download_url=download_url,
        filename=filename,
    )

