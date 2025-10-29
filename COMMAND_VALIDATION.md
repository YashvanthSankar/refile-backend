# Command Validation Fix

## Problem
The AI was generating incomplete commands, specifically for PDF operations using `pdftocairo`. The command was being executed without required arguments, causing the tool to display its help message instead of processing files.

**Error Example:**
```
AI Processing failed: Docker command failed: pdftocairo version 24.02.0
Copyright 2005-2024 The Poppler Developers...
Usage: pdftocairo [options] <PDF-file> [<output-file>]
```

This indicated the command was run as just `pdftocairo` without any arguments.

## Root Cause
The AI agent (using Groq's llama-3.3-70b-versatile model) occasionally generated incomplete commands that lacked:
- Required format flags (e.g., `-jpeg`, `-png` for `pdftocairo`)
- Input file arguments
- Output file arguments

## Solution Implemented

### 1. Command Validation Function (`app/main.py`)
Added a `validate_command()` function that checks commands before Docker execution:

```python
def validate_command(command: str) -> tuple[bool, str]:
    """
    Validate that a command has proper arguments and is not just showing help.
    """
```

**Validation Rules:**
- **pdftocairo**: Must have format flag (-png, -jpeg, -pdf, etc.) AND at least 2 non-flag arguments (input PDF + output)
- **ffmpeg**: Must have `-i` input flag
- **convert/mogrify**: Must have at least one argument after command name
- **tesseract**: Must have both input and output arguments

**Example Validations:**
- ✗ `pdftocairo` → FAIL: "missing output format flag"
- ✗ `pdftocairo -jpeg document.pdf` → FAIL: "missing output file"
- ✓ `pdftocairo -jpeg document.pdf output` → PASS
- ✓ `pdftocairo -png -r 300 test.pdf page` → PASS

### 2. Enhanced AI System Prompt (`app/ai_agent.py`)
Updated the system prompt with stronger validation guidance:

**Added Critical Guidelines:**
```
- **CRITICAL**: Always include ALL required arguments - never generate incomplete commands
- **VALIDATION**: Before returning a command, verify it has:
  1. The base command
  2. ALL required input files or flags
  3. ALL required output files or parameters
  4. Any mandatory format flags
```

**Improved PDF Documentation:**
```python
- **PDF to images**: `pdftocairo -jpeg -r 300 {input.pdf} {output_prefix}` 
  - IMPORTANT: pdftocairo requires BOTH a format flag (-jpeg, -png, -pdf, -svg) AND input/output files
  - Example: `pdftocairo -jpeg -r 300 document.pdf page` creates page-001.jpg, page-002.jpg
```

**Error Prevention Rules:**
```
- Never return a command with just the tool name (e.g., "pdftocairo" alone)
- Always include format flags for PDF tools
- Always include input AND output files for conversion tools
- If unsure about arguments, ask the user for clarification
```

### 3. Pre-Execution Validation
Integrated validation into the Docker execution pipeline:

```python
def execute_command_in_docker(user_dir: Path, linux_command: str, input_files: List[str]):
    # Validate command before execution
    is_valid, error_msg = validate_command(linux_command)
    if not is_valid:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid command: {error_msg}. The AI may have generated an incomplete command."
        )
    # ... proceed with Docker execution
```

## Benefits

1. **Early Error Detection**: Catches incomplete commands before Docker execution
2. **Better Error Messages**: Users get clear feedback about what's wrong
3. **AI Guidance**: Enhanced prompts help the AI generate complete commands
4. **Prevention**: Multiple layers prevent incomplete commands from reaching execution

## User Experience Improvements

**Before Fix:**
```
Error: Docker command failed: pdftocairo version 24.02.0...
[Long help message]
```

**After Fix:**
```
Error: Invalid command: pdftocairo command missing output format flag (-png, -jpeg, -pdf, etc.).
The AI may have generated an incomplete command. Please try rephrasing your request.
```

## Testing

Created `test_validation.py` with comprehensive test cases:
- ✓ All 8 test cases pass
- Validates various command patterns
- Tests both valid and invalid commands

## Files Modified

1. **`app/main.py`**:
   - Added `validate_command()` function (60 lines)
   - Integrated validation into `execute_command_in_docker()`
   - Better error messages for users

2. **`app/ai_agent.py`**:
   - Enhanced system prompt with validation guidelines
   - Improved PDF command documentation
   - Added critical error prevention rules

3. **`test_validation.py`** (NEW):
   - Test suite for validation logic
   - 8 test cases covering common scenarios

## Future Enhancements

- [ ] Add validation for more complex commands (pipes, redirects)
- [ ] Validate file existence before execution
- [ ] Add command complexity scoring
- [ ] Implement command sanitization for security
- [ ] Add automatic command correction suggestions
- [ ] Track common AI generation failures for prompt tuning

## Related Issues

This fix addresses the broader issue of ensuring AI-generated commands are complete and executable. It provides a safety net for any command-generation failures, not just PDF operations.
