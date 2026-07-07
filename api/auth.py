import datetime

from fastapi import Header, HTTPException, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from config import SECRET_KEY, ADMIN_PASSWORD

TOKEN_MAX_AGE = 60 * 60 * 12  # 12 hours
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="dashboard-auth")


def create_token() -> str:
    return serializer.dumps({"role": "admin", "issued": str(datetime.datetime.utcnow())})


def verify_password(password: str) -> bool:
    return password == ADMIN_PASSWORD


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
