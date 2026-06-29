from proteinhub.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_jwt_roundtrip_and_signature_check() -> None:
    token = create_token(42, "secret", issuer="proteinhub", ttl_seconds=60, now=100)

    payload = decode_token(token, "secret", issuer="proteinhub", now=120)

    assert payload["sub"] == "42"
    assert payload["iss"] == "proteinhub"


def test_jwt_rejects_expired_token() -> None:
    token = create_token(42, "secret", issuer="proteinhub", ttl_seconds=60, now=100)

    try:
        decode_token(token, "secret", issuer="proteinhub", now=200)
    except ValueError as error:
        assert "expired" in str(error).lower()
    else:
        raise AssertionError("expired token was accepted")

