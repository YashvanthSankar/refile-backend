from fastapi import FastAPI, Query, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
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
    If multiple commands are detected (separated by && or newlines), they will be
    executed sequentially one after the other.
    
    Args:
        user_dir: Path to user's upload directory
        linux_command: The command to execute (may contain multiple commands)
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
    
    # Detect and split multiple commands
    # Commands can be separated by && or by newlines
    commands = []
    
    # First, split by newlines and clean up
    lines = [line.strip() for line in linux_command.split('\n') if line.strip()]
    
    # Then, split each line by && if present
    for line in lines:
        if '&&' in line:
            # Split by && and add each part
            parts = [part.strip() for part in line.split('&&') if part.strip()]
            commands.extend(parts)
        else:
            commands.append(line)
    
    # If we ended up with just one command, keep it simple
    if len(commands) == 1:
        commands = [linux_command.strip()]
    
    try:
        # Execute commands sequentially
        for cmd in commands:
            # Run each command in the container
            container_logs = client.containers.run(
                DOCKER_IMAGE_NAME,
                command=cmd,
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

def map_files_to_stored_names(user_dir: Path, file_identifiers: List[str]) -> List[str]:
    """
    Map file identifiers to actual stored filenames.
    file_identifiers can be either:
    - File IDs (UUIDs)
    - Stored filenames (UUID.ext)
    - Original filenames (fallback, tries extension matching)
    """
    files_list = []
    
    for identifier in file_identifiers:
        stored_filename = None
        
        # Check if it's already a stored filename (contains UUID pattern)
        if len(identifier.split('.')[0]) == 36:  # UUID length
            stored_filename = identifier
        else:
            # Try to find by file ID (if just UUID provided)
            try:
                # Check if it's a UUID
                if len(identifier) == 36 and '-' in identifier:
                    # Look for files starting with this UUID
                    for f in user_dir.iterdir():
                        if f.is_file() and f.name.startswith(identifier):
                            stored_filename = f.name
                            break
            except:
                pass
            
            # Fallback: extension matching (original problematic logic)
            if not stored_filename:
                original_ext = Path(identifier).suffix.lower()
                matching_files = [f for f in user_dir.iterdir() 
                                if f.is_file() and f.suffix.lower() == original_ext]
                if matching_files:
                    stored_filename = matching_files[0].name
        
        if stored_filename and (user_dir / stored_filename).exists():
            files_list.append(stored_filename)
        else:
            # Log warning and skip
            print(f"Warning: Could not map file identifier '{identifier}' to stored file")
    
    return files_list

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
        # Save file with UUID name for security
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
            "stored_filename": filename,  # UUID-based filename
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
    previous_command_template: str = Form(None),
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
        original_files_list = json.loads(uploaded_files) if uploaded_files else []
    except:
        original_files_list = [uploaded_files] if uploaded_files else []
    
    # Map file identifiers to actual stored UUID filenames using improved logic
    user_dir = user_folder(user_id)
    files_list = map_files_to_stored_names(user_dir, original_files_list)
    
    # Build previous result if provided
    previous_result = None
    if previous_command:
        from dataclasses import dataclass
        from .ai_agent import ResponseFormat
        
        @dataclass
        class PrevResponse:
            linux_command: str
            command_template: str
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
                command_template=previous_command_template or previous_command,
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
            "command_template": structured_resp.command_template if structured_resp else None,
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


@app.get("/files/{user_id}/{filename}")
async def download_file(
    user_id: str, 
    filename: str,
    current_user: str = Depends(get_current_user)
):
    """
    Download/serve processed files from user's directory.
    """
    # Verify user access
    verify_user_access(current_user, user_id)
    
    # Sanitize the filename to prevent path traversal
    safe_filename = sanitize_filename(filename)
    
    # Construct file path
    user_dir = user_folder(user_id)
    file_path = user_dir / safe_filename
    
    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file is within user directory (extra security)
    try:
        file_path.resolve().relative_to(user_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Determine content type
    content_type, _ = mimetypes.guess_type(str(file_path))
    if content_type is None:
        content_type = 'application/octet-stream'
    
    # Return the file
    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type=content_type
    )


@app.get("/files/{user_id}")
async def list_user_files(
    user_id: str,
    current_user: str = Depends(get_current_user)
):
    """
    List all files in user's directory.
    """
    # Verify user access
    verify_user_access(current_user, user_id)
    
    user_dir = user_folder(user_id)
    
    if not user_dir.exists():
        return {"files": []}
    
    files = []
    for file_path in user_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "download_url": f"/files/{user_id}/{file_path.name}"
            })
    
    return {"files": files}

def render_preset_command(
    command_template: str,
    input_mappings: dict,
    output_patterns: List[dict]
) -> tuple[str, List[str]]:
    """
    Render a preset command template with actual file names.
    
    Args:
        command_template: Template string like "convert {input_file} -colorspace Gray {output_file}"
        input_mappings: Dict mapping variable names to actual filenames, e.g., {"input_file": "photo.jpg"}
        output_patterns: List of output file patterns from preset
        
    Returns:
        Tuple of (rendered_command, list_of_output_filenames)
    """
    rendered_command = command_template
    output_files = []
    
    # Replace input variables
    for var_name, actual_filename in input_mappings.items():
        rendered_command = rendered_command.replace(f"{{{var_name}}}", actual_filename)
    
    # Generate output filenames from patterns
    for output_pattern in output_patterns:
        pattern_template = output_pattern.get("template", "")
        
        # Replace special variables in output pattern
        output_filename = pattern_template
        
        # Get first input file for basename/extension extraction
        first_input = list(input_mappings.values())[0] if input_mappings else "output"
        input_path = Path(first_input)
        
        # Replace template variables
        output_filename = output_filename.replace("{input_basename}", input_path.stem)
        output_filename = output_filename.replace("{input_ext}", input_path.suffix)
        output_filename = output_filename.replace("{timestamp}", datetime.now().strftime("%Y%m%d_%H%M%S"))
        
        output_files.append(output_filename)
        
        # Replace in command
        var_name = output_pattern.get("name", "output_file")
        rendered_command = rendered_command.replace(f"{{{var_name}}}", output_filename)
    
    return rendered_command, output_files


# ============= PRESET ROUTES =============

@app.post("/api/presets")
async def create_preset(
    name: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    command_template: str = Form(...),
    input_file_patterns: str = Form(...),  # JSON string
    output_file_patterns: str = Form(...),  # JSON string
    tags: str = Form("[]"),  # JSON array string
    tool: str = Form(...),
    is_public: bool = Form(True),
    current_user: str = Depends(get_current_user)
):
    """
    Create a new community preset.
    
    Example input_file_patterns:
    [{"name": "input_file", "extensions": [".png", ".jpg"], "description": "Image to convert"}]
    
    Example output_file_patterns:
    [{"name": "output_file", "template": "{input_basename}_grayscale{input_ext}", "description": "Grayscale image"}]
    """
    try:
        input_patterns = json.loads(input_file_patterns)
        output_patterns = json.loads(output_file_patterns)
        tags_list = json.loads(tags)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in patterns or tags")
    
    preset_data = {
        "user_id": current_user,
        "name": name,
        "description": description,
        "category": category,
        "command_template": command_template,
        "input_file_patterns": json.dumps(input_patterns),
        "output_file_patterns": json.dumps(output_patterns),
        "tags": tags_list,
        "tool": tool,
        "is_public": is_public,
    }
    
    try:
        result = sb.create_preset(preset_data)
        return {"status": "ok", "preset": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create preset: {str(e)}")


@app.get("/api/presets")
def list_presets(
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: str = Depends(get_current_user)
):
    """
    List community presets with optional filtering.
    
    Filters:
    - category: Filter by category (image, video, audio, pdf)
    - tag: Filter by tag
    - search: Search in name and description
    - user_id: Filter by creator (to see your own presets)
    """
    try:
        presets = sb.list_presets(
            category=category,
            tag=tag,
            search=search,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        return {"status": "ok", "presets": presets, "count": len(presets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list presets: {str(e)}")


@app.get("/api/presets/{preset_id}")
def get_preset(
    preset_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about a specific preset."""
    try:
        preset = sb.get_preset_by_id(preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        # Check if user has liked this preset
        has_liked = sb.has_user_liked_preset(preset_id, current_user)
        preset["has_liked"] = has_liked
        
        return {"status": "ok", "preset": preset}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preset: {str(e)}")


@app.post("/api/presets/{preset_id}/like")
async def like_preset(
    preset_id: str,
    current_user: str = Depends(get_current_user)
):
    """Like/unlike a preset (toggle)."""
    try:
        result = sb.toggle_preset_like(preset_id, current_user)
        return {"status": "ok", "liked": result["liked"], "likes_count": result["likes_count"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to like preset: {str(e)}")


@app.delete("/api/presets/{preset_id}")
async def delete_preset(
    preset_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a preset (only creator can delete)."""
    try:
        preset = sb.get_preset_by_id(preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        # Verify ownership
        if preset["user_id"] != current_user:
            raise HTTPException(status_code=403, detail="You can only delete your own presets")
        
        sb.delete_preset(preset_id)
        return {"status": "ok", "message": "Preset deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete preset: {str(e)}")


@app.post("/api/presets/{preset_id}/execute")
async def execute_preset(
    preset_id: str,
    file_mappings: str = Form(...),  # JSON: {"input_file": "actual_filename.jpg"}
    current_user: str = Depends(get_current_user)
):
    """
    Execute a preset with user's files.
    
    Args:
        preset_id: UUID of the preset to execute
        file_mappings: JSON mapping of variable names to actual filenames
                      e.g., {"input_file": "a6ba841e-d302-40ca-9183-4d4c117b559a.png"}
    """
    try:
        # Get preset
        preset = sb.get_preset_by_id(preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        # Parse file mappings
        try:
            mappings = json.loads(file_mappings)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid file_mappings JSON")
        
        # Parse preset patterns
        output_patterns = json.loads(preset["output_file_patterns"])
        
        # Render command
        rendered_command, expected_outputs = render_preset_command(
            preset["command_template"],
            mappings,
            output_patterns
        )
        
        # Execute in Docker
        user_dir = user_folder(current_user)
        new_files = execute_command_in_docker(
            user_dir, 
            rendered_command, 
            list(mappings.values())
        )
        
        # Register new files
        new_files_metadata = register_generated_files(user_dir, new_files, current_user)
        
        # Increment usage count
        sb.increment_preset_usage(preset_id)
        
        return {
            "status": "ok",
            "preset_name": preset["name"],
            "command_executed": rendered_command,
            "output_files": new_files_metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute preset: {str(e)}")