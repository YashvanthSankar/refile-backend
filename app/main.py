from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import os
from pathlib import Path
from .config import settings
from .db import SupabaseClient
from .security import get_current_user, verify_user_access, sanitize_filename
from .ai_agent import get_agent
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

    Saves uploaded file to user-specific folder, processes with AI agent,
    and records everything in Supabase.
    Returns a JSON object with metadata and AI-generated command.
    
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

    # Process with AI agent
    try:
        agent = get_agent()
        ai_response = agent.process_request(
            user_prompt=prompt,
            uploaded_files=[file.filename],
            user_id=user_id,
            previous_result=None
        )
        
        # Extract structured response
        structured_resp = ai_response.get('structured_response')
        ai_result = {
            "linux_command": structured_resp.linux_command if structured_resp else None,
            "input_files": structured_resp.input_files if structured_resp else [],
            "output_files": structured_resp.output_files if structured_resp else [],
            "description": structured_resp.description if structured_resp else None,
        }
    except Exception as e:
        # If AI processing fails, continue without it
        print(f"AI processing error: {e}")
        ai_result = {
            "linux_command": None,
            "input_files": [],
            "output_files": [],
            "description": f"AI processing failed: {str(e)}",
        }

    # create DB record with AI response
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
    }, "prompt_record": db_res, "ai_response": ai_result}


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


@app.post("/api/process")
async def process_prompt(
    prompt: str = Form(...),
    uploaded_files: str = Form(...),  # JSON string of filenames
    previous_command: str = Form(None),
    previous_input_files: str = Form(None),
    previous_output_files: str = Form(None),
    previous_description: str = Form(None),
    current_user: str = Depends(get_current_user)
):
    """Process a prompt with AI agent for follow-up commands.
    
    This endpoint allows users to have a conversation with the AI agent
    without uploading new files. Useful for follow-up requests like:
    "Convert that audio to WAV format"
    
    Args:
        prompt: User's natural language request
        uploaded_files: JSON string list of available filenames
        previous_*: Previous AI response for conversation continuity
        
    Returns:
        AI-generated command and metadata
    """
    import json
    
    user_id = current_user
    
    # Parse uploaded files list
    try:
        files_list = json.loads(uploaded_files) if uploaded_files else []
    except:
        files_list = [uploaded_files] if uploaded_files else []
    
    # Build previous result if provided
    previous_result = None
    if previous_command:
        from dataclasses import dataclass
        from .ai_agent import ResponseFormat
        
        @dataclass
        class PrevResponse:
            linux_command: str
            input_files: list
            output_files: list
            description: str
        
        try:
            prev_input = json.loads(previous_input_files) if previous_input_files else []
            prev_output = json.loads(previous_output_files) if previous_output_files else []
        except:
            prev_input = []
            prev_output = []
            
        previous_result = {
            'structured_response': PrevResponse(
                linux_command=previous_command,
                input_files=prev_input,
                output_files=prev_output,
                description=previous_description or ""
            )
        }
    
    # Process with AI agent
    try:
        agent = get_agent()
        ai_response = agent.process_request(
            user_prompt=prompt,
            uploaded_files=files_list,
            user_id=user_id,
            previous_result=previous_result
        )
        
        # Extract structured response
        structured_resp = ai_response.get('structured_response')
        ai_result = {
            "linux_command": structured_resp.linux_command if structured_resp else None,
            "input_files": structured_resp.input_files if structured_resp else [],
            "output_files": structured_resp.output_files if structured_resp else [],
            "description": structured_resp.description if structured_resp else None,
        }
        
        return {"status": "ok", "ai_response": ai_result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing error: {str(e)}")
