"""Tests for RBAC model helpers and schema validation."""
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.identity import (
    OrganizationCreate,
    UserCreate,
)


# ---------------------------------------------------------------------------
# UserCreate schema validation
# ---------------------------------------------------------------------------

def test_user_create_valid():
    u = UserCreate(
        email="student@pharmlearn.ai",
        username="student_01",
        password="SecurePass1!",
        full_name="Alice Pharmacist",
    )
    assert u.email == "student@pharmlearn.ai"
    assert u.username == "student_01"


def test_user_create_missing_uppercase_in_password():
    with pytest.raises(ValidationError, match="uppercase"):
        UserCreate(email="a@b.com", username="user1", password="nouppercase1!")


def test_user_create_missing_digit_in_password():
    with pytest.raises(ValidationError, match="digit"):
        UserCreate(email="a@b.com", username="user1", password="NoDigitHere!")


def test_user_create_password_too_short():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", username="user1", password="Sh0rt!")


def test_user_create_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", username="user1", password="ValidPass1!")


def test_user_create_username_disallows_spaces():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", username="user name", password="ValidPass1!")


def test_user_create_username_too_short():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", username="ab", password="ValidPass1!")


# ---------------------------------------------------------------------------
# OrganizationCreate schema validation
# ---------------------------------------------------------------------------

def test_org_create_valid_types():
    for org_type in [
        "university",
        "pharmacy_chain",
        "hospital",
        "training_center",
        "enterprise",
        "individual_workspace",
    ]:
        org = OrganizationCreate(name="Test Org", slug="test-org", org_type=org_type)
        assert org.org_type == org_type


def test_org_create_invalid_type():
    with pytest.raises(ValidationError, match="org_type must be one of"):
        OrganizationCreate(name="Test", slug="test", org_type="invalid_type")


def test_org_create_slug_must_be_lowercase_hyphenated():
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Test", slug="UPPERCASE_SLUG", org_type="university")


def test_org_create_slug_valid():
    org = OrganizationCreate(name="City Pharmacy", slug="city-pharmacy-2024", org_type="pharmacy_chain")
    assert org.slug == "city-pharmacy-2024"


def test_org_create_name_too_short():
    with pytest.raises(ValidationError):
        OrganizationCreate(name="X", slug="valid-slug", org_type="university")


# ---------------------------------------------------------------------------
# Role hierarchy ordering (logical — no DB needed)
# ---------------------------------------------------------------------------

ROLE_HIERARCHY = [
    "student",
    "pharmacist",
    "educator",
    "content_reviewer",
    "institution_admin",
    "platform_admin",
]


def test_role_list_is_complete():
    assert len(ROLE_HIERARCHY) == 6


def test_platform_admin_is_last():
    assert ROLE_HIERARCHY[-1] == "platform_admin"


def test_student_is_first():
    assert ROLE_HIERARCHY[0] == "student"


def test_roles_are_unique():
    assert len(set(ROLE_HIERARCHY)) == len(ROLE_HIERARCHY)


# ---------------------------------------------------------------------------
# Org type set validation
# ---------------------------------------------------------------------------

from app.schemas.identity import ORG_TYPES  # noqa: E402


def test_org_types_count():
    assert len(ORG_TYPES) == 6


def test_individual_workspace_in_types():
    assert "individual_workspace" in ORG_TYPES


def test_all_expected_types_present():
    expected = {
        "university",
        "pharmacy_chain",
        "hospital",
        "training_center",
        "enterprise",
        "individual_workspace",
    }
    assert ORG_TYPES == expected
