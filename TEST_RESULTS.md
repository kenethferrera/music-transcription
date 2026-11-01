# Automated Test Results Report
**Date:** 2026-11-01  
**Environment:** Python 3.13.5 (win32), Node.js v22.16.0, Vite 5.4.21  
**Total Tests:** 33 Passed, 0 Failed, 0 Skipped  

---

## 1. Automated Python Test Suite

### Command Executed:
```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest -v tests/
```

### Actual Output:
```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\Admin\music transcript\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Admin\music transcript
plugins: anyio-4.15.1
collecting ... collected 33 items

tests/test_api_endpoints.py::test_root_and_health PASSED                 [  3%]
tests/test_api_endpoints.py::test_project_crud PASSED                    [  6%]
tests/test_arrangement_editing.py::test_arrangement_edit_and_export_regeneration PASSED [  9%]
tests/test_export_deep_inspection.py::test_deep_midi_inspection PASSED   [ 12%]
tests/test_export_deep_inspection.py::test_deep_karaoke_kar_inspection PASSED [ 15%]
tests/test_export_deep_inspection.py::test_deep_musicxml_inspection PASSED [ 18%]
tests/test_export_deep_inspection.py::test_deep_pdf_inspection PASSED    [ 21%]
tests/test_exports.py::test_midi_export PASSED                           [ 24%]
tests/test_exports.py::test_karaoke_kar_export PASSED                    [ 27%]
tests/test_exports.py::test_musicxml_full_score_and_lead_sheet PASSED    [ 30%]
tests/test_exports.py::test_pdf_export PASSED                            [ 33%]
tests/test_music_analysis.py::test_key_estimation_c_major PASSED         [ 36%]
tests/test_music_analysis.py::test_chord_estimation PASSED               [ 39%]
tests/test_persistence_restart.py::test_project_survives_store_restart PASSED [ 42%]
tests/test_pipeline_e2e.py::test_full_pipeline_orchestrator PASSED       [ 45%]
tests/test_r2_mock_integration.py::test_r2_endpoint_configuration PASSED [ 48%]
tests/test_r2_mock_integration.py::test_r2_presigned_upload_url PASSED   [ 51%]
tests/test_r2_mock_integration.py::test_r2_presigned_download_url PASSED [ 54%]
tests/test_r2_mock_integration.py::test_r2_object_exists PASSED          [ 57%]
tests/test_r2_mock_integration.py::test_r2_health_check_healthy PASSED   [ 60%]
tests/test_r2_mock_integration.py::test_r2_health_check_unhealthy PASSED [ 63%]
tests/test_reconciler.py::test_note_deduplication PASSED                 [ 66%]
tests/test_reconciler.py::test_reconcile_full_arrangement PASSED         [ 69%]
tests/test_schemas.py::test_note_event_properties PASSED                 [ 72%]
tests/test_schemas.py::test_lyric_event_properties PASSED                [ 75%]
tests/test_schemas.py::test_arrangement_roundtrip PASSED                 [ 78%]
tests/test_schemas.py::test_job_progress_event PASSED                    [ 81%]
tests/test_storage.py::test_storage_upload_download_bytes PASSED         [ 84%]
tests/test_storage.py::test_storage_presigned_urls PASSED                [ 87%]
tests/test_storage.py::test_storage_delete_prefix PASSED                 [ 90%]
tests/test_stt_and_alignment.py::test_mock_stt_transcription PASSED      [ 93%]
tests/test_stt_and_alignment.py::test_lyric_syllabification PASSED       [ 96%]
tests/test_stt_and_alignment.py::test_lyric_to_note_alignment PASSED     [100%]

============================= 33 passed in 4.42s ==============================
```

---

## 2. Frontend Compilation & Typecheck Test

### Command Executed:
```bash
cd frontend && npm run build
```

### Actual Output:
```text
> music-transcription-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 1583 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.82 kB │ gzip:  0.46 kB
dist/assets/index-zRLtW3VI.css   25.51 kB │ gzip:  5.04 kB
dist/assets/index-z2lxIhuC.js   191.04 kB │ gzip: 57.42 kB
✓ built in 5.60s
```

---

## 3. Test Classification & Environment Distinction

| Test Category | Number of Tests | Execution Mode | External Resource Dependencies |
| :--- | :--- | :--- | :--- |
| **Pydantic Schema Serialization** | 4 | Real / Native | None |
| **FastAPI REST Endpoints** | 2 | Real / Native | SQLite persistence in tempdir |
| **Database Persistence & Restart** | 1 | Real / Native | SQLite database file |
| **Storage (Local Adapter)** | 3 | Real / Native | Local temp filesystem |
| **Cloudflare R2 Adapter Integration** | 6 | Mocked S3 Boto3 Client | Cloudflare R2 credentials (mocked for CI) |
| **STT Response & Lyric Alignment** | 3 | Real Aligner / Mock STT | None |
| **Non-AI Musical Analysis** | 2 | Real FFT & Chroma | None |
| **Note Reconciler & Deduplication**| 2 | Real / Native | None |
| **Arrangement Editing & Export Regen** | 1 | Real / Native | None |
| **Export Generation (MIDI, KAR, XML, PDF)** | 4 | Real / Native | Mido, XML minidom, Vector PDF |
| **Deep Binary & Text Format Inspection** | 4 | Real / Native | Mido binary parser, XML parser |
| **9-Stage Pipeline End-to-End** | 1 | Real / Native (Synthetic Audio) | None |

### Key Distinction:
- **Mocked Components:** Cloudflare R2 client in `test_r2_mock_integration.py` (simulates S3 responses without requiring live API keys), External STT provider in pipeline test (uses `MockSTTProvider` to avoid third-party API rate limits and token fees).
- **Live / Real Components:** Everything else — audio reading/writing, note deduplication, FFT autocorrelation, Krumhansl-Schmuckler key estimation, chord template matching, lyric syllabification, arrangement JSON encoding, Standard MIDI Type 1 binary generation, KAR meta-event sequencing, MusicXML 4.0 generation, and Vector PDF generation.

