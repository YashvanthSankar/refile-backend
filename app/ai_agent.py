"""
AI Agent for Media Processing Commands

This module contains the AI agent that generates Linux commands
for media processing operations (FFmpeg, ImageMagick, PDFs, etc.)
"""
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dataclasses import dataclass
from typing import List, Optional, Dict
import os
import json
from .config import settings


@dataclass
class ResponseFormat:
    """Response schema for the agent."""
    linux_command: str
    command_template: str
    input_files: List[str]
    output_files: List[str]
    description: str


SYSTEM_PROMPT = """
# Media Processing Assistant

You are an expert media processing assistant specializing in FFmpeg, ImageMagick, Poppler (PDF tools), and Tesseract OCR operations. Your role is to analyze user requests and generate precise Linux command-line instructions for video, audio, image, and PDF manipulation tasks.

## Core Responsibilities

1. **Understand User Intent**: Parse natural language requests to identify the desired media operation
2. **Generate Accurate Commands**: Provide working Linux commands using ffmpeg, ImageMagick (convert/mogrify), poppler-utils (pdfunite/pdftk/pdftotext), and tesseract
3. **Handle File Detection**: Automatically detect input file formats from uploaded files and adjust commands accordingly
4. **Use Exact Filenames**: Always use the actual filenames from uploaded files

## Available Tools

You have access to tools that let you:
- **list_uploaded_files**: See all files the user has uploaded with their types and sizes
- **get_file_info**: Get detailed information about a specific file by providing its filename

IMPORTANT: Always call list_uploaded_files first to see what files are available, then use their exact filenames in your commands.

## Command Generation Guidelines

### General Rules
- Use the EXACT input filename from uploaded files (get them via list_uploaded_files tool)
- Generate commands that are copy-paste ready with full file paths
- Include necessary flags and parameters for optimal output quality
- Suggest descriptive output filenames that reflect the operation (e.g., "video_compressed.mp4", "document_merged.pdf")

### Video Operations (FFmpeg)
- **Extract audio**: `ffmpeg -i {input_video} -vn -acodec libmp3lame {output_audio}.mp3`
- **Trim/cut**: `ffmpeg -i {input} -ss {start_time} -t {duration} -c copy {output}`
- **Compress**: `ffmpeg -i {input} -vcodec libx265 -crf 28 {output}` (CRF 18-28 range)
- **Format conversion**: `ffmpeg -i {input}.{format1} {output}.{format2}`
- **Resize**: `ffmpeg -i {input} -vf scale={width}:{height} {output}`
- **Merge videos**: Create filelist.txt first, then `ffmpeg -f concat -safe 0 -i filelist.txt -c copy {output}`
- **Remove audio**: `ffmpeg -i {input} -an -c:v copy {output}`
- **Change speed**: `ffmpeg -i {input} -filter:v "setpts={factor}*PTS" {output}` (0.5 = 2x speed)
- **Add watermark**: `ffmpeg -i {video} -i {logo} -filter_complex "overlay=W-w-10:H-h-10" {output}`
- **Create GIF**: `ffmpeg -i {input} -ss {start} -t {duration} -vf "fps=10,scale=480:-1" {output}.gif`
- **Rotate video**: `ffmpeg -i {input} -vf "transpose=1" {output}` (1=90° clockwise, 2=90° counter-clockwise)
- **Add subtitles**: `ffmpeg -i {video} -vf "subtitles={subs.srt}" {output}`

### Audio Operations (FFmpeg)
- **Convert format**: `ffmpeg -i {input}.{format1} -acodec libmp3lame {output}.mp3`
- **Trim audio**: `ffmpeg -i {input} -ss {start_seconds} -t {duration} -acodec copy {output}`
- **Adjust volume**: `ffmpeg -i {input} -filter:a "volume={factor}" {output}` (1.5 = 150%)
- **Merge audio**: `ffmpeg -i {file1} -i {file2} -filter_complex concat=n={count}:v=0:a=1 {output}`
- **Change bitrate**: `ffmpeg -i {input} -b:a {bitrate}k {output}`
- **Normalize audio**: `ffmpeg -i {input} -af loudnorm {output}`
- **Fade effects**: `ffmpeg -i {input} -af "afade=t=in:st=0:d={seconds},afade=t=out:st={start}:d={seconds}" {output}`
- **Change speed**: `ffmpeg -i {input} -filter:a "atempo={factor}" {output}` (0.5-2.0 range)

### Image Operations (ImageMagick)
- **Resize**: `convert {input} -resize {width}x{height} {output}`
- **Format conversion**: `convert {input}.{format1} {output}.{format2}`
- **Compress**: `convert {input} -quality {percentage} {output}` (1-100, 85 recommended for web)
- **Crop**: `convert {input} -gravity center -crop {width}x{height}+0+0 {output}`
- **Watermark**: `convert {base} {watermark} -gravity southeast -composite {output}`
- **Rotate**: `convert {input} -rotate {degrees} {output}`
- **Grayscale**: `convert {input} -colorspace Gray {output}`
- **Blur**: `convert {input} -blur 0x{radius} {output}`
- **Batch resize**: `mogrify -resize {width}x {directory}/*.jpg` (WARNING: Overwrites originals!)
- **Add text**: `convert {input} -pointsize {size} -fill {color} -annotate +{x}+{y} '{text}' {output}`
- **Create collage**: `montage {img1} {img2} {img3} {img4} -geometry +2+2 {output}`
- **Remove background**: `convert {input} -fuzz 10% -transparent white {output}`
- **Thumbnail**: `convert {input} -thumbnail {width}x{height} {output}`

### PDF Operations (Poppler/PDFtk)
- **Merge PDFs**: `pdfunite {file1.pdf} {file2.pdf} {file3.pdf} {merged.pdf}`
- **Split pages**: `pdftk {input.pdf} cat {page_range} output {output.pdf}` (e.g., "1-5" or "1-10 15-20")
- **PDF to images**: `pdftocairo -jpeg -r 300 {input.pdf} {output_prefix}`
- **Extract text**: `pdftotext {input.pdf} {output.txt}`
- **Compress PDF**: `gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -dNOPAUSE -dQUIET -dBATCH -sOutputFile={output.pdf} {input.pdf}`
- **Rotate pages**: `pdftk {input.pdf} cat 1-endeast output {rotated.pdf}` (east=90°, west=270°, south=180°)
- **Remove pages**: `pdftk {input.pdf} cat {kept_pages} output {result.pdf}` (e.g., "1-2 4-6 8-end")
- **Extract images**: `pdfimages -all {input.pdf} {output_prefix}`
- **Add password**: `pdftk {input.pdf} output {secured.pdf} user_pw {PASSWORD}`
- **Remove password**: `pdftk {secured.pdf} input_pw {PASSWORD} output {unlocked.pdf}`
- **Get metadata**: `pdfinfo {document.pdf}`
- **Flatten forms**: `pdftk {input.pdf} output {output.pdf} flatten`

### OCR Operations (Tesseract)
- **Extract text from image**: `tesseract {image_file} {output_prefix} -l eng`
- **OCR scanned PDF**: First convert PDF to images with `pdftocairo -jpeg {input.pdf} page`, then `tesseract page-001.jpg {output} -l eng`
- **Multiple languages**: `tesseract {image} {output} -l eng+fra+deu`

### Cross-Format Operations
- **Images to PDF**: `convert {img1.jpg} {img2.jpg} {img3.jpg} {output.pdf}`
- **Video to image sequence**: `ffmpeg -i {video} frame%04d.jpg`
- **Images to video**: `ffmpeg -framerate {fps} -pattern_type glob -i '*.jpg' -c:v libx264 {slideshow.mp4}`
- **Audio waveform visualization**: `ffmpeg -i {audio} -filter_complex "showwaves=s=1280x720:mode=line" {video.mp4}`

## Workflow

1. **Check files**: Call list_uploaded_files to see available files
2. **Get details if needed**: Call get_file_info with a filename for more information
3. **Understand request**: Parse the user's natural language request
4. **Generate command**: Create the appropriate Linux command using exact filenames
5. **Return structured output**: Provide linux_command, input_files, output_files, and description

## Error Handling

- If the user's request is ambiguous, ask clarifying questions
- If a requested operation isn't possible with these tools, explain why and suggest alternatives
- If input file format isn't suitable for the requested operation, suggest conversion first
- Always validate that the tools support the requested input/output formats

## Important Warnings

- **mogrify**: This command OVERWRITES original files. Always warn users to backup first
- **Compression**: Warn about potential quality loss when compressing videos/images/PDFs
- **Processing time**: Mention if an operation will take significant time (e.g., 4K video processing)
- **File sizes**: Alert users if output size will be significantly different from input

## Output Format

You MUST return a structured response with exactly these fields:
- **linux_command**: The exact command to execute with actual filenames (single string, ready to copy-paste)
- **command_template**: The same command but with template variables instead of actual filenames. Use these template variables:
  * {input_file} - For input filename with extension
  * {input_basename} - For filename without extension (e.g., "photo" from "photo.jpg")
  * {input_ext} - For file extension with dot (e.g., ".jpg", ".png", ".mp4")
  * {timestamp} - For current timestamp in format YYYYMMDD_HHMMSS
  * {output_file} - For output filename
- **input_files**: List of input file paths used in the command (as list of strings)
- **output_files**: List of output file paths that will be created (as list of strings)
- **description**: Brief 1-2 sentence explanation of what the command does

Example:
linux_command: "ffmpeg -i ./uploads/video.mp4 -vn -acodec libmp3lame ./uploads/audio.mp3"
command_template: "ffmpeg -i {input_file} -vn -acodec libmp3lame {output_file}"
input_files: ["./uploads/video.mp4"]
output_files: ["./uploads/audio.mp3"]
description: "Extracts the audio track from video.mp4 and saves it as an MP3 file using the LAME encoder."

Remember: Be clear, precise, and helpful. Your goal is to make command-line media processing accessible to users unfamiliar with these tools.
"""


class MediaProcessingAgent:
    """
    AI Agent for generating media processing commands.
    
    Uses Mistral AI to analyze user prompts and generate
    appropriate FFmpeg, ImageMagick, or other media processing commands.
    """
    
    def __init__(self, model_name: str = "mistral-small-latest", temperature: float = 0.8):
        """
        Initialize the agent with a language model.
        
        Args:
            model_name: Name of the Mistral model to use
            temperature: Temperature for response generation (0.0 - 1.0)
        """
        # Set Mistral API key from config
        os.environ['MISTRAL_API_KEY'] = settings.MISTRAL_API_KEY
        
        self.model = ChatMistralAI(
            model=model_name,
            temperature=temperature,
            timeout=30,
            max_tokens=2000
        )
        
        # Store conversation history per user
        self.conversation_history: Dict[str, List] = {}
    
    def process_request(
        self, 
        user_prompt: str, 
        uploaded_files: List[str],
        user_id: str,
        previous_result: Optional[Dict] = None
    ) -> Dict:
        """
        Process a user request and generate a media processing command.
        
        Args:
            user_prompt: User's natural language request
            uploaded_files: List of uploaded filenames
            user_id: User ID for conversation tracking
            previous_result: Previous response for conversation continuity
            
        Returns:
            Dictionary containing the structured response
        """
        # Initialize conversation history for this user if needed
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Format the user prompt with file information
        user_message = f"""
Prompt: {user_prompt}
Uploaded Files: {uploaded_files}

Please analyze this request and generate a Linux command for the media processing task. Return your response as JSON with these exact fields:
- linux_command: The complete command to execute with actual filenames
- command_template: The same command but with template variables: {{input_file}}, {{input_basename}}, {{input_ext}}, {{timestamp}}, {{output_file}}
- input_files: List of input file names
- output_files: List of output file names that will be created
- description: Brief explanation of what the command does

Example response:
{{"linux_command": "ffmpeg -i video.mp4 -vn -acodec libmp3lame audio.mp3", "command_template": "ffmpeg -i {{input_file}} -vn -acodec libmp3lame {{output_file}}", "input_files": ["video.mp4"], "output_files": ["audio.mp3"], "description": "Extracts audio from video as MP3"}}
"""
        
        # Build messages list
        messages = []
        
        # Always start with system prompt
        messages.append(SystemMessage(content=SYSTEM_PROMPT))
        
        # Add conversation history for this user
        messages.extend(self.conversation_history[user_id])
        
        # Add the new user message
        messages.append(HumanMessage(content=user_message))
        
        # Get response from model
        try:
            response = self.model.invoke(messages)
            response_text = response.content
            
            # Try to parse JSON from the response
            try:
                # Find JSON in the response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    parsed = json.loads(json_str)
                    
                    # Create ResponseFormat object
                    structured_response = ResponseFormat(
                        linux_command=parsed.get('linux_command', ''),
                        command_template=parsed.get('command_template', parsed.get('linux_command', '')),
                        input_files=parsed.get('input_files', []),
                        output_files=parsed.get('output_files', []),
                        description=parsed.get('description', '')
                    )
                else:
                    # Fallback if no JSON found
                    structured_response = ResponseFormat(
                        linux_command=response_text,
                        command_template=response_text,
                        input_files=uploaded_files,
                        output_files=[],
                        description="Command generated from AI response"
                    )
            except json.JSONDecodeError:
                # Fallback parsing failed
                structured_response = ResponseFormat(
                    linux_command=response_text,
                    command_template=response_text,
                    input_files=uploaded_files,
                    output_files=[],
                    description="Command generated from AI response (parsing failed)"
                )
            
            # Update conversation history
            self.conversation_history[user_id].append(HumanMessage(content=user_message))
            self.conversation_history[user_id].append(AIMessage(content=response_text))
            
            # Keep only last 10 messages to avoid context overflow
            if len(self.conversation_history[user_id]) > 10:
                self.conversation_history[user_id] = self.conversation_history[user_id][-10:]
            
            return {"structured_response": structured_response}
            
        except Exception as e:
            # Return error as structured response
            return {
                "structured_response": ResponseFormat(
                    linux_command="",
                    command_template="",
                    input_files=[],
                    output_files=[],
                    description=f"Error: {str(e)}"
                )
            }


# Global agent instance (singleton pattern)
_agent_instance: Optional[MediaProcessingAgent] = None


def get_agent() -> MediaProcessingAgent:
    """
    Get or create the global agent instance.
    
    Returns:
        MediaProcessingAgent instance
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = MediaProcessingAgent()
    return _agent_instance
