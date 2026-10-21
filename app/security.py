import hashlib
import os


def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    pwd = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000
    ).hex()
    return pwd, salt


def verify_password(password, salt, stored_hash):
    pwd, _ = hash_password(password, salt)
    return pwd == stored_hash
