from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("secure-password")
    assert verify_password("secure-password", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = create_access_token("admin")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
