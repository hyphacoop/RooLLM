#!/usr/bin/env python3
"""
GitHub App Authentication Test Script

This script tests GitHub App authentication locally using your actual credentials.
If this succeeds but the server fails, you can identify differences in environment.

The config needed in the config.json file is:

{
    "GITHUB_APP_ID": "",
    "GITHUB_INSTALLATION_ID": "",
    "GITHUB_PRIVATE_KEY_BASE64": ""
}

"""
import json
import base64
import time
import requests
import jwt
import sys

# Print Python and library versions for comparison with server
print(f"Python version: {sys.version}")
print(f"PyJWT version: {jwt.__version__}")
try:
    from cryptography import __version__ as crypto_version
    print(f"Cryptography version: {crypto_version}")
except ImportError:
    print("Cryptography not installed")

def test_github_auth(config_path):
    """Test GitHub App authentication with the provided config file"""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            
        app_id = config.get("GITHUB_APP_ID")
        installation_id = config.get("GITHUB_INSTALLATION_ID")
        github_private_key_base64 = config.get("GITHUB_PRIVATE_KEY_BASE64")
        
        print(f"App ID: {app_id}")
        print(f"Installation ID: {installation_id}")
        print(f"Has private key: {'Yes' if github_private_key_base64 else 'No'}")
        
        if not all([app_id, installation_id, github_private_key_base64]):
            print("Missing required GitHub App credentials")
            return False
        
        # Decode the key
        private_key = base64.b64decode(github_private_key_base64).decode("utf-8")
        
        # Generate JWT
        now = int(time.time())
        payload = {
            'iat': now - 60,  # Account for clock drift
            'exp': now + 600,  # 10 minutes
            'iss': app_id
        }
        
        print(f"Payload: {payload}")
        
        # Try encoding with PyJWT
        try:
            print("Attempting to encode JWT...")
            jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
            print(f"Token type: {type(jwt_token)}")
            print(f"Token first 30 chars: {str(jwt_token)[:30]}...")
            
            # PyJWT 1.x returns bytes, PyJWT 2.x returns string
            if isinstance(jwt_token, bytes):
                print("Token is bytes, decoding to string...")
                jwt_token = jwt_token.decode('utf-8')
                print(f"Decoded token first 30 chars: {jwt_token[:30]}...")
        except Exception as e:
            print(f"Error encoding JWT: {e}")
            return False
        
        # Get installation token
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHubAppTest"
        }
        
        print(f"Requesting token from GitHub: {url}")
        response = requests.post(url, headers=headers)
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 201:
            data = response.json()
            token = data["token"]
            print(f"Successfully obtained token!")
            print(f"Token expires: {data.get('expires_at')}")
            return True
        else:
            print(f"Failed to get token, status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error during authentication: {e}")
        return False

def compare_with_server_version():
    """Print important differences between local and server environments"""
    print("\nEnvironment comparison:")
    print("Local:")
    print(f"  - Python: {sys.version.split()[0]}")
    print(f"  - PyJWT: {jwt.__version__}")
    try:
        from cryptography import __version__ as crypto_version
        print(f"  - Cryptography: {crypto_version}")
    except ImportError:
        print("  - Cryptography: Not installed")
    
    print("\nServer (from your logs):")
    print("  - Python: 3.9.x (from logs)")
    print("  - PyJWT: 2.10.1 (recently updated)")
    print("  - Cryptography: 44.0.2 (recently updated)")
    
    print("\nIf these match but results differ, the issue is likely with:")
    print("1. The private key format - server might have line ending issues")
    print("2. The network/firewall configuration of the server")
    print("3. The GitHub App installation for the server may need to be reinstalled")

if __name__ == "__main__":
    print("GitHub App Authentication Test")
    print("==============================")
    
    config_path = input("Enter the path to your config file: ")
    if not config_path:
        config_path = "config.json"  # Default path
    
    print(f"Testing with config file: {config_path}")
    success = test_github_auth(config_path)
    
    if success:
        print("\nLOCAL TEST SUCCESSFUL! 🎉")
        print("This confirms your GitHub App credentials work correctly locally.")
        
        # Suggest modifications
        print("\nTo fix the server issue, try this minimal change:")
        print("1. Add a single line to decode bytes to string if needed:")
        print("   In github_app_auth.py, after jwt_token = jwt.encode(...), add:")
        print("   if isinstance(jwt_token, bytes):")
        print("       jwt_token = jwt_token.decode('utf-8')")
        
        print("\n2. Convert app_id to string explicitly:")
        print("   Change 'iss': self.app_id to 'iss': str(self.app_id)")
    else:
        print("\nLOCAL TEST FAILED.")
        print("The issue exists in your local environment as well.")
        
    # Always print environment comparison
    compare_with_server_version()
