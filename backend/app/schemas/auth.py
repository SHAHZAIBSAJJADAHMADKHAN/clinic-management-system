from uuid import UUID

from pydantic import BaseModel

from app.models.roles import UserRole


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str | None = None


class Profile(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    role: UserRole
    is_active: bool
