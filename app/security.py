"""
Security utilities for authentication and authorization.

This module provides JWT-based authentication and user verification.
"""
from fastapi import HTTPException, Header, Depends
from typing import Optional
import re

# TODO: Replace with actual JWT verification in production
# For now, this is a placeholder that accepts any user_id from headers

async def get_current_user(x_user_id: Optional[str] = Header(None)) -> str:
    """
    Extract and verify the current user from request headers.
    
    In production, this should:
    1. Verify JWT token from Authorization header
    2. Extract user_id from verified token
    3. Return the authenticated user_id
    
    For now, it accepts x-user-id header for development.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Missing x-user-id header."
        )
    
    # Validate user_id format (alphanumeric, hyphens, underscores only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', x_user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user_id format"
        )
    
    return x_user_id


def verify_user_access(requesting_user: str, resource_user: str):
    """
    Verify that the requesting user has access to the resource.
    
    Args:
        requesting_user: The authenticated user making the request
        resource_user: The user who owns the resource
    
    Raises:
        HTTPException: If access is denied
    """
    if requesting_user != resource_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied. You can only access your own files."
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename
        
    Raises:
        HTTPException: If filename contains invalid characters
    """
    # Remove any path separators
    filename = filename.replace('/', '').replace('\\', '').replace('..', '')
    
    # Only allow alphanumeric, hyphens, underscores, and dots
    if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename format"
        )
    
    return filename
