"""
Startup script for the FastAPI application

Run this to start the server with AI agent integration.
"""
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting refile-backend with AI integration...")
    print("📝 API docs available at: http://localhost:8000/docs")
    print("🤖 AI agent ready for media processing commands")
    print("\nPress CTRL+C to stop the server\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
