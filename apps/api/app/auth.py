from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from .config import Settings, get_settings


class AuthenticatedUser(BaseModel):
    """Identity asserted by Supabase Auth, never by request payload data."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str
    full_name: str | None = None


class InvalidAccessToken(Exception):
    pass


class AuthenticationUnavailable(Exception):
    pass


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedUser: ...


class SupabaseTokenVerifier:
    """Ask the authoritative Supabase Auth service to verify an access token."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._anon_key = settings.next_public_supabase_anon_key

    async def verify(self, token: str) -> AuthenticatedUser:
        if not self._url or not self._anon_key:
            raise AuthenticationUnavailable
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    f"{self._url}/auth/v1/user",
                    headers={
                        "apikey": self._anon_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.HTTPError as exc:
            raise AuthenticationUnavailable from exc

        if response.status_code in (401, 403):
            raise InvalidAccessToken
        if response.status_code != 200:
            raise AuthenticationUnavailable

        try:
            payload: dict[str, Any] = response.json()
            user_id = UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidAccessToken from exc

        metadata = payload.get("user_metadata")
        full_name = metadata.get("full_name") if isinstance(metadata, dict) else None
        email = payload.get("email")
        return AuthenticatedUser(
            id=user_id,
            email=email if isinstance(email, str) else "",
            full_name=full_name
            if isinstance(full_name, str) and full_name.strip()
            else None,
        )


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_token_verifier() -> TokenVerifier:
    return SupabaseTokenVerifier(get_settings())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await verifier.verify(credentials.credentials)
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthenticationUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from exc


async def current_user_id(user: AuthenticatedUser = Depends(get_current_user)) -> UUID:
    """Compatibility dependency for owner-scoped session routes."""

    return user.id

