from sqlalchemy.types import TypeDecorator, String
from cryptography.fernet import Fernet

# TODO: manage this. This should be kept in secret manager.
def generate_key():
    if get_key():
        print("Key already exists. Manual deletion required to generate a new key. Save the old one or use it to decrypt data.")
        return None
    
    key = Fernet.generate_key()
    with open('.key', 'wb') as key_file:
        key_file.write(key)
    return key

def get_key():
    try:
        with open('.key', 'rb') as key_file:
            key = key_file.read()
        return key
    except Exception as e:
        print(f"Key not found: {e}")
        return None

def get_cipher_suite():
    key = get_key()
    if not key:
        generate_key()
        key = get_key()
    return Fernet(key)

cipher_suite = get_cipher_suite()

class EncryptedString(TypeDecorator):
    """A type that encrypts and decrypts strings transparently."""
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.encode('utf-8')
            encrypted_value = cipher_suite.encrypt(value)
            return encrypted_value.decode('utf-8')
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.encode('utf-8')
            decrypted_value = cipher_suite.decrypt(value)
            return decrypted_value.decode('utf-8')
        return value

    def copy(self):
        return EncryptedString(self.impl.length)
