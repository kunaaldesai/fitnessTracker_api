from __future__ import annotations

from typing import Any

from firebase_admin import auth


class AuthError(ValueError):
    pass


def verify_authorization_header(header_value: str | None) -> dict[str, Any]:
    raw = str(header_value or "").strip()
    if not raw:
        raise AuthError("Missing Authorization header.")

    scheme, _, token = raw.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Authorization header must be Bearer token.")

    try:
        decoded = auth.verify_id_token(token.strip())
    except Exception as exc:  # pragma: no cover - firebase-admin owns details
        raise AuthError("Invalid Firebase ID token.") from exc

    uid = str(
        decoded.get("uid")
        or decoded.get("user_id")
        or decoded.get("sub")
        or ""
    ).strip()
    if not uid:
        raise AuthError("Firebase ID token is missing uid.")

    return {
        "uid": uid,
        "email": str(decoded.get("email") or "").strip(),
        "display_name": str(decoded.get("name") or decoded.get("display_name") or "").strip(),
        "picture": str(decoded.get("picture") or "").strip(),
        "claims": decoded,
    }
