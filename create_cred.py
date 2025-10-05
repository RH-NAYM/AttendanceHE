# decrypt_dict.py
from cryptography.fernet import Fernet
import json

def decrypt_to_json():
    # Load the encryption key
    try:
        with open("secret.key", "rb") as key_file:
            key = key_file.read()
    except FileNotFoundError:
        print("Error: secret.key file not found!")
        return False
    
    cipher = Fernet(key)

    # Load and decrypt the data
    try:
        with open("encrypted_data.bin", "rb") as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        print("Error: encrypted_data.bin file not found!")
        return False

    try:
        decrypted_data = cipher.decrypt(encrypted_data)
        original_dict = json.loads(decrypted_data.decode())
    except Exception as e:
        print(f"Decryption error: {e}")
        return False

    # Save decrypted data to service_account.json
    try:
        with open("service_account.json", "w") as json_file:
            json.dump(original_dict, json_file, indent=2)
        print("Successfully decrypted and created service_account.json")
        return True
    except Exception as e:
        print(f"Error writing JSON file: {e}")
        return False

if __name__ == "__main__":
    decrypt_to_json()