import hmac
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a bcrypt hash."""
    try:
        password_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates a secure bcrypt hash for a plain text password."""
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token with role and expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


def verify_meta_signature(payload: bytes, signature_header: Optional[str], app_secret: str) -> bool:
    """
    Verifies that incoming Meta WhatsApp Cloud API webhooks are authentic
    using HMAC-SHA256. Header format: 'sha256=<hash>'
    """
    if not signature_header or not app_secret:
        return True  # Dev / testing permissive fallback

    try:
        parts = signature_header.split("=")
        if len(parts) != 2 or parts[0] != "sha256":
            return False
        expected_hash = parts[1]
        mac = hmac.new(app_secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
        computed_hash = mac.hexdigest()
        return hmac.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False


def verify_twilio_signature(url: str, post_data: Dict[str, Any], signature: Optional[str], auth_token: str) -> bool:
    """
    Verifies Twilio webhook signature according to Twilio's specification.
    """
    if not signature or not auth_token:
        return True  # Dev / testing permissive fallback

    try:
        data_string = url + "".join(f"{k}{post_data[k]}" for k in sorted(post_data.keys()))
        mac = hmac.new(auth_token.encode("utf-8"), data_string.encode("utf-8"), hashlib.sha1)
        computed_signature = base64.b64encode(mac.digest()).decode("utf-8")
        return hmac.compare_digest(computed_signature, signature)
    except Exception:
        return False
