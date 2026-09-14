import base64
import hashlib
import json

from Crypto.Cipher import AES


def _evp_bytes_to_key(password: bytes, salt: bytes, key_len: int, iv_len: int):
    """
    兼容 CryptoJS 在使用字符串密码时采用的 OpenSSL EVP_BytesToKey(MD5) 密钥派生算法
    """
    derived = b""
    block = b""
    while len(derived) < key_len + iv_len:
        block = hashlib.md5(block + password + salt).digest()
        derived += block
    return derived[:key_len], derived[key_len:key_len + iv_len]


def decrypt_aes_payload(cipher_text: str, secret: str):
    """
    解密前端 utils/AES.js 中 passwd_encode() 生成的密文
    （即 crypto-js 的 AES.encrypt(JSON.stringify(data), secret)）

    Args:
        cipher_text: 前端传来的 base64 密文
        secret: AES 密钥，需与前端 AES_SECRET 一致

    Returns:
        解密并 JSON.parse 后的原始数据
    """
    raw = base64.b64decode(cipher_text)
    if raw[:8] != b"Salted__":
        raise ValueError("密文格式不正确")

    salt = raw[8:16]
    ciphertext = raw[16:]
    key, iv = _evp_bytes_to_key(secret.encode("utf-8"), salt, 32, 16)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = cipher.decrypt(ciphertext)
    pad_len = padded[-1]
    plain = padded[:-pad_len]

    return json.loads(plain.decode("utf-8"))
