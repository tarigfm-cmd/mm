"""Schema umbrella — import from here; internal layout is an implementation detail."""

from app.schemas.content import (
    MaterialCreate,
    MaterialListItem,
    MaterialListResponse,
    MaterialResponse,
)
from app.schemas.identity import (
    LoginRequest,
    OrganizationCreate,
    OrganizationMembershipCreate,
    OrganizationMembershipRead,
    OrganizationRead,
    PermissionRead,
    RefreshRequest,
    RoleRead,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.schemas.learning import (
    InteractionCreate,
    InteractionResponse,
    ScenarioGenerateRequest,
    ScenarioInteractionsResponse,
    ScenarioListItem,
    ScenarioListResponse,
    ScenarioResponse,
)
from app.schemas.platform import HealthResponse, PaginatedResponse

__all__ = [
    # Platform
    "HealthResponse",
    "PaginatedResponse",
    # Content
    "MaterialCreate",
    "MaterialResponse",
    "MaterialListItem",
    "MaterialListResponse",
    # Learning
    "ScenarioGenerateRequest",
    "ScenarioResponse",
    "ScenarioListItem",
    "ScenarioListResponse",
    "InteractionCreate",
    "InteractionResponse",
    "ScenarioInteractionsResponse",
    # Identity / Auth
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "OrganizationCreate",
    "OrganizationRead",
    "OrganizationMembershipCreate",
    "OrganizationMembershipRead",
    "RoleRead",
    "PermissionRead",
]
