import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

SECRET_KEY = os.getenv("NEXUSTRACE_SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("NEXUSTRACE_ACCESS_TOKEN_MINUTES", "720"))
BCRYPT_ROUNDS = max(10, min(14, int(os.getenv("NEXUSTRACE_BCRYPT_ROUNDS", "12"))))


def hash_password(password):
    password_bytes = str(password or "").encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password, hashed_password):
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            str(plain_password).encode("utf-8"),
            str(hashed_password).encode("utf-8"),
        )
    except ValueError:
        return False


def create_access_token(user):
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "is_admin": bool(user.get("is_admin")),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
