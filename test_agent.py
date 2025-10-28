"""
Test script for the AI agent integration

This script tests the MediaProcessingAgent without running the full FastAPI app.
"""
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.ai_agent import MediaProcessingAgent

def test_agent():
    """Test the AI agent with a simple request."""
    print("Initializing AI agent...")
    agent = MediaProcessingAgent()
    
    print("\nTest 1: Extract audio from video")
    print("-" * 50)
    
    response = agent.process_request(
        user_prompt="Extract audio from the video as MP3",
        uploaded_files=["wedding_video.mp4"],
        user_id="test_user_1",
        previous_result=None
    )
    
    if 'structured_response' in response:
        resp = response['structured_response']
        print(f"Command: {resp.linux_command}")
        print(f"Input files: {resp.input_files}")
        print(f"Output files: {resp.output_files}")
        print(f"Description: {resp.description}")
    else:
        print(f"Response: {response}")
    
    print("\n" + "=" * 50)
    print("Test 2: Follow-up request (convert to WAV)")
    print("-" * 50)
    
    # Use the previous response for context
    response2 = agent.process_request(
        user_prompt="Can you convert that audio to WAV format?",
        uploaded_files=["wedding_video.mp4"],
        user_id="test_user_1",
        previous_result=response
    )
    
    if 'structured_response' in response2:
        resp2 = response2['structured_response']
        print(f"Command: {resp2.linux_command}")
        print(f"Input files: {resp2.input_files}")
        print(f"Output files: {resp2.output_files}")
        print(f"Description: {resp2.description}")
    else:
        print(f"Response: {response2}")

if __name__ == "__main__":
    try:
        test_agent()
        print("\n✅ Agent test completed successfully!")
    except Exception as e:
        print(f"\n❌ Agent test failed: {e}")
        import traceback
        traceback.print_exc()
