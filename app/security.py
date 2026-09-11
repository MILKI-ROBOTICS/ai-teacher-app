from datetime import datetime, timedelta, timezone
import base64, hashlib, hmac, os
import jwt
from .config import settings

ALGO = "HS256"
PBKDF2_ITERS = 600_000

def hash_password(value: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

def verify_password(value: str, encoded: str) -> bool:
    try:
        scheme, iters, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256": return False
        salt = base64.b64decode(salt_b64); expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", value.encode(), salt, int(iters))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def create_token(user_id: int, session_version: int = 1) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "sv": int(session_version), "iat": int(now.timestamp()), "exp": now + timedelta(minutes=settings.access_token_expire_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGO)

def decode_token(token: str) -> tuple[int, int]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGO])
    return int(payload["sub"]), int(payload.get("sv", 1))


def new_secret_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip("=")
