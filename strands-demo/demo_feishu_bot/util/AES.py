import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad


class AESCipher:

    @staticmethod
    def encrypt(content, aes_key):
        if not content:
            print("AES encrypt: the content is null!")
            return None
        if len(aes_key) == 16:
            try:
                cipher = AES.new(aes_key.encode(), AES.MODE_ECB)
                encrypted = cipher.encrypt(pad(content.encode(), AES.block_size))
                return base64.b64encode(encrypted).decode()
            except Exception as e:
                print("AES encrypt exception:", e)
                raise RuntimeError(e)
        else:
            print("AES encrypt: the aesKey is null or error!")
            return None

    @staticmethod
    def decrypt(content, aes_key):
        if not content:
            print("AES decrypt: the content is null!")
            return None
        if len(aes_key) == 16:
            try:
                cipher = AES.new(aes_key.encode(), AES.MODE_ECB)
                decrypted = unpad(cipher.decrypt(base64.b64decode(content)), AES.block_size)
                return decrypted.decode()
            except Exception as e:
                print("AES decrypt exception:", e)
                raise RuntimeError(e)
        else:
            print("AES decrypt: the aesKey is null or error!")
            return None
