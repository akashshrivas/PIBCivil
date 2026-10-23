"""
backend/auth.py
------------------------------------------------------------------
Lets your FastAPI backend check WHO is calling an endpoint.
You do not need this yet (your articles endpoints are public), but
you will the moment you build "Saved" or anything user-specific.

How it works:
  1. After login the Next.js app has a Supabase access token (a JWT).
  2. The frontend sends it to FastAPI in this header:
         Authorization: Bearer <access_token>
  3. get_current_user() checks the token's signature (using Supabase's
     public keys), expiry, audience and issuer. Anything wrong -> 401.

Install:   pip install "pyjwt[crypto]"   (add it to backend_requirements.txt)
Use:
    from ..auth import get_current_user

    @router.get("/saved")
    def my_saved(user: dict = Depends(get_current_user)):
        user_id = user["sub"]   # the Supabase user id (a UUID)

Optional env var in backend/.env (older projects only):
    SUPABASE_JWT_SECRET=...   # needed only if your project still signs
                              # tokens with the shared HS256 secret
------------------------------------------------------------------
"""

import os

import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

# Reuse your existing config module: it loads backend/.env for us.
from .config import SUPABASE_URL

SUPABASE_URL = SUPABASE_URL.rstrip("/")
LEGACY_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")  # optional

# Supabase publishes its public signing keys here.
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
# A valid token says it was issued by your project...
ISSUER = f"{SUPABASE_URL}/auth/v1"
# ...and that it is meant for logged-in users.
AUDIENCE = "authenticated"

# Downloads the keys and caches them, so we do not call Supabase on every request.
_jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)

# Reads "Authorization: Bearer ...". auto_error=False lets us send our own 401.
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    """A 401 error that tells the client to send a Bearer token."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency: returns the verified token claims, or raises 401."""
    if credentials is None:
        raise _unauthorized()

    token = credentials.credentials

    try:
        # Peek at the header (NOT trusted yet) to see which algorithm is claimed.
        algorithm = jwt.get_unverified_header(token).get("alg")

        if algorithm in ("ES256", "RS256"):
            # Modern projects: verify with the matching public key.
            key = _jwks_client.get_signing_key_from_jwt(token).key
            allowed = [algorithm]
        elif algorithm == "HS256" and LEGACY_JWT_SECRET:
            # Older projects: verify with the shared secret.
            key = LEGACY_JWT_SECRET
            allowed = ["HS256"]
        else:
            # Unknown algorithm (including "none"): reject.
            raise _unauthorized("Invalid token")

        claims = jwt.decode(
            token,
            key,
            algorithms=allowed,  # never accept any other algorithm
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "sub"]},  # these claims must exist
        )
    except HTTPException:
        raise
    except jwt.PyJWTError:
        # Expired, bad signature, wrong issuer, malformed, ...
        # We do not say which, to give attackers no hints.
        raise _unauthorized("Invalid or expired token")

    return claims
