from app.services.encryption import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-live-abc123-trading212-api-key"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext.encode()
    assert decrypt(ciphertext) == plaintext


def test_different_plaintexts_produce_different_ciphertexts():
    a = encrypt("key-a")
    b = encrypt("key-b")
    assert a != b
