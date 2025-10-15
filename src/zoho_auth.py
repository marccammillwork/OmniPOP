"""
Zoho Books OAuth Authentication Module
Handles OAuth 2.0 flow for Zoho Books API integration
"""

import os
import json
import time
import webbrowser
import requests
from urllib.parse import urlencode, parse_qs, urlparse
import tkinter as tk
from tkinter import messagebox
import threading


class ZohoAuth:
    """Handles OAuth 2.0 authentication for Zoho Books API"""
    
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser("~"), ".omnipop_zoho_config.json")
        self.client_id = "1000.4T5D90QD2OHVCO2T5ML4GSC4INNP5V"  # Replace this with your actual client ID from Zoho API Console
        self.client_secret = "60c7c4062daa6c165eaca5c591df03ae15e5114fd5"    # Replace this with your actual client secret
        self.redirect_uri = "https://www.zoho.com/books/oauthredirect"
        self.scope = "ZohoBooks.fullaccess.all"
        self.auth_url = "https://accounts.zoho.com/oauth/v2/auth"
        self.token_url = "https://accounts.zoho.com/oauth/v2/token"
        self.revoke_url = "https://accounts.zoho.com/oauth/v2/token/revoke"
        
        # Load existing config
        self.config = self._load_config()
    
    def _load_config(self):
        """Load OAuth configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_config(self):
        """Save OAuth configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Error saving OAuth config: {e}")
    
    def generate_auth_url(self):
        """Generate OAuth authorization URL"""
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'scope': self.scope,
            'redirect_uri': self.redirect_uri,
            'access_type': 'offline',
            'prompt': 'consent'
        }
        return f"{self.auth_url}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, authorization_code):
        """Exchange authorization code for access and refresh tokens"""
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': authorization_code
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Store tokens with expiration time
            self.config.update({
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_in': token_data.get('expires_in', 3600),
                'expires_at': time.time() + token_data.get('expires_in', 3600),
                'organization_id': token_data.get('organization_id'),
                'authenticated': True,
                'last_auth': time.time()
            })
            
            self._save_config()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error exchanging code for tokens: {e}")
            return False
        except KeyError as e:
            print(f"Missing token data: {e}")
            return False
    
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        if not self.config.get('refresh_token'):
            return False
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.config['refresh_token']
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Update access token
            self.config.update({
                'access_token': token_data.get('access_token'),
                'expires_in': token_data.get('expires_in', 3600),
                'expires_at': time.time() + token_data.get('expires_in', 3600),
                'last_refresh': time.time()
            })
            
            self._save_config()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error refreshing token: {e}")
            return False
    
    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        if not self.is_authenticated():
            return None
        
        # Check if token is expired or will expire soon (within 5 minutes)
        if time.time() >= (self.config.get('expires_at', 0) - 300):
            if not self.refresh_access_token():
                return None
        
        return self.config.get('access_token')
    
    def is_authenticated(self):
        """Check if user is authenticated with valid tokens"""
        if not self.config.get('authenticated', False):
            return False
        
        if not self.config.get('access_token'):
            return False
        
        # Check if token is expired
        if time.time() >= self.config.get('expires_at', 0):
            # Try to refresh
            if not self.refresh_access_token():
                return False
        
        return True
    
    def get_organization_id(self):
        """Get the organization ID from config, fetching if necessary."""
        org_id = self.config.get('organization_id')
        if org_id:
            return org_id

        # If not in config, try to fetch it from the API
        if self.is_authenticated():
            try:
                # Import here to avoid circular dependency
                from zoho_client import ZohoBooksClient
                
                client = ZohoBooksClient(self)
                orgs_response = client.get_organization_details()
                
                if orgs_response and 'organizations' in orgs_response and orgs_response['organizations']:
                    # Assuming the first organization is the correct one
                    org_id = orgs_response['organizations'][0]['organization_id']
                    self.config['organization_id'] = org_id
                    self._save_config()
                    print(f"Fetched and saved organization_id: {org_id}")
                    return org_id
            except Exception as e:
                print(f"Could not fetch organization_id: {e}")
        
        return None
    
    def revoke_tokens(self):
        """Revoke access and refresh tokens"""
        if not self.config.get('access_token'):
            return True
        
        data = {
            'token': self.config['access_token']
        }
        
        try:
            response = requests.post(self.revoke_url, data=data)
            response.raise_for_status()
            
            # Clear config
            self.config = {}
            self._save_config()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error revoking tokens: {e}")
            return False
    
    def get_auth_status(self):
        """Get detailed authentication status"""
        if not self.is_authenticated():
            return {
                'authenticated': False,
                'status': 'Not authenticated',
                'organization_id': None
            }
        
        return {
            'authenticated': True,
            'status': 'Connected to Zoho Books',
            'organization_id': self.get_organization_id(),
            'expires_at': self.config.get('expires_at'),
            'last_auth': self.config.get('last_auth')
        }


class ZohoAuthDialog:
    """Modal dialog for OAuth authentication flow"""
    
    def __init__(self, parent, auth_handler):
        self.parent = parent
        self.auth_handler = auth_handler
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Authenticate with Zoho Books")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"500x400+{x}+{y}")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame
        main_frame = tk.Frame(self.dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Zoho Books Authentication", 
                              font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Instructions
        instructions = tk.Text(main_frame, height=8, width=60, wrap=tk.WORD)
        instructions.pack(pady=(0, 20))
        
        instructions_text = """To authenticate with Zoho Books:

1. Click 'Open in Browser' below.
2. Log in and grant permissions to OmniPOP.
3. Zoho will redirect to a "Page Not Found" error. THIS IS EXPECTED.
4. Copy the 'code' from the URL in your browser's address bar.
   (It's the long string of text after 'code=')
5. Paste it in the field below and click 'Authenticate'."""
        
        instructions.insert(tk.END, instructions_text)
        instructions.config(state=tk.DISABLED)
        
        # Open browser button
        self.browser_button = tk.Button(main_frame, text="Open in Browser", 
                                      command=self._open_browser, bg="#4CAF50", 
                                      fg="white", font=("Arial", 10, "bold"))
        self.browser_button.pack(pady=(0, 10))
        
        # Authorization code input
        code_frame = tk.Frame(main_frame)
        code_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(code_frame, text="Authorization Code:").pack(anchor=tk.W)
        self.code_entry = tk.Entry(code_frame, width=50, font=("Arial", 10))
        self.code_entry.pack(fill=tk.X, pady=(5, 0))
        
        # Buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.authenticate_button = tk.Button(button_frame, text="Authenticate", 
                                           command=self._authenticate, 
                                           bg="#2196F3", fg="white", 
                                           font=("Arial", 10, "bold"))
        self.authenticate_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_button = tk.Button(button_frame, text="Cancel", 
                                     command=self._cancel)
        self.cancel_button.pack(side=tk.LEFT)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="", fg="blue")
        self.status_label.pack(pady=(10, 0))
        
        # Focus on code entry
        self.code_entry.focus()
    
    def _open_browser(self):
        """Open authorization URL in browser"""
        auth_url = self.auth_handler.generate_auth_url()
        webbrowser.open(auth_url)
        self.status_label.config(text="Browser opened. Please copy the authorization code.", 
                               fg="blue")
    
    def _authenticate(self):
        """Authenticate with provided code"""
        code = self.code_entry.get().strip()
        if not code:
            self.status_label.config(text="Please enter the authorization code.", fg="red")
            return
        
        self.status_label.config(text="Authenticating...", fg="blue")
        self.dialog.update()
        
        if self.auth_handler.exchange_code_for_tokens(code):
            self.status_label.config(text="Authentication successful!", fg="green")
            self.dialog.after(1000, self._close_success)
        else:
            self.status_label.config(text="Authentication failed. Please try again.", fg="red")
    
    def _close_success(self):
        """Close dialog after successful authentication"""
        self.result = True
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel authentication"""
        self.result = False
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result


# Test function
if __name__ == "__main__":
    auth = ZohoAuth()
    print(f"Authenticated: {auth.is_authenticated()}")
    print(f"Auth URL: {auth.generate_auth_url()}")
