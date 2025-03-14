import time
import requests
import jwt
from datetime import datetime

class GitHubAppAuth:
    def __init__(self, app_id=None, private_key=None, installation_id=None, pat=None):
        """
        Initialize GitHub App authentication
        
        Args:
            app_id (str): GitHub App ID
            private_key (str): GitHub App private key content (not path)
            installation_id (str): GitHub App installation ID
            pat (str): Personal Access Token (fallback)
        """
        # GitHub App credentials
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        
        # For backward compatibility
        self.pat = pat
        
        # Cache for the installation token
        self.token = None
        self.token_expires_at = 0
        
        # Track auth method for logging/debugging
        self.auth_method = None
    
    def get_token(self):
        """Get an installation access token for the GitHub App, or fallback to PAT"""
        # Check if we have a valid cached token
        now = int(time.time())
        if self.token and now < (self.token_expires_at - 300):  # 5-minute buffer
            return self.token
            
        # If GitHub App credentials are not configured, fallback to PAT
        if not all([self.app_id, self.private_key, self.installation_id]):
            self.auth_method = "pat"
            return self.pat
            
        try:
            # Generate JWT
            now = int(time.time())
            payload = {
                'iat': now - 60,  # Account for clock drift
                'exp': now + 600,  # 10 minutes
                'iss': str(self.app_id)
            }
            
            jwt_token = jwt.encode(payload, self.private_key, algorithm='RS256')

            if isinstance(jwt_token, bytes):
                jwt_token = jwt_token.decode('utf-8')
            
            # Get installation token
            url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RooLLM-GitHub-App"  # Always include a User-Agent
            }
            
            response = requests.post(url, headers=headers)
            
            if response.status_code != 201:
                self.auth_method = "pat"
                return self.pat
                
            data = response.json()
            self.token = data["token"]
            
            # Parse expiration if available
            if "expires_at" in data:
                expires_at = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
                self.token_expires_at = int(expires_at.timestamp())
            else:
                # Default to 1 hour
                self.token_expires_at = now + 3600
                
            self.auth_method = "github_app"
            return self.token
            
        except Exception as e:
            self.auth_method = "pat"
            return self.pat
    
    def get_auth_method(self):
        """Return the current authentication method being used"""
        return self.auth_method


def prepare_github_token(config):
    """
    Prepare GitHub token from config
    
    Args:
        config (dict): Configuration dictionary that may contain GitHub credentials
        
    Returns:
        tuple: (token, auth_method) - The GitHub token and the authentication method used
    """
    # Check if GitHub App credentials are available
    app_id = config.get("GITHUB_APP_ID")
    private_key = config.get("GITHUB_PRIVATE_KEY")
    installation_id = config.get("GITHUB_INSTALLATION_ID")
    pat = config.get("GITHUB_TOKEN") or config.get("gh_token")
    
    # Early return if no credentials are available
    if not (app_id or pat):
        return None, None
    
    # If we have GitHub App credentials, try to get a token
    auth = GitHubAppAuth(
        app_id=app_id,
        private_key=private_key,
        installation_id=installation_id,
        pat=pat
    )
    
    token = auth.get_token()
    auth_method = auth.get_auth_method()
    
    # Return the auth object as well, which can be useful for token refresh
    return token, auth_method, auth