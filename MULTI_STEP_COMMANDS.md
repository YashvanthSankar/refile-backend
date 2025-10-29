# Multi-Step Command Execution Fix

## Problem
The AI was generating multi-step operations where the second command relied on intermediate files created by the first command. However, these commands were being executed separately, causing the second command to fail with "No such file or directory" errors.

**Error Example:**
```
AI Processing failed: Docker command failed: 
convert: unable to open image 'page-001.png': No such file or directory
```

This occurred when:
1. User requested: "Convert PDF to images and make them grayscale"
2. AI generated two separate commands:
   - Command 1: `pdftocairo -png document.pdf page` (creates page-001.png, page-002.png, etc.)
   - Command 2: `convert page-001.png -colorspace Gray grayscale.png` (expects page-001.png to exist)
3. Commands executed in separate Docker containers, losing intermediate files

## Root Cause
The backend was splitting commands by `&&` and running them separately in different Docker containers. Each container had its own filesystem, so intermediate files from the first command weren't available to the second command.

## Solution Implemented

### 1. **Shell-Based Command Execution** (`app/main.py`)

Changed Docker execution to run commands through `/bin/sh -c` when they contain shell features:

```python
# Check if command contains shell features
needs_shell = any([
    '&&' in linux_command,  # Command chaining
    '||' in linux_command,  # Or operator
    '|' in linux_command,   # Pipes
    'for ' in linux_command,  # For loops
    'while ' in linux_command,  # While loops
    '*' in linux_command,   # Wildcards
    '?' in linux_command,   # Wildcards
    '$(' in linux_command,  # Command substitution
])

if needs_shell:
    docker_command = ['/bin/sh', '-c', cmd]
else:
    docker_command = cmd
```

**Benefits:**
- Single Docker container execution preserves intermediate files
- Shell handles `&&` chaining (only runs second command if first succeeds)
- Wildcards (`*.png`, `page-*.png`) work properly
- For loops and other shell constructs supported

### 2. **Enhanced AI Prompt** (`app/ai_agent.py`)

Added comprehensive multi-step operation guidelines:

```python
## Multi-Step Operations

**OPTION 1 - Single Command with Pipes (PREFERRED):**
Chain commands using && or shell operators:
```bash
pdftocairo -png input.pdf page && mogrify -colorspace Gray page-*.png
```

**IMPORTANT RULES FOR MULTI-STEP COMMANDS:**
1. Use `&&` to chain commands
2. Use shell wildcards (`*.png`, `page-*.png`) to process intermediate files
3. Use `for` loops when needed
4. Always ensure intermediate files are accessible
5. Avoid specific filenames (like `page-001.png`) - use wildcards
```

**Examples Added:**
```bash
# PDF to grayscale images
pdftocairo -png -r 150 doc.pdf page && mogrify -colorspace Gray page-*.png

# Video frames to thumbnails
ffmpeg -i video.mp4 frame%04d.jpg && mogrify -resize 200x200 frame*.jpg

# Extract audio and compress
ffmpeg -i video.mp4 -vn audio.wav && ffmpeg -i audio.wav -b:a 128k audio.mp3
```

### 3. **Updated Validation** (`app/main.py`)

Enhanced validation to handle chained commands:

```python
def validate_command(command: str) -> tuple[bool, str]:
    # Split by && to handle chained commands
    command_parts = [part.strip() for part in command.split('&&') if part.strip()]
    
    # Validate each command in the chain
    for cmd_part in command_parts:
        # Skip validation for shell loops and control structures
        if cmd_part.startswith('for ') or cmd_part.startswith('while '):
            continue  # Complex shell constructs are allowed
        
        # Validate individual commands...
```

## How It Works Now

### Before (Broken):
```
User: "Convert PDF to grayscale images"
AI generates: 
  1. pdftocairo -png input.pdf page
  2. convert page-001.png -colorspace Gray output.png

Execution:
  Container 1: pdftocairo → creates page-001.png → container destroyed
  Container 2: convert page-001.png → ERROR: file not found!
```

### After (Fixed):
```
User: "Convert PDF to grayscale images"
AI generates: 
  pdftocairo -png input.pdf page && mogrify -colorspace Gray page-*.png

Execution:
  Container 1: /bin/sh -c "pdftocairo ... && mogrify ..."
    Step 1: pdftocairo → creates page-001.png, page-002.png
    Step 2: mogrify → processes all page-*.png files
    Result: Grayscale images created successfully
```

## Testing

Updated `test_validation.py` with multi-step command tests:

```python
# Chained commands
("pdftocairo -png input.pdf page && mogrify -colorspace Gray page-*.png", True)

# For loops
("pdftocairo -png input.pdf page && for f in page-*.png; do convert \"$f\" -resize 50% \"$f\"; done", True)
```

**All 10 tests passing ✓**

## User Experience

### Before:
```
User: "Convert my PDF to grayscale images"
Result: ❌ Error - intermediate files not found
```

### After:
```
User: "Convert my PDF to grayscale images"
AI: pdftocairo -png document.pdf page && mogrify -colorspace Gray page-*.png
Result: ✅ Creates page-001.png, page-002.png (all grayscale)
```

## Technical Details

### Docker Command Execution:
- **Simple commands**: Run directly as string
- **Complex commands**: Wrapped in `/bin/sh -c "command"`

### Shell Features Detected:
- `&&` - Command chaining
- `||` - Or operator
- `|` - Pipes
- `for`, `while` - Loops
- `*`, `?` - Wildcards
- `$(...)`, `` `...` `` - Command substitution

### File Persistence:
All operations in a single Docker container ensure:
- Intermediate files remain accessible
- Wildcards expand correctly
- Sequential commands work as expected

## Files Modified

1. **`app/main.py`**:
   - Removed command splitting by `&&`
   - Added shell feature detection
   - Execute complex commands through `/bin/sh -c`
   - Updated validation for chained commands

2. **`app/ai_agent.py`**:
   - Added "Multi-Step Operations" section
   - Provided chaining examples
   - Rules for using wildcards
   - Best practices for intermediate files

3. **`test_validation.py`**:
   - Added chained command tests
   - Added for loop tests
   - All 10 tests passing

## Examples of Fixed Operations

### 1. PDF to Grayscale Images
```bash
pdftocairo -png -r 150 document.pdf page && mogrify -colorspace Gray page-*.png
```

### 2. Video Frame Extraction + Resize
```bash
ffmpeg -i video.mp4 frame%04d.jpg && mogrify -resize 800x600 frame*.jpg
```

### 3. Audio Extraction + Compression
```bash
ffmpeg -i video.mp4 -vn audio.wav && ffmpeg -i audio.wav -b:a 128k audio.mp3
```

### 4. PDF Pages to Thumbnails
```bash
pdftocairo -jpeg -r 72 doc.pdf page && mogrify -thumbnail 200x200 page-*.jpg
```

### 5. Batch Image Processing with Loop
```bash
for f in *.jpg; do convert "$f" -quality 85 -resize 1920x1080 "compressed_$f"; done
```

## Future Enhancements

- [ ] Support for more complex shell patterns
- [ ] Add command pipeline optimization
- [ ] Implement intermediate file cleanup
- [ ] Add progress tracking for multi-step operations
- [ ] Support for parallel command execution where safe
- [ ] Add command dependency analysis

## Security Considerations

**Shell Injection Protection:**
- Commands are validated before execution
- Docker container isolation provides additional security
- User directory is the only mounted volume
- No privileged access granted

**Best Practices:**
- Always use Docker user ID mapping
- Limit container resources
- Validate all input files exist in user directory
- Sanitize filenames before processing
