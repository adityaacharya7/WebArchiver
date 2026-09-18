"""
Authentication endpoints for Google OAuth 2.0 and Session Management.
"""
import secrets
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import User, utc_now

logger = logging.getLogger("archiver_auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE_NAME = "archiver_session"
SESSION_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days


def get_callback_url(request: Request) -> str:
    """Determine the OAuth callback URL dynamically or from configuration."""
    if settings.AUTH_REDIRECT_URI:
        return settings.AUTH_REDIRECT_URI
    
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{forwarded_proto}://{host}/api/auth/google/callback"


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Retrieve currently authenticated user from session cookie or Bearer token."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        return None

    user = db.query(User).filter(User.session_token == token).first()
    return user


@router.get("/config")
def get_auth_config():
    """Return public authentication configuration."""
    is_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    return {
        "google_enabled": is_configured,
        "client_id": settings.GOOGLE_CLIENT_ID if is_configured else None,
        "demo_mode": not is_configured,
    }


@router.get("/google/login")
def google_login(request: Request):
    """Initiate Google OAuth 2.0 authorization code flow."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(
            url="/?auth_error=google_credentials_missing",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    state = secrets.token_urlsafe(24)
    redirect_uri = get_callback_url(request)

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }

    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    response = RedirectResponse(url=google_auth_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth 2.0 callback redirect."""
    if error:
        logger.error(f"Google OAuth returned error: {error}")
        return RedirectResponse(url=f"/?auth_error={error}", status_code=status.HTTP_303_SEE_OTHER)

    if not code:
        return RedirectResponse(url="/?auth_error=missing_code", status_code=status.HTTP_303_SEE_OTHER)

    redirect_uri = get_callback_url(request)

    try:
        token_url = "https://oauth2.googleapis.com/token"
        token_payload = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            token_res = await client.post(token_url, data=token_payload)
            if token_res.status_code != 200:
                logger.error(f"Failed to exchange token with Google: {token_res.text}")
                return RedirectResponse(url="/?auth_error=token_exchange_failed", status_code=status.HTTP_303_SEE_OTHER)

            token_data = token_res.json()
            access_token = token_data.get("access_token")

            userinfo_res = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_res.status_code != 200:
                logger.error(f"Failed to fetch userinfo from Google: {userinfo_res.text}")
                return RedirectResponse(url="/?auth_error=userinfo_failed", status_code=status.HTTP_303_SEE_OTHER)

            profile = userinfo_res.json()

        google_id = str(profile.get("sub"))
        email = profile.get("email")
        name = profile.get("name", email.split("@")[0] if email else "Archiver User")
        picture = profile.get("picture")

        if not email or not google_id:
            return RedirectResponse(url="/?auth_error=invalid_profile", status_code=status.HTTP_303_SEE_OTHER)

        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            user = db.query(User).filter(User.email == email).first()

        new_session_token = secrets.token_urlsafe(32)

        if user:
            user.google_id = google_id
            user.name = name
            user.picture = picture
            user.session_token = new_session_token
            user.last_login_at = utc_now()
        else:
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                picture=picture,
                role="operator",
                session_token=new_session_token,
                created_at=utc_now(),
                last_login_at=utc_now(),
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        response = RedirectResponse(url="/?auth_success=1", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=new_session_token,
            httponly=True,
            max_age=SESSION_COOKIE_MAX_AGE,
            samesite="lax",
            path="/",
        )
        return response

    except Exception as exc:
        logger.exception(f"Exception in Google OAuth callback: {exc}")
        return RedirectResponse(url="/?auth_error=server_error", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/demo-login")
def demo_login(
    response: Response,
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
):
    """
    Simulate Google authentication for development, testing,
    and presentation purposes without requiring Google Cloud setup.
    """
    demo_email = "commander@orbitronix.io"
    demo_name = "Alex Mercer"
    demo_avatar = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80"

    if payload:
        demo_email = payload.get("email", demo_email)
        demo_name = payload.get("name", demo_name)
        demo_avatar = payload.get("picture", demo_avatar)

    demo_google_id = f"demo_gid_{secrets.token_hex(8)}"

    user = db.query(User).filter(User.email == demo_email).first()
    new_session_token = secrets.token_urlsafe(32)

    if user:
        user.name = demo_name
        user.picture = demo_avatar
        user.session_token = new_session_token
        user.last_login_at = utc_now()
    else:
        user = User(
            google_id=demo_google_id,
            email=demo_email,
            name=demo_name,
            picture=demo_avatar,
            role="lead_archivist",
            session_token=new_session_token,
            created_at=utc_now(),
            last_login_at=utc_now(),
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=new_session_token,
        httponly=True,
        max_age=SESSION_COOKIE_MAX_AGE,
        samesite="lax",
        path="/",
    )

    return {
        "status": "success",
        "authenticated": True,
        "user": user.to_dict(),
    }


@router.get("/me")
def get_current_user_profile(
    user: Optional[User] = Depends(get_current_user),
):
    """Retrieve the currently authenticated user's profile."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return {
        "authenticated": True,
        "user": user.to_dict(),
    }


@router.post("/logout")
def logout(
    response: Response,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invalidate active session token and clear authentication cookie."""
    if user:
        user.session_token = None
        db.commit()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return {
        "status": "success",
        "message": "Successfully logged out.",
    }
