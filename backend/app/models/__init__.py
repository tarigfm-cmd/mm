"""Domain models — import from here to keep routes decoupled from file layout."""

from app.models.content import Material
from app.models.identity import (
    AuditLog,
    Organization,
    OrganizationMembership,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
)
from app.models.governance import (
    ApprovalBatch,
    ClinicalReview,
    ContentItem,
    ContentVersion,
    EvidenceSource,
    LearnerFailureAnalytics,
    PublicationRecord,
    RegionPublishingRule,
)
from app.models.learning import Interaction, Scenario

__all__ = [
    # Content
    "Material",
    # Learning
    "Scenario",
    "Interaction",
    # Identity / RBAC
    "User",
    "Organization",
    "OrganizationMembership",
    "Role",
    "Permission",
    "RolePermission",
    "RefreshToken",
    "AuditLog",
    # Governance
    "ContentItem",
    "ContentVersion",
    "EvidenceSource",
    "ApprovalBatch",
    "ClinicalReview",
    "RegionPublishingRule",
    "PublicationRecord",
    "LearnerFailureAnalytics",
]
