from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from uuid import uuid4
import os
import platform
import sys
from pathlib import Path
import docker
import json
import mimetypes
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

# Docker configuration
DOCKER_IMAGE_NAME = "my-base-image-clis"  # Configure this in your environment
CONTAINER_MOUNT_PATH = "/data"

def get_docker_client():
    """Connects to the Docker daemon."""
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not connect to Docker daemon: {str(e)}")

def get_user_id():
    """Gets the user:group ID to fix file permissions. Not supported on Windows."""
    if platform.system() == "Windows":
        return None
    return f"{os.getuid()}:{os.getgid()}"

def execute_command_in_docker(user_dir: Path, linux_command: str, input_files: List[str]) -> List[str]:
    """
    Execute a Linux command in a Docker container with user directory mounted.
    
    Args:
        user_dir: Path to user's upload directory
        linux_command: The command to execute
        input_files: List of input filenames
        
    Returns:
        List of newly created output files
    """
    client = get_docker_client()
    
    # Get list of files before execution
    files_before = set()
    if user_dir.exists():
        files_before = {f.name for f in user_dir.iterdir() if f.is_file()}
    
    # Convert to absolute path and resolve any symlinks
    user_dir_absolute = user_dir.resolve()
    
    # Prepare container run arguments with absolute host path
    volumes_dict = {
        str(user_dir_absolute): {
            'bind': CONTAINER_MOUNT_PATH,
            'mode': 'rw'
        }
    }
    
    user_id = get_user_id()
    
    try:
        # Run the container
        container_logs = client.containers.run(
            DOCKER_IMAGE_NAME,
            command=linux_command,
            remove=True,
            volumes=volumes_dict,
            user=user_id,
            stdout=True,
            stderr=True,
            working_dir=CONTAINER_MOUNT_PATH
        )
        
        # Get list of files after execution
        files_after = set()
        if user_dir.exists():
            files_after = {f.name for f in user_dir.iterdir() if f.is_file()}
        
        # Find newly created files
        new_files = list(files_after - files_before)
        
        return new_files
        
    except docker.errors.ContainerError as e:
        error_msg = e.stderr.decode('utf-8').strip() if e.stderr else "Command failed"
        raise HTTPException(status_code=400, detail=f"Docker command failed: {error_msg}")
    except docker.errors.ImageNotFound:
        raise HTTPException(status_code=500, detail=f"Docker image '{DOCKER_IMAGE_NAME}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker execution error: {str(e)}")

def register_generated_files(user_dir: Path, new_file_names: List[str], user_id: str) -> List[dict]:
    """
    Register newly generated files using the same logic as /api/upload
    
    Args:
        user_dir: Path to user's upload directory
        new_file_names: List of newly created filenames
        user_id: User ID
        
    Returns:
        List of file metadata with UUIDs
    """
    registered_files = []
    
    for filename in new_file_names:
        file_path = user_dir / filename
        
        if file_path.exists():
            # Generate UUID and new filename like upload route
            ext = file_path.suffix
            file_id = str(uuid4())
            new_filename = f"{file_id}{ext}"
            dest = user_dir / new_filename
            
            # Rename file to UUID format
            file_path.rename(dest)
            
            # Get content type
            content_type, _ = mimetypes.guess_type(str(dest))
            if not content_type:
                content_type = "application/octet-stream"
            
            # Create file metadata with correct path format
            relative_path = f"user_uploads/{user_id}/{new_filename}"
            
            file_info = {
                "id": file_id,
                "original_filename": filename,
                "stored_filename": new_filename,
                "content_type": content_type,
                "path": relative_path,
            }
            
            registered_files.append(file_info)
    
    return registered_files

@app.post("/api/upload")
async def upload_file(
    files: List[UploadFile] = File(...),
    current_user: str = Depends(get_current_user)
):
    """Upload one or more files without processing.

    Saves uploaded files to user-specific folder and returns file metadata.
    Use /api/process endpoint to generate AI commands for these files.
    
    Security: Only authenticated users can upload files to their own folder.
    """
    user_id = current_user  # Use authenticated user, not client-provided
    
    # Save all files
    uploaded_files_info = []
    original_filenames = []
    
    for file in files:
        # save file
        ext = Path(file.filename).suffix
        file_id = str(uuid4())
        filename = f"{file_id}{ext}"
        dest = user_folder(user_id) / filename

        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create correct relative path
        relative_path = f"user_uploads/{user_id}/{filename}"
        
        uploaded_files_info.append({
            "id": file_id,
            "original_filename": file.filename,
            "stored_filename": filename,
            "content_type": file.content_type,
            "path": relative_path,
        })
        
        original_filenames.append(file.filename)

    return {
        "status": "ok", 
        "files": uploaded_files_info,
        "file_count": len(uploaded_files_info),
        "message": "Files uploaded successfully. Use /api/process to generate commands."
    }


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


@app.delete("/api/delete/{user_id}/{file_id}")
def delete_file(
    user_id: str,
    file_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a file by its ID.
    
    Removes the file from the user's upload folder.
    The file_id should be the UUID part of the stored_filename (without extension).
    
    Security: Users can only delete their own files.
    """
    # Verify user can only access their own files
    verify_user_access(current_user, user_id)
    
    # Get user folder
    user_dir = user_folder(user_id)
    
    # Find files matching the file_id pattern
    deleted_files = []
    file_found = False
    
    try:
        # List all files in user directory
        for file_path in user_dir.iterdir():
            if file_path.is_file():
                # Check if filename starts with the file_id
                if file_path.stem == file_id or file_path.name.startswith(f"{file_id}."):
                    # Delete the file
                    file_path.unlink()
                    deleted_files.append(file_path.name)
                    file_found = True
        
        if not file_found:
            raise HTTPException(status_code=404, detail=f"File with ID '{file_id}' not found")
        
        return {
            "status": "ok",
            "message": f"File(s) deleted successfully",
            "deleted_files": deleted_files,
            "file_id": file_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/status/{prompt_id}")
def get_prompt_status(
    prompt_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get the processing status of a prompt/file upload.
    
    Returns the current AI processing status, response, and any error messages.
    Users can only check status of their own prompts.
    """
    try:
        record = sb.get_prompt_by_id(prompt_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Verify user owns this prompt
        verify_user_access(current_user, record["user_id"])
        
        return {
            "status": "ok",
            "id": str(record["id"]),
            "user_id": record["user_id"],
            "prompt": record["prompt"],
            "original_filename": record["original_filename"],
            "ai_processing_status": record.get("ai_processing_status", "pending"),
            "ai_response": record.get("ai_response"),
            "ai_command": record.get("ai_command"),
            "error_message": record.get("error_message"),
            "processed_at": record.get("processed_at"),
            "created_at": record["created_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


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
        
        # Execute the command in Docker
        if ai_result["linux_command"]:
            user_dir = user_folder(user_id)
            new_files = execute_command_in_docker(user_dir, ai_result["linux_command"], ai_result["input_files"])
            
            # Register new files
            new_files_metadata = register_generated_files(user_dir, new_files, user_id)
            
            ai_result["output_files"] = new_files_metadata
        
        return {"status": "ok", "ai_response": ai_result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing error: {str(e)}")
