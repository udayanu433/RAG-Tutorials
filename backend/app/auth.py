from fastapi import Header, HTTPException, status, Depends

# Mock Credentials Database
MOCK_CREDENTIALS = {
    "student": {"password": "student123", "role": "Student"},
    "faculty": {"password": "faculty123", "role": "Faculty"},
    "admin": {"password": "admin123", "role": "Admin"}
}

# Simple Token mapping for on-premise authentication simulation
TOKEN_TO_ROLE = {
    "token-student-session-key-2026": "Student",
    "token-faculty-session-key-2026": "Faculty",
    "token-admin-session-key-2026": "Admin"
}

# Reverse mapping to generate token upon login
ROLE_TO_TOKEN = {v: k for k, v in TOKEN_TO_ROLE.items()}

def get_current_role(authorization: str = Header(None)) -> str:
    """
    Validates the Bearer token in the Authorization header and returns the associated role.
    """
    if not authorization:
        # Default to lowest clearance if no header is present
        return "Student"
        
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Must use Bearer token."
        )
        
    token = authorization.split(" ")[1]
    if token not in TOKEN_TO_ROLE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid credentials."
        )
        
    return TOKEN_TO_ROLE[token]

def require_role(allowed_roles: list):
    """
    FastAPI dependency factory to enforce RBAC on specific endpoints using the token.
    """
    def dependency(role: str = Depends(get_current_role)):
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Access denied. Role '{role}' does not have permission. Required roles: {allowed_roles}."
            )
        return role
    return dependency
