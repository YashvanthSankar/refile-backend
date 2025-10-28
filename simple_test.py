"""
Simple Test Server - AI Processing Only, NO DATABASE
Just upload files, get AI commands back. That's it!
"""
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import AI agent
from app.ai_agent import get_agent

app = FastAPI(title="ReFile AI - Test Mode")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create temp upload directory
TEMP_DIR = Path("./temp-uploads")
TEMP_DIR.mkdir(exist_ok=True)

@app.get("/api/health")
async def health():
    """Health check"""
    return {"status": "ok", "mode": "test-no-db"}

@app.post("/api/process")
async def process_files(
    prompt: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Process files with AI - NO DATABASE SAVING
    Just returns the AI-generated command
    """
    try:
        # Save files temporarily
        saved_files = []
        for file in files:
            file_path = TEMP_DIR / file.filename
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_files.append({
                "name": file.filename,
                "size": len(content),
                "type": file.content_type
            })
        
        print(f"\n📁 Files received: {[f['name'] for f in saved_files]}")
        print(f"💬 Prompt: {prompt}")
        
        # Get AI agent and process
        agent = get_agent()
        
        # Create file list for AI (correct parameter names)
        file_names = [f["name"] for f in saved_files]
        
        print(f"🤖 Processing with AI...")
        ai_result = agent.process_request(
            user_prompt=prompt,
            uploaded_files=file_names,
            user_id="test_user"
        )
        
        print(f"✅ AI Response received!")
        print(f"Command: {ai_result.get('linux_command', 'N/A')[:100]}...")
        
        # Return AI response
        return {
            "status": "success",
            "files": saved_files,
            "prompt": prompt,
            "ai_response": ai_result
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e),
            "details": traceback.format_exc()
        }

@app.get("/")
async def root():
    return {
        "message": "ReFile AI Test Server",
        "mode": "No Database - Just AI Processing",
        "endpoints": {
            "health": "/api/health",
            "process": "/api/process (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting Simple Test Server")
    print("📍 No database - just AI processing!")
    print("🌐 URL: http://localhost:8000")
    print("🧪 Test endpoint: /api/process\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
