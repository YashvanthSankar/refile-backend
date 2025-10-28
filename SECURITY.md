# 🔒 Security Implementation Guide

## Current Security Status

### ✅ Implemented Security Features

1. **Authentication Required**
   - All endpoints now require authentication via `x-user-id` header
   - Users must provide valid credentials to access any file operations

2. **User Access Control**
   - Users can ONLY access their own files
   - Attempting to access another user's files returns `403 Forbidden`

3. **Path Traversal Protection**
   - Filenames are sanitized to prevent `../` attacks
   - File paths are validated to ensure they stay within user folders

4. **UUID-Based Filenames**
   - Each file gets a globally unique identifier
   - Prevents filename collisions and guessing attacks

5. **User-Separated Storage**
   - Physical file separation: `user-uploads/{user_id}/`
   - Database records filtered by user_id

## How Authentication Works

### Current Implementation (Development Mode)

```bash
# Upload file - MUST include x-user-id header
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user123" \
  -F "prompt=Process this file" \
  -F "file=@document.pdf"

# Download file - user can only download their own files
curl http://localhost:8000/api/download/user123/550e8400.pdf \
  -H "x-user-id: user123"

# This will FAIL (403 Forbidden):
curl http://localhost:8000/api/download/user456/some-file.pdf \
  -H "x-user-id: user123"
```

### ⚠️ Production Requirement: JWT Tokens

For production, you MUST replace the `x-user-id` header with proper JWT authentication:

**Step 1:** Install JWT library
```bash
pip install pyjwt python-jose[cryptography]
```

**Step 2:** Update `app/security.py` to verify JWT tokens:

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key-here"  # Store in .env
ALGORITHM = "HS256"

async def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Step 3:** Frontend sends JWT token:
```javascript
// Frontend code
const response = await fetch('http://localhost:8000/api/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`  // JWT from login
  },
  body: formData
});
```

## Security Tests

### Test 1: Authentication Required ✅
```bash
# Without header - should FAIL
curl http://localhost:8000/api/list/user123
# Response: {"detail":"Authentication required. Missing x-user-id header."}
```

### Test 2: User Isolation ✅
```bash
# User123 trying to access user456's files - should FAIL
curl http://localhost:8000/api/list/user456 \
  -H "x-user-id: user123"
# Response: {"detail":"Access denied. You can only access your own files."}
```

### Test 3: Path Traversal Protection ✅
```bash
# Trying to escape user folder - should FAIL
curl http://localhost:8000/api/download/user123/../../../etc/passwd \
  -H "x-user-id: user123"
# Response: {"detail":"Invalid user_id format"}
```

### Test 4: Filename Sanitization ✅
```bash
# Malicious filename - should FAIL
curl http://localhost:8000/api/download/user123/../../secret.txt \
  -H "x-user-id: user123"
# Response: {"detail":"Invalid filename format"}
```

## Integration with Frontend

### React/Vue/Angular Example

```javascript
// Store user's token after login
localStorage.setItem('userToken', 'user123');  // Replace with real JWT

// Upload file
async function uploadFile(file, prompt) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('prompt', prompt);
  
  const response = await fetch('http://localhost:8000/api/upload', {
    method: 'POST',
    headers: {
      'x-user-id': localStorage.getItem('userToken')  // Dev mode
      // Production: 'Authorization': `Bearer ${localStorage.getItem('userToken')}`
    },
    body: formData
  });
  
  return await response.json();
}

// List user's files
async function listFiles() {
  const userId = localStorage.getItem('userToken');
  const response = await fetch(`http://localhost:8000/api/list/${userId}`, {
    headers: {
      'x-user-id': userId  // Dev mode
    }
  });
  
  return await response.json();
}
```

## Best Practices Checklist

- [x] All endpoints require authentication
- [x] Users can only access their own resources
- [x] Filenames are sanitized
- [x] Path traversal attacks prevented
- [x] UUID filenames prevent guessing
- [ ] JWT tokens (TODO: Add for production)
- [ ] Rate limiting (TODO: Add with slowapi)
- [ ] File size limits (TODO: Add validation)
- [ ] HTTPS only in production
- [ ] Supabase Row Level Security policies enabled

## Next Steps for Production

1. **Add JWT Authentication** (see above)
2. **Enable HTTPS**: Use nginx/Caddy with SSL certificates
3. **Add Rate Limiting**:
   ```bash
   pip install slowapi
   ```
4. **Enable Supabase RLS**: Run policies from `schema.sql`
5. **Add File Size Limits**: Prevent abuse
   ```python
   @app.post("/api/upload")
   async def upload_file(...):
       MAX_SIZE = 100 * 1024 * 1024  # 100MB
       content = await file.read()
       if len(content) > MAX_SIZE:
           raise HTTPException(400, "File too large")
   ```
6. **Add Logging**: Track suspicious activity
7. **Regular Security Audits**: Use tools like `bandit`, `safety`

## Testing Security

Run these commands to verify security is working:

```bash
# Should work (authenticated user)
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user123" \
  -F "prompt=test" \
  -F "file=@test.txt"

# Should fail (no auth)
curl http://localhost:8000/api/list/user123

# Should fail (wrong user)
curl http://localhost:8000/api/list/user456 \
  -H "x-user-id: user123"
```
