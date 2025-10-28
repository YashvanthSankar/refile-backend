from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
from pathlib import Path
from app.ai_agent import get_agent

# Simple test endpoint app
app = FastAPI(title="refile-test", version="1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/process-only")
async def process_only(
    prompt: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Simple endpoint: Takes files and prompt, returns AI command
    NO DATABASE, NO STORAGE - Just AI processing
    """
    try:
        # Get file names
        filenames = [file.filename for file in files]
        
        # Get AI agent
        agent = get_agent()
        
        # Process with AI
        result = agent.process_request(
            user_prompt=prompt,
            uploaded_files=filenames,
            user_id="test_user",  # Dummy user for testing
            previous_result=None
        )
        
        # Extract structured response
        structured_resp = result.get('structured_response')
        
        if structured_resp:
            return {
                "status": "ok",
                "ai_response": {
                    "linux_command": structured_resp.linux_command,
                    "input_files": structured_resp.input_files,
                    "output_files": structured_resp.output_files,
                    "description": structured_resp.description,
                }
            }
        else:
            return {
                "status": "error",
                "message": "AI processing failed"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
