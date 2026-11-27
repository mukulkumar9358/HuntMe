import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.security import (
    create_access_token, decode_access_token, hash_password, hash_token, verify_password,
)
from tests.conftest import make_settings


async def test_password_hash_is_argon2id_and_verifies():
    h = await hash_password("s3cret-pass-phrase")
    assert h.startswith("$argon2id$")
    assert await verify_password(h, "s3cret-pass-phrase")
    assert not await verify_password(h, "wrong")
    assert not await verify_password(None, "anything")


def test_access_token_roundtrip_and_rejections():
    s = make_settings()
    uid = uuid.uuid4()
    assert decode_access_token(create_access_token(uid, s), s) == uid
    assert decode_access_token("garbage", s) is None
    other = make_settings(jwt_secret="another-secret-another-secret-123456789")
    assert decode_access_token(create_access_token(uid, other), s) is None
    expired = jwt.encode(
        {"sub": str(uid), "type": "access", "exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
        s.jwt_secret, algorithm="HS256")
    assert decode_access_token(expired, s) is None
    wrong_type = jwt.encode(
        {"sub": str(uid), "type": "refresh", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        s.jwt_secret, algorithm="HS256")
    assert decode_access_token(wrong_type, s) is None
    none_alg = jwt.encode({"sub": str(uid), "type": "access"}, key="", algorithm="none")
    assert decode_access_token(none_alg, s) is None


def test_hash_token_is_stable_sha256():
    assert hash_token("abc") == hash_token("abc") and len(hash_token("abc")) == 64
