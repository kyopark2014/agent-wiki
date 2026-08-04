"""Session auth — local User ID plus optional Google OAuth."""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

try:
    from application import utils
except ImportError:
    import utils  # type: ignore

logger = logging.getLogger("routes_auth")

router = APIRouter(prefix="/api/session", tags=["session"])

SESSION_COOKIE = "agent_user_id"
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
# agentic-work and peers store opaque HMAC cookies under the same name.
_SIGNED_COOKIE_PREFIX = "v1."
_MAX_PLAIN_USER_ID_LEN = 128


class SessionRequest(BaseModel):
    credential: str | None = Field(
        default=None, description="Google ID Token (JWT)"
    )
    access_token: str | None = Field(
        default=None, description="Google OAuth access token"
    )
    user_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Local-only user id when auth bypass is enabled",
    )


class SessionResponse(BaseModel):
    user_id: str
    name: str | None = None
    picture: str | None = None
    llm_gateway_ready: bool = False


def _google_client_id() -> str:
    cfg = utils.load_config()
    return (cfg.get("google_client_id") or "").strip()


def _env_bypass_flag() -> bool:
    return os.environ.get("ALLOW_LOCAL_AUTH_BYPASS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_loopback_request(request: Request) -> bool:
    """True only for direct localhost access. Ignores X-Forwarded-Host."""
    host = (request.headers.get("host") or "").split("%")[0]
    hostname = host.split(":")[0].strip().lower().strip("[]")
    return hostname in {"localhost", "127.0.0.1", "::1"}


def local_auth_bypass_enabled(request: Request) -> bool:
    """Allow plain User ID login when Google is not required.

    True when:
    - ALLOW_LOCAL_AUTH_BYPASS is set,
    - request Host is loopback, or
    - google_client_id is not configured (agent-skills default).
    """
    if _env_bypass_flag() or is_loopback_request(request):
        return True
    return not bool(_google_client_id())


def _llm_gateway_ready() -> bool:
    cfg = utils.load_config()
    url = (cfg.get("llm_gateway_url") or "").strip()
    key = (cfg.get("llm_gateway_key") or "").strip()
    return bool(url and key)


def verify_google_token(token: str, client_id: str) -> dict:
    url = f"{TOKENINFO_URL}?id_token={urllib.parse.quote(token)}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            idinfo = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"Token verification failed ({e.code}): {body}") from e
    except Exception as e:
        raise ValueError(f"Token verification request failed: {e}") from e

    if idinfo.get("aud") != client_id:
        raise ValueError(f"Invalid audience: {idinfo.get('aud')}")
    email = (idinfo.get("email") or "").strip()
    if not email:
        raise ValueError("Google token missing email")
    return idinfo


def verify_google_access_token(token: str, client_id: str) -> dict:
    info_url = f"{TOKENINFO_URL}?access_token={urllib.parse.quote(token)}"
    req = urllib.request.Request(info_url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            idinfo = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"Token verification failed ({e.code}): {body}") from e
    except Exception as e:
        raise ValueError(f"Token verification request failed: {e}") from e

    aud = idinfo.get("aud") or idinfo.get("azp")
    if aud != client_id:
        raise ValueError(f"Invalid audience: {aud}")
    email = (idinfo.get("email") or "").strip()
    if not email:
        raise ValueError("Google token missing email")
    return idinfo


def _set_user_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=user_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )


def _uid_from_signed_cookie(raw: str) -> str | None:
    """Extract uid from opaque ``v1.<payload_b64>.<sig>`` cookies (e.g. agentic-work).

    agent-skills itself stores plain user_id values. When the browser still has a
    signed peer-app cookie under the same name, decode the payload so artifacts
    land under ``{uid}/`` instead of the full token string.
    """
    parts = raw.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        return None
    try:
        padding = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
    except Exception:
        logger.warning("Ignoring undecodable signed session cookie")
        return None
    uid = (payload.get("uid") or "").strip()
    if not uid or len(uid) > _MAX_PLAIN_USER_ID_LEN:
        return None
    return uid


def resolve_cookie_user_id(raw: str | None) -> str | None:
    """Normalize cookie value to a plain user_id (never return a signed token)."""
    value = (raw or "").strip()
    if not value:
        return None
    if value.startswith(_SIGNED_COOKIE_PREFIX):
        return _uid_from_signed_cookie(value)
    if len(value) > _MAX_PLAIN_USER_ID_LEN:
        logger.warning("Ignoring oversized session cookie (%d chars)", len(value))
        return None
    return value


def get_optional_user_id(request: Request) -> str | None:
    return resolve_cookie_user_id(request.cookies.get(SESSION_COOKIE))


@router.post("", response_model=SessionResponse)
def set_session(body: SessionRequest, request: Request, response: Response) -> SessionResponse:
    credential = (body.credential or "").strip()
    access_token = (body.access_token or "").strip()
    local_user_id = (body.user_id or "").strip()
    gateway_ready = _llm_gateway_ready()

    if credential or access_token:
        client_id = _google_client_id()
        if not client_id:
            raise HTTPException(
                status_code=500, detail="google_client_id is not configured"
            )
        try:
            if credential:
                idinfo = verify_google_token(credential, client_id)
            else:
                idinfo = verify_google_access_token(access_token, client_id)
        except ValueError as e:
            logger.warning("Google login rejected: %s", e)
            raise HTTPException(status_code=401, detail="Invalid Google credential") from e

        user_id = idinfo["email"].strip()
        _set_user_cookie(response, user_id)
        utils.ensure_user_artifacts_dir(user_id)
        utils.ensure_user_skills_dir(user_id)
        utils.ensure_user_skills_list(user_id)
        logger.info("Google login success: %s (llm_gateway_ready=%s)", user_id, gateway_ready)
        return SessionResponse(
            user_id=user_id,
            name=(idinfo.get("name") or None),
            picture=(idinfo.get("picture") or None),
            llm_gateway_ready=gateway_ready,
        )

    if local_user_id:
        if not local_auth_bypass_enabled(request):
            raise HTTPException(
                status_code=403,
                detail="Local auth bypass is disabled",
            )
        _set_user_cookie(response, local_user_id)
        utils.ensure_user_artifacts_dir(local_user_id)
        utils.ensure_user_skills_dir(local_user_id)
        utils.ensure_user_skills_list(local_user_id)
        logger.info(
            "Local auth bypass login: %s (llm_gateway_ready=%s)",
            local_user_id,
            gateway_ready,
        )
        return SessionResponse(user_id=local_user_id, llm_gateway_ready=gateway_ready)

    raise HTTPException(
        status_code=400, detail="credential, access_token, or user_id is required"
    )


@router.get("", response_model=SessionResponse | None)
def get_session(request: Request, response: Response) -> SessionResponse | None:
    raw_cookie = (request.cookies.get(SESSION_COOKIE) or "").strip()
    user_id = resolve_cookie_user_id(raw_cookie)
    if not user_id:
        return None
    # Rewrite opaque peer-app cookies to plain user_id for this app.
    if raw_cookie.startswith(_SIGNED_COOKIE_PREFIX) and raw_cookie != user_id:
        _set_user_cookie(response, user_id)
        logger.info("Normalized signed session cookie to user_id=%s", user_id)
    # Ensure workspace survives process restarts for an existing cookie session
    utils.ensure_user_artifacts_dir(user_id)
    utils.ensure_user_skills_dir(user_id)
    utils.ensure_user_skills_list(user_id)
    return SessionResponse(user_id=user_id, llm_gateway_ready=_llm_gateway_ready())


@router.delete("", status_code=204, response_model=None)
def clear_session(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, samesite="lax")


def require_user_id(request: Request) -> str:
    user_id = get_optional_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="User session required")
    return user_id
