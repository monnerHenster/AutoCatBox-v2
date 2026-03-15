import base64
import json
import pulsar
from Crypto.Cipher import AES


def decrypt_message(pulsar_message, access_key: str) -> str:
    payload = pulsar_message.data().decode("utf-8")
    decrypt_model = pulsar_message.properties().get("em") or "aes_ecb"
    return do_decrypt_message(payload, decrypt_model, access_key)


def do_decrypt_message(payload: str, decrypt_model: str, access_key: str) -> str:
    data_json = json.loads(payload)
    encrypt_data = data_json["data"]
    return decrypt_by_aes(encrypt_data, access_key, decrypt_model)


def decrypt_by_aes(raw: str, key: str, decrypt_model: str) -> str:
    raw_bytes = base64.b64decode(raw)
    key_bytes = key[8:24].encode("utf-8")
    if decrypt_model == "aes_gcm":
        return decrypt_by_gcm(raw_bytes, key_bytes)
    return decrypt_by_ecb(raw_bytes, key_bytes)


def decrypt_by_gcm(raw_bytes: bytes, key_bytes: bytes) -> str:
    nonce = raw_bytes[:12]
    ciphertext = raw_bytes[12:-16]
    auth_tag = raw_bytes[-16:]
    aes_cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=nonce)
    return aes_cipher.decrypt_and_verify(ciphertext, auth_tag).decode("utf-8")


def decrypt_by_ecb(raw_bytes: bytes, key_bytes: bytes) -> str:
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    decrypted_data = cipher.decrypt(raw_bytes)
    res_str = decrypted_data.decode("utf-8")
    res_str = res_str.replace("\r", "").replace("\n", "").replace("\f", "")
    return res_str


def message_id(msg_id) -> str:
    return f"{msg_id.ledger_id()}:{msg_id.entry_id()}:{msg_id.partition()}:{msg_id.batch_index()}"
