"""JWT authentication; no unauthenticated document endpoints."""
import os
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from storage import connect

JWT_SECRET = os.getenv("JWT_SECRET")
bearer = HTTPBearer()

def register(email, password):
    if len(password) < 8 or len(password.encode()) > 72:
        raise HTTPException(400, "Password must be 8–72 bytes")
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with connect() as conn:
            conn.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s)",
                         (user_id, email.strip().lower(), hashed))
    except Exception as exc:
        from psycopg.errors import UniqueViolation
        if isinstance(exc, UniqueViolation):
            raise HTTPException(409, "Email already registered")
        raise
    return user_id

def login(email, password):
    with connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=%s", (email.strip().lower(),)).fetchone()
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    return token(str(user["id"]))

def token(user_id):
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be configured")
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
                      JWT_SECRET, algorithm="HS256")

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        if not JWT_SECRET:
            raise ValueError("JWT secret not configured")
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return str(uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
