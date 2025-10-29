#!/usr/bin/env python3
"""
Test script for command validation
"""

def validate_command(command: str) -> tuple[bool, str]:
    """
    Validate that a command has proper arguments and is not just showing help.
    
    Args:
        command: The Linux command to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    command = command.strip()
    
    # Check if command is empty
    if not command:
        return False, "Command is empty"
    
    # Split command to get the base command and arguments
    parts = command.split()
    if len(parts) == 0:
        return False, "Command has no parts"
    
    base_cmd = parts[0]
    
    # Commands that require specific arguments
    commands_needing_args = {
        'pdftocairo': ['input.pdf', 'output'],  # Needs input PDF and output prefix/file
        'pdftotext': ['input.pdf'],  # Needs input PDF
        'pdfimages': ['input.pdf', 'prefix'],  # Needs input PDF and prefix
        'pdfinfo': ['input.pdf'],  # Needs input PDF
        'ffmpeg': ['-i'],  # Needs input file flag
        'convert': ['input'],  # ImageMagick needs input file
        'mogrify': ['input'],  # ImageMagick needs input file
        'tesseract': ['input', 'output'],  # Needs input and output
    }
    
    # Check if this command requires arguments
    if base_cmd in commands_needing_args:
        # For pdftocairo specifically, check for output format flags
        if base_cmd == 'pdftocairo':
            has_format = any(flag in command for flag in ['-png', '-jpeg', '-pdf', '-svg', '-tiff', '-ps', '-eps'])
            if not has_format:
                return False, f"pdftocairo command missing output format flag (-png, -jpeg, -pdf, etc.)"
            
            # Check for input/output files (at least 2 arguments after flags)
            non_flag_args = [p for p in parts[1:] if not p.startswith('-')]
            if len(non_flag_args) < 2:
                return False, f"pdftocairo command missing input PDF and/or output file arguments"
        
        # For ffmpeg, check for -i flag
        elif base_cmd == 'ffmpeg':
            if '-i' not in command:
                return False, "ffmpeg command missing -i input file flag"
        
        # Generic check for minimum number of arguments
        elif len(parts) < 2:
            return False, f"{base_cmd} command appears to be missing required arguments"
    
    return True, ""


# Test cases
test_commands = [
    ("pdftocairo", False, "Should fail - no format flag or files"),
    ("pdftocairo -jpeg", False, "Should fail - missing input/output files"),
    ("pdftocairo -jpeg document.pdf", False, "Should fail - missing output file"),
    ("pdftocairo -jpeg document.pdf output", True, "Should pass - complete command"),
    ("pdftocairo -png -r 300 test.pdf page", True, "Should pass - with resolution"),
    ("ffmpeg", False, "Should fail - no -i flag"),
    ("ffmpeg -i video.mp4 output.mp3", True, "Should pass - complete ffmpeg"),
    ("convert input.jpg output.png", True, "Should pass - imagemagick"),
    ("pdftocairo -png input.pdf page && mogrify -colorspace Gray page-*.png", True, "Should pass - chained commands"),
    ("pdftocairo -png input.pdf page && for f in page-*.png; do convert \"$f\" -resize 50% \"$f\"; done", True, "Should pass - with for loop"),
]

print("Testing command validation...\n")
for cmd, should_pass, description in test_commands:
    is_valid, error_msg = validate_command(cmd)
    status = "✓ PASS" if is_valid == should_pass else "✗ FAIL"
    print(f"{status}: {description}")
    print(f"  Command: {cmd}")
    print(f"  Valid: {is_valid}, Error: {error_msg}")
    print()
