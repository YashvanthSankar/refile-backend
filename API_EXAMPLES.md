# refile Backend API Examples

## ⚠️ Security Update

**All endpoints now require authentication!** You must include the `x-user-id` header with every request.

In production, replace this with JWT tokens in the `Authorization: Bearer <token>` header.

## Prerequisites

1. Start the server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Make sure you have a `.env` file with Supabase credentials (copy from `.env.example`)

## API Endpoints

### 1. Health Check

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"status": "ok"}
```

### 2. Upload File with Prompt

**Important:** User is now determined by authentication header, not form field.

```bash
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user123" \
  -F "prompt=Extract text from this image" \
  -F "file=@/path/to/your/file.jpg"
```

Example with a test file:
```bash
# Create a test file first
echo "Hello World" > test.txt

# Upload it (notice: no user_id in form data, only in header)
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user123" \
  -F "prompt=Convert this text file to uppercase" \
  -F "file=@test.txt"
```

Expected response:
```json
{
  "status": "ok",
  "file": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "original_filename": "test.txt",
    "stored_filename": "550e8400-e29b-41d4-a716-446655440000.txt",
    "content_type": "text/plain",
    "path": "./user-uploads/user123/550e8400-e29b-41d4-a716-446655440000.txt"
  },
  "prompt_record": [{
    "id": "...",
    "user_id": "user123",
    "prompt": "Convert this text file to uppercase",
    "original_filename": "test.txt",
    "stored_filename": "550e8400-e29b-41d4-a716-446655440000.txt",
    "content_type": "text/plain",
    "created_at": "2025-10-28T..."
  }],
  "ai_response": null
}
```

### 3. List User's Files and Prompts

**Security:** You can only list your own files (determined by x-user-id header).

```bash
curl http://localhost:8000/api/list/user123 \
  -H "x-user-id: user123"
```

Trying to access another user's files will fail:
```bash
# This returns 403 Forbidden
curl http://localhost:8000/api/list/user456 \
  -H "x-user-id: user123"
```

Expected response:
```json
{
  "status": "ok",
  "items": [
    {
      "id": "...",
      "user_id": "user123",
      "prompt": "Convert this text file to uppercase",
      "original_filename": "test.txt",
      "stored_filename": "550e8400-e29b-41d4-a716-446655440000.txt",
      "content_type": "text/plain",
      "created_at": "2025-10-28T..."
    }
  ]
}
```

### 4. Download a File

**Security:** You can only download your own files.

```bash
curl http://localhost:8000/api/download/user123/550e8400-e29b-41d4-a716-446655440000.txt \
  -H "x-user-id: user123" \
  -o downloaded_file.txt
```

Or open in browser (will need authentication in production):
```
http://localhost:8000/api/download/user123/550e8400-e29b-41d4-a716-446655440000.txt
```

**Security Test - This will FAIL:**
```bash
# Trying to download another user's file
curl http://localhost:8000/api/download/user456/some-file.pdf \
  -H "x-user-id: user123"
# Response: {"detail":"Access denied. You can only access your own files."}
```

## Testing Different File Types

### Upload an image
```bash
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user456" \
  -F "prompt=Extract text using OCR" \
  -F "file=@image.png"
```

### Upload a video
```bash
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user456" \
  -F "prompt=Extract audio from this video" \
  -F "file=@video.mp4"
```

### Upload a PDF
```bash
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user456" \
  -F "prompt=Convert PDF to images" \
  -F "file=@document.pdf"
```

## Security Features

### ✅ What's Protected

1. **Authentication Required**: All endpoints need `x-user-id` header
2. **User Isolation**: Users can only access their own files
3. **Path Traversal Protection**: Malicious filenames are blocked
4. **UUID Filenames**: Prevents guessing attacks

### 🔒 Security Tests

```bash
# Test 1: Missing authentication - FAILS
curl http://localhost:8000/api/list/user123
# {"detail":"Authentication required. Missing x-user-id header."}

# Test 2: Access control - FAILS
curl http://localhost:8000/api/list/user456 -H "x-user-id: user123"
# {"detail":"Access denied. You can only access your own files."}

# Test 3: Path traversal - FAILS
curl http://localhost:8000/api/download/user123/../../../etc/passwd -H "x-user-id: user123"
# {"detail":"Invalid user_id format"}
```

## Notes

- **Authentication is now REQUIRED** - all requests must include `x-user-id` header
- Users can **only access their own files** - access control is enforced
- The `stored_filename` is a UUID + original extension to avoid collisions
- Files are stored in `user-uploads/{user_id}/` directory structure
- The `ai_response` field is currently null; you'll add AI processing later
- For **production**, replace `x-user-id` with JWT tokens (see SECURITY.md)
