from collections.abc import Sequence
from enum import Enum

from fastapi import HTTPException, status


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.ADMIN: 4,
    UserRole.EDITOR: 3,
    UserRole.OPERATOR: 2,
    UserRole.VIEWER: 1,
}


def normalize_role(role: str | UserRole) -> UserRole:
    if isinstance(role, UserRole):
        return role
    val = role.lower()
    alias_map = {
        "strategist": UserRole.EDITOR,
        "approver": UserRole.OPERATOR,
    }
    if val in alias_map:
        return alias_map[val]
    try:
        return UserRole(val)
    except ValueError:
        return UserRole.VIEWER


def has_role(user_role: str | UserRole, minimum_role: str | UserRole) -> bool:
    user_norm = normalize_role(user_role)
    min_norm = normalize_role(minimum_role)
    return ROLE_HIERARCHY[user_norm] >= ROLE_HIERARCHY[min_norm]


def check_permission(
    user_role: str | UserRole,
    allowed_roles: Sequence[str | UserRole] | None = None,
    minimum_role: str | UserRole | None = None,
) -> None:
    if minimum_role is not None:
        if not has_role(user_role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires minimum role '{minimum_role}', user has '{user_role}'",
            )
        return

    if allowed_roles:
        norm_user = normalize_role(user_role)
        norm_allowed = [normalize_role(r) for r in allowed_roles]
        if norm_user not in norm_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for current user role",
            )
