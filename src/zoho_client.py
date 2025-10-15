"""
Zoho Books API Client
Wrapper for Zoho Books API calls with rate limiting and error handling
"""

import requests
import time
import json
from typing import Dict, List, Optional, Any
from zoho_auth import ZohoAuth


class ZohoBooksClient:
    """Client for Zoho Books API with rate limiting and error handling"""
    
    def __init__(self, auth_handler: ZohoAuth):
        self.auth_handler = auth_handler
        self.base_url = "https://www.zohoapis.com/books/v3"
        self.rate_limit_delay = 1.0  # Delay between requests (seconds)
        self.last_request_time = 0
        self.max_retries = 3
        
    def _wait_for_rate_limit(self):
        """Wait to respect rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, 
                     data: Dict = None, retry_count: int = 0) -> Optional[Dict]:
        """Make API request with error handling and retries"""
        self._wait_for_rate_limit()
        
        # Get valid access token
        token = self.auth_handler.get_valid_token()
        if not token:
            print("No valid access token available")
            return None
        
        # Prepare headers
        headers = {
            'Authorization': f'Zoho-oauthtoken {token}',
            'Content-Type': 'application/json'
        }
        
        # Add organization_id to params, unless we're fetching the organizations themselves
        if params is None:
            params = {}
        
        # Add organization_id to params, unless we're fetching the organizations themselves
        if endpoint != 'organizations':
            organization_id = self.auth_handler.get_organization_id()
            if organization_id:
                params['organization_id'] = organization_id
        
        # Make request
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                print(f"Unsupported HTTP method: {method}")
                return None
            
            # Handle response
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Token expired, try to refresh
                if self.auth_handler.refresh_access_token():
                    if retry_count < self.max_retries:
                        return self._make_request(method, endpoint, params, data, retry_count + 1)
                print("Authentication failed - please re-authenticate")
                return None
            elif response.status_code == 429:
                # Rate limited, wait and retry
                if retry_count < self.max_retries:
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    return self._make_request(method, endpoint, params, data, retry_count + 1)
                print("Rate limit exceeded")
                return None
            else:
                print(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            if retry_count < self.max_retries:
                time.sleep(1)
                return self._make_request(method, endpoint, params, data, retry_count + 1)
            return None
    
    def get_organization_details(self) -> Optional[Dict]:
        """Get organization details"""
        return self._make_request('GET', 'organizations')
    
    def get_items(self, page: int = 1, per_page: int = 200) -> Optional[Dict]:
        """Get all items (materials) from Zoho Books"""
        params = {
            'page': page,
            'per_page': per_page
        }
        
        response = self._make_request('GET', 'items', params=params)
        return response
    
    def get_item_by_name(self, name: str) -> Optional[Dict]:
        """Get specific item by name"""
        params = {
            'name': name,
            'per_page': 1
        }
        
        response = self._make_request('GET', 'items', params=params)
        if response and 'items' in response and response['items']:
            return response['items'][0]
        return None
    
    def get_item_by_id(self, item_id: str) -> Optional[Dict]:
        """Get specific item by ID"""
        return self._make_request('GET', f'items/{item_id}')
    
    def search_items(self, search_term: str) -> List[Dict]:
        """Search items by name or description"""
        params = {
            'search_text': search_term,
            'per_page': 50
        }
        
        response = self._make_request('GET', 'items', params=params)
        if response and 'items' in response:
            return response['items']
        return []
    
    def get_custom_fields(self) -> List[Dict]:
        """Get custom fields for items"""
        response = self._make_request('GET', 'settings/items/customfields')
        if response and 'custom_fields' in response:
            return response['custom_fields']
        return []
    
    def create_estimate(self, estimate_data: Dict) -> Optional[Dict]:
        """Create a new estimate (for future order requests)"""
        return self._make_request('POST', 'estimates', data=estimate_data)
    
    def get_estimates(self, page: int = 1, per_page: int = 200) -> List[Dict]:
        """Get all estimates"""
        params = {
            'page': page,
            'per_page': per_page
        }
        
        response = self._make_request('GET', 'estimates', params=params)
        if response and 'estimates' in response:
            return response['estimates']
        return []
    
    def get_estimate_by_id(self, estimate_id: str) -> Optional[Dict]:
        """Get specific estimate by ID"""
        return self._make_request('GET', f'estimates/{estimate_id}')
    
    def update_estimate(self, estimate_id: str, estimate_data: Dict) -> Optional[Dict]:
        """Update an existing estimate"""
        return self._make_request('PUT', f'estimates/{estimate_id}', data=estimate_data)
    
    def delete_estimate(self, estimate_id: str) -> bool:
        """Delete an estimate"""
        response = self._make_request('DELETE', f'estimates/{estimate_id}')
        return response is not None
    
    def get_contacts(self, page: int = 1, per_page: int = 200) -> List[Dict]:
        """Get all contacts (customers)"""
        params = {
            'page': page,
            'per_page': per_page
        }
        
        response = self._make_request('GET', 'contacts', params=params)
        if response and 'contacts' in response:
            return response['contacts']
        return []
    
    def create_contact(self, contact_data: Dict) -> Optional[Dict]:
        """Create a new contact"""
        return self._make_request('POST', 'contacts', data=contact_data)
    
    def get_contact_by_id(self, contact_id: str) -> Optional[Dict]:
        """Get specific contact by ID"""
        return self._make_request('GET', f'contacts/{contact_id}')
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            response = self.get_organization_details()
            return response is not None
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def get_pricing_data(self) -> Dict[str, Any]:
        """Get comprehensive pricing data for materials"""
        try:
            # Get all items
            items = self.get_items()
            
            # Get custom fields to understand pricing structure
            custom_fields = self.get_custom_fields()
            
            # Process items into pricing data
            pricing_data = {
                'items': items or [],
                'custom_fields': custom_fields,
                'last_updated': time.time(),
                'organization_id': self.auth_handler.get_organization_id()
            }
            
            return pricing_data
            
        except Exception as e:
            print(f"Error fetching pricing data: {e}")
            return {
                'items': [],
                'custom_fields': [],
                'last_updated': time.time(),
                'error': str(e)
            }


# Test function
if __name__ == "__main__":
    from zoho_auth import ZohoAuth
    
    auth = ZohoAuth()
    if auth.is_authenticated():
        client = ZohoBooksClient(auth)
        print("Testing connection...")
        if client.test_connection():
            print("Connection successful!")
            items = client.get_items(per_page=5)
            print(f"Found {len(items)} items")
        else:
            print("Connection failed")
    else:
        print("Not authenticated")
