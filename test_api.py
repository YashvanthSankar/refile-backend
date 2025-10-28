"""
Test client for the FastAPI application

This script tests the /api/upload endpoint with AI integration.
"""
import requests
import json
import io

# Configuration
BASE_URL = "http://localhost:8000"
USER_ID = "test_user_123"

def test_health():
    """Test the health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"✅ Health check: {response.json()}\n")

def test_upload_with_ai():
    """Test file upload with AI processing."""
    print("Testing file upload with AI processing...")
    
    # Create a dummy file
    dummy_file = io.BytesIO(b"dummy video content")
    dummy_file.name = "wedding_video.mp4"
    
    # Prepare the request
    files = {
        'file': ('wedding_video.mp4', dummy_file, 'video/mp4')
    }
    data = {
        'prompt': 'Extract audio from the video as MP3'
    }
    headers = {
        'x-user-id': USER_ID
    }
    
    # Send request
    try:
        response = requests.post(
            f"{BASE_URL}/api/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Upload successful!")
            print(f"\nFile info:")
            print(f"  - Original filename: {result['file']['original_filename']}")
            print(f"  - Stored as: {result['file']['stored_filename']}")
            
            print(f"\n🤖 AI Response:")
            ai_resp = result['ai_response']
            print(f"  - Command: {ai_resp['linux_command']}")
            print(f"  - Input files: {ai_resp['input_files']}")
            print(f"  - Output files: {ai_resp['output_files']}")
            print(f"  - Description: {ai_resp['description']}")
            
            return result
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def test_followup(previous_result):
    """Test follow-up AI request."""
    if not previous_result:
        print("\n⏭️  Skipping follow-up test (no previous result)")
        return
    
    print("\n" + "="*60)
    print("Testing follow-up AI request...")
    
    ai_resp = previous_result['ai_response']
    
    data = {
        'prompt': 'Convert that audio to WAV format',
        'uploaded_files': json.dumps(["wedding_video.mp4"]),
        'previous_command': ai_resp['linux_command'],
        'previous_input_files': json.dumps(ai_resp['input_files']),
        'previous_output_files': json.dumps(ai_resp['output_files']),
        'previous_description': ai_resp['description']
    }
    headers = {
        'x-user-id': USER_ID
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/process",
            data=data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Follow-up successful!")
            
            print(f"\n🤖 AI Response:")
            ai_resp = result['ai_response']
            print(f"  - Command: {ai_resp['linux_command']}")
            print(f"  - Input files: {ai_resp['input_files']}")
            print(f"  - Output files: {ai_resp['output_files']}")
            print(f"  - Description: {ai_resp['description']}")
        else:
            print(f"❌ Follow-up failed: {response.status_code}")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    print("="*60)
    print("🧪 Testing FastAPI Application with AI Integration")
    print("="*60 + "\n")
    
    # Test health endpoint
    test_health()
    
    # Test upload with AI
    print("="*60)
    result = test_upload_with_ai()
    
    # Test follow-up
    test_followup(result)
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
