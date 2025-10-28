from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import os
from pathlib import Path
from .config import settings
from .db import SupabaseClient
from .security import get_current_user, verify_user_access, sanitize_filename
from datetime import datetime

app = FastAPI(title="refile-backend", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ensure upload dir exists
UPLOAD_ROOT = Path(settings.UPLOAD_DIR)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

sb = SupabaseClient()


def user_folder(user_id: str) -> Path:
    p = UPLOAD_ROOT / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.post("/api/upload")
async def upload_file(
    prompt: str = Form(...),
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """Upload a file and save prompt in Supabase.

    Saves uploaded file to user-specific folder and records a prompt entry in Supabase.
    Returns a JSON object with metadata and a placeholder `ai_response` field (empty for now).
    
    Security: Only authenticated users can upload files to their own folder.
    """
    user_id = current_user  # Use authenticated user, not client-provided
    
    # save file
    ext = Path(file.filename).suffix
    file_id = str(uuid4())
    filename = f"{file_id}{ext}"
    dest = user_folder(user_id) / filename

    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    # create DB record
    record = {
        "user_id": user_id,
        "prompt": prompt,
        "original_filename": file.filename,
        "stored_filename": filename,
        "content_type": file.content_type,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        db_res = sb.insert_prompt(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db error: {e}")

    return {"status": "ok", "file": {
        "id": file_id,
        "original_filename": file.filename,
        "stored_filename": filename,
        "content_type": file.content_type,
        "path": str(dest),
    }, "prompt_record": db_res, "ai_response": None}


@app.get("/api/list/{user_id}")
def list_user_files(
    user_id: str,
    current_user: str = Depends(get_current_user)
):
    """List saved prompts/files for a user from Supabase.
    
    Security: Users can only list their own files.
    """
    # Verify user can only access their own files
    verify_user_access(current_user, user_id)
    
    try:
        rows = sb.get_prompts_for_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db error: {e}")
    return {"status": "ok", "items": rows}


@app.get("/api/download/{user_id}/{stored_filename}")
def download_file(
    user_id: str,
    stored_filename: str,
    current_user: str = Depends(get_current_user)
):
    """Download a stored file.
    
    Security: Users can only download their own files.
    Path traversal protection applied to filenames.
    """
    # Verify user can only access their own files
    verify_user_access(current_user, user_id)
    
    # Sanitize filename to prevent path traversal
    safe_filename = sanitize_filename(stored_filename)
    
    path = UPLOAD_ROOT / user_id / safe_filename
    
    # Additional security: ensure resolved path is within user folder
    try:
        path = path.resolve()
        user_folder_path = (UPLOAD_ROOT / user_id).resolve()
        if not str(path).startswith(str(user_folder_path)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, filename=safe_filename)


@app.get("/api/health")
def health():
    return {"status": "ok"}
