from enum import Enum

from fastapi import HTTPException, status


class UserRole(str, Enum):
    ADMIN = "admin"
    STRATEGIST = "strategist"
    APPROVER = "approver"
    VIEWER = "viewer"

def check_permission(user_role: str, allowed_roles: list[UserRole]):
    if user_role not in [role.value for role in allowed_roles]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted for current user role"
        )
