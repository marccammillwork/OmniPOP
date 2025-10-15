"""
Pricing Data Manager
Handles material pricing calculations from Zoho Books data
"""

import os
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from zoho_client import ZohoBooksClient
from zoho_auth import ZohoAuth


class PricingManager:
    """Manages material pricing data and calculations"""
    
    def __init__(self, auth_handler: ZohoAuth, zoho_client: ZohoBooksClient):
        self.auth_handler = auth_handler
        self.zoho_client = zoho_client
        self.cache_file = os.path.join(os.path.expanduser("~"), ".omnipop_pricing_cache.json")
        self.cache_expiry = 24 * 60 * 60  # 24 hours in seconds
        self.pricing_data = {}
        self.material_mappings = self._load_material_mappings()
        
    def _load_material_mappings(self) -> Dict[str, str]:
        """Load material name mappings to Zoho Books items"""
        # Load from saved mappings file
        mapping_file = os.path.join(os.path.expanduser("~"), ".omnipop_material_mappings.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r') as f:
                    saved_mappings = json.load(f)
                    return saved_mappings
            except (json.JSONDecodeError, IOError):
                pass
        
        # Default mappings (fallback)
        return {
            # Fixed OmniPOP material types
            'Melamine Black': 'Melamine - Black: 5 x 9 x 3/4',
            'Melamine White': 'Melamine - Black: 5 x 9 x 3/4',
            'Melamine Gray': 'Melamine - Black: 5 x 9 x 3/4',
            'Melamine Cherry': 'Melamine - Black: 5 x 9 x 3/4',
            'Melamine Spring Blossom': 'Melamine - Black: 5 x 9 x 3/4',
            'Melamine Hardrock Maple': 'Melamine - Black: 5 x 9 x 3/4',
            'Back Panel Material': 'Melamine - Black: 5 x 9 x 3/4',
            'Base Material': 'Melamine - Black: 5 x 9 x 3/4',
            'Canopy Material': 'Melamine - Black: 5 x 9 x 3/4'
        }
    
    def _load_cached_data(self) -> Dict:
        """Load pricing data from cache"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid
                if time.time() - cache_data.get('last_updated', 0) < self.cache_expiry:
                    return cache_data
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_cached_data(self, data: Dict):
        """Save pricing data to cache"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Error saving pricing cache: {e}")
    
    def fetch_and_cache_pricing(self) -> Dict:
        """Fetch pricing data from Zoho Books and cache it"""
        if not self.auth_handler.is_authenticated():
            print("Not authenticated with Zoho Books")
            return self._load_cached_data()
        
        try:
            print("Fetching pricing data from Zoho Books...")
            pricing_data = self.zoho_client.get_pricing_data()
            
            if pricing_data.get('error'):
                print(f"Error fetching pricing data: {pricing_data['error']}")
                return self._load_cached_data()
            
            # Cache the data
            self._save_cached_data(pricing_data)
            self.pricing_data = pricing_data
            
            print(f"Successfully cached {len(pricing_data.get('items', []))} items")
            return pricing_data
            
        except Exception as e:
            print(f"Error fetching pricing data: {e}")
            return self._load_cached_data()
    
    def get_material_cost(self, material_name: str, quantity: float, 
                         unit_type: str = 'unit') -> float:
        """Calculate cost for a specific material"""
        # Map material name to Zoho item name
        mapping_info = self.material_mappings.get(material_name, material_name)
        
        # Handle both old string-based and new dictionary-based mappings
        if isinstance(mapping_info, dict):
            zoho_item_name = mapping_info.get('zoho_item', material_name)
            # For manual entries, use the rate directly from the mapping
            if zoho_item_name == 'Manual Entry':
                rate = float(mapping_info.get('rate', 0))
                cost = rate * quantity
                return round(cost, 2)
        else:
            zoho_item_name = mapping_info
        
        # Get pricing data
        if not self.pricing_data:
            self.pricing_data = self._load_cached_data()
        
        items = self.pricing_data.get('items', [])
        
        # Find matching item
        item = None
        for zoho_item in items:
            # Check if zoho_item is a dictionary before calling .get()
            if isinstance(zoho_item, dict) and zoho_item.get('name', '').lower() == zoho_item_name.lower():
                item = zoho_item
                break
        
        if not item:
            print(f"Material not found in pricing data: {zoho_item_name}")
            return 0.0
        
        # Get rate from item (use purchase_rate as the cost)
        rate = float(item.get('purchase_rate', item.get('rate', 0)))
        
        # Calculate cost based on unit type
        if unit_type.lower() in ['lf', 'linear_foot', 'linear']:
            # For linear foot materials (like wire shelves)
            cost = rate * quantity
        elif unit_type.lower() in ['sf', 'square_foot', 'square']:
            # For square foot materials (like melamine sheets)
            cost = rate * quantity
        else:
            # For unit-based materials
            cost = rate * quantity
        
        return round(cost, 2)
    
    def get_material_info(self, material_name: str) -> Dict[str, Any]:
        """Get detailed material information including Zoho Books mapping"""
        if not self.pricing_data:
            self.pricing_data = self._load_cached_data()
        
        # Get mapping info
        mapping_info = self.material_mappings.get(material_name, {})
        if isinstance(mapping_info, dict):
            zoho_item_name = mapping_info.get('zoho_item', material_name)
            unit_type = mapping_info.get('unit_type', 'SI')
            rate = mapping_info.get('rate', 0)
        else:
            # Legacy string mapping
            zoho_item_name = mapping_info
            unit_type = 'SI'
            rate = 0
        
        # Find Zoho Books item details
        items = self.pricing_data.get('items', [])
        zoho_item = None
        for item in items:
            # Check if item is a dictionary before calling .get()
            if isinstance(item, dict) and item.get('name', '').lower() == zoho_item_name.lower():
                zoho_item = item
                break
        
        if zoho_item:
            rate = float(zoho_item.get('purchase_rate', zoho_item.get('rate', 0)))
            unit_type = zoho_item.get('unit', 'SF')
        
        return {
            'omnipop_material': material_name,
            'zoho_item': zoho_item_name,
            'unit_type': unit_type,
            'rate': rate,
            'found': zoho_item is not None
        }
    
    def calculate_parts_material_cost(self, part_list: List[Dict]) -> Dict[str, Any]:
        """Calculate total material cost for a list of parts"""
        if not part_list:
            return {
                'total_cost': 0.0,
                'breakdown': [],
                'error': 'No parts provided'
            }
        
        total_cost = 0.0
        breakdown = []
        
        # Group identical parts
        part_groups = {}
        for part in part_list:
            part_key = f"{part.get('name', '')}_{part.get('w', 0)}_{part.get('h', 0)}_{part.get('th', 0)}"
            
            if part_key not in part_groups:
                part_groups[part_key] = {
                    'name': part.get('name', ''),
                    'quantity': 0,
                    'width': part.get('w', 0),
                    'height': part.get('h', 0),
                    'thickness': part.get('th', 0),
                    'material': part.get('material', 'Melamine')
                }
            
            part_groups[part_key]['quantity'] += part.get('qty', 1)
        
        # Calculate cost for each part group
        for part_key, part_data in part_groups.items():
            material_name = part_data['material']
            quantity = part_data['quantity']
            
            # Determine unit type and quantity based on material
            if 'wire' in material_name.lower():
                unit_type = 'LF'
                # For wire shelves, quantity is linear feet
                unit_quantity = part_data['width'] * quantity / 12.0  # Convert inches to feet
            elif material_name.lower() in ['melamine', 'back panel', 'base', 'canopy', 'mdf']:
                # For sheet materials, use the conversion system
                material_info = self.get_material_info(material_name)
                if material_info and 'source_unit_type' in material_info and 'target_unit_type' in material_info:
                    source_unit = material_info['source_unit_type']
                    target_unit = material_info['target_unit_type']
                    
                    if source_unit == 'PCS' and target_unit == 'SI':
                        # Convert from pieces to square inches
                        if 'piece_dimensions' in material_info:
                            piece_width = material_info['piece_dimensions'].get('width', 0)
                            piece_height = material_info['piece_dimensions'].get('height', 0)
                            piece_sq_inches = piece_width * piece_height
                            part_sq_inches = part_data['width'] * part_data['height']
                            # Calculate how many pieces are needed
                            unit_quantity = (part_sq_inches * quantity) / piece_sq_inches
                            unit_type = 'PCS'
                        else:
                            # Fallback to square inches
                            unit_quantity = part_data['width'] * part_data['height'] * quantity
                            unit_type = 'SI'
                    elif source_unit == 'SI' and target_unit == 'SI':
                        # Direct square inches calculation
                        unit_quantity = part_data['width'] * part_data['height'] * quantity
                        unit_type = 'SI'
                    elif source_unit == 'LI' and target_unit == 'LI':
                        # Direct linear inches calculation
                        unit_quantity = part_data['width'] * quantity
                        unit_type = 'LI'
                    else:
                        # Use the target unit type directly
                        unit_quantity = quantity
                        unit_type = target_unit
                else:
                    # Fallback to square inches if no conversion info
                    unit_quantity = part_data['width'] * part_data['height'] * quantity
                    unit_type = 'SI'
            else:
                unit_type = 'unit'
                unit_quantity = quantity
            
            # Calculate cost
            cost = self.get_material_cost(material_name, unit_quantity, unit_type)
            total_cost += cost
            
            breakdown.append({
                'name': part_data['name'],
                'quantity': quantity,
                'material': material_name,
                'unit_type': unit_type,
                'unit_quantity': unit_quantity,
                'cost': cost,
                'dimensions': f"{part_data['width']}\" × {part_data['height']}\" × {part_data['thickness']}\""
            })
        
        return {
            'total_cost': round(total_cost, 2),
            'breakdown': breakdown,
            'part_count': len(part_list),
            'unique_parts': len(part_groups)
        }
    
    def get_pricing_summary(self) -> Dict[str, Any]:
        """Get summary of current pricing data"""
        if not self.pricing_data:
            self.pricing_data = self._load_cached_data()
        
        items = self.pricing_data.get('items', [])
        last_updated = self.pricing_data.get('last_updated', 0)
        
        return {
            'item_count': len(items),
            'last_updated': last_updated,
            'cache_age_hours': (time.time() - last_updated) / 3600 if last_updated else 0,
            'organization_id': self.pricing_data.get('organization_id'),
            'is_authenticated': self.auth_handler.is_authenticated()
        }
    
    def refresh_pricing_data(self) -> bool:
        """Refresh pricing data from Zoho Books"""
        try:
            self.pricing_data = self.fetch_and_cache_pricing()
            return True
        except Exception as e:
            print(f"Error refreshing pricing data: {e}")
            return False
    
    def get_material_suggestions(self, search_term: str) -> List[Dict]:
        """Get material suggestions based on search term"""
        if not self.pricing_data:
            self.pricing_data = self._load_cached_data()
        
        items = self.pricing_data.get('items', [])
        suggestions = []
        
        for item in items:
            name = item.get('name', '').lower()
            if search_term.lower() in name:
                suggestions.append({
                    'name': item.get('name'),
                    'rate': item.get('rate', 0),
                    'description': item.get('description', ''),
                    'item_id': item.get('item_id')
                })
        
        return suggestions[:10]  # Limit to 10 suggestions
    
    def validate_pricing_data(self) -> Dict[str, Any]:
        """Validate that pricing data is complete and accurate"""
        if not self.pricing_data:
            self.pricing_data = self._load_cached_data()
        
        items = self.pricing_data.get('items', [])
        required_materials = [
            'Melamine 3/4in',
            'Wire Shelf 12in',
            'Wire Shelf 16in', 
            'Wire Shelf 24in',
            'Wire Shelf 36in',
            'Wire Shelf 48in',
            'Back Panel Material',
            'Base Material',
            'Canopy Material'
        ]
        
        found_materials = []
        missing_materials = []
        
        for required in required_materials:
            found = False
            for item in items:
                if item.get('name', '').lower() == required.lower():
                    found_materials.append({
                        'name': item.get('name'),
                        'rate': item.get('rate', 0),
                        'status': 'Found'
                    })
                    found = True
                    break
            
            if not found:
                missing_materials.append(required)
        
        return {
            'total_items': len(items),
            'found_materials': found_materials,
            'missing_materials': missing_materials,
            'completeness_percent': len(found_materials) / len(required_materials) * 100,
            'is_complete': len(missing_materials) == 0
        }


# Test function
if __name__ == "__main__":
    from zoho_auth import ZohoAuth
    from zoho_client import ZohoBooksClient
    
    auth = ZohoAuth()
    if auth.is_authenticated():
        client = ZohoBooksClient(auth)
        manager = PricingManager(auth, client)
        
        print("Fetching pricing data...")
        manager.fetch_and_cache_pricing()
        
        print("Validating pricing data...")
        validation = manager.validate_pricing_data()
        print(f"Completeness: {validation['completeness_percent']:.1f}%")
        
        # Test material cost calculation
        test_cost = manager.get_material_cost('Melamine', 1.0, 'SI')
        print(f"Test cost for 1 SI of Melamine: ${test_cost}")
    else:
        print("Not authenticated")
