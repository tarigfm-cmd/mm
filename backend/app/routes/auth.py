"""
Authentication endpoints: register, login, token refresh, profile.
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.database import get_db
from app.models.identity import PasswordResetToken, RefreshToken, User
from app.schemas.identity import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    PasswordChangeResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services.audit import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _prune_expired_tokens(user_id: uuid.UUID, db: AsyncSession) -> None:
    """Delete revoked or expired refresh tokens for one user."""
    now = datetime.now(timezone.utc)
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user_id,
            or_(
                RefreshToken.is_revoked.is_(True),
                RefreshToken.expires_at < now,
            ),
        )
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit("5/minute")
async def register(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    existing_email = await db.execute(select(User).where(User.email == body.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    existing_username = await db.execute(select(User).where(User.username == body.username))
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken.",
        )

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()  # populate user.id before audit log

    await log_action(
        db,
        action="user.register",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"email": body.email, "username": body.username},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
@limiter.limit("10/minute")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None or not verify_password(body.password, user.hashed_password):
        raise invalid
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    settings = get_settings()
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days),
        device_info=request.headers.get("User-Agent", "")[:500],
    )
    db.add(rt)

    await log_action(
        db,
        action="user.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    await _prune_expired_tokens(user.id, db)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for new tokens",
)
@limiter.limit("20/minute")
async def refresh_tokens(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        claims = decode_token(body.refresh_token)
        if claims.get("type") != "refresh":
            raise invalid
        user_id = uuid.UUID(claims["sub"])
    except (ValueError, KeyError):
        raise invalid

    token_hash = hash_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        raise invalid

    stored.is_revoked = True

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise invalid

    settings = get_settings()
    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(new_rt)

    await log_action(
        db,
        action="auth.token_refresh",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
    )
    await _prune_expired_tokens(user.id, db)
    await db.commit()

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the current authenticated user's profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update the current user's profile",
)
async def update_me(
    body: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    if body.username is not None and body.username != current_user.username:
        existing = await db.execute(select(User).where(User.username == body.username))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already taken.",
            )
        current_user.username = body.username

    if body.full_name is not None:
        current_user.full_name = body.full_name

    await db.commit()
    await db.refresh(current_user)
    return UserRead.model_validate(current_user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    body: RefreshRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    token_hash = hash_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == current_user.id,
        )
    )
    stored = result.scalar_one_or_none()
    if stored:
        stored.is_revoked = True

    await log_action(
        db,
        action="user.logout",
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password reset link",
)
@limiter.limit("3/minute")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    generic_message = (
        "If an account exists with that email, password reset instructions have been sent."
    )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return ForgotPasswordResponse(message=generic_message)

    # Latest-only policy: invalidate all previous unused tokens for this user
    await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )

    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )
    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
        request_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent", "")[:500],
    )
    db.add(prt)
    await db.commit()

    reset_url = f"{settings.app_public_url}/reset-password?token={raw_token}"

    if settings.expose_reset_token_in_dev:
        return ForgotPasswordResponse(message=generic_message, reset_url=reset_url)

    logger.info(
        "Password reset token created for user_id=%s expires=%s", user.id, expires_at
    )
    return ForgotPasswordResponse(message=generic_message)


@router.post(
    "/reset-password",
    response_model=PasswordChangeResponse,
    summary="Reset password using a valid reset token",
)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> PasswordChangeResponse:
    invalid_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired password reset token.",
    )

    token_hash = hash_token(body.token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    prt = result.scalar_one_or_none()

    if prt is None or prt.used_at is not None or prt.expires_at.replace(tzinfo=timezone.utc) < now:
        raise invalid_error

    user = await db.get(User, prt.user_id)
    if user is None or not user.is_active:
        raise invalid_error

    user.hashed_password = hash_password(body.new_password)
    prt.used_at = now

    # Revoke all refresh tokens for this user
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True)
    )

    await log_action(
        db,
        action="user.password_reset",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
    )
    await db.commit()

    return PasswordChangeResponse(
        message="Password has been reset. You can now sign in with your new password."
    )


@router.post(
    "/change-password",
    response_model=PasswordChangeResponse,
    summary="Change password while authenticated",
)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PasswordChangeResponse:
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if verify_password(body.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password.",
        )

    current_user.hashed_password = hash_password(body.new_password)

    # Revoke all active refresh tokens (forces re-login on other devices)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True)
    )

    await log_action(
        db,
        action="user.password_changed",
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
    )
    await db.commit()

    return PasswordChangeResponse(message="Password changed successfully.")
