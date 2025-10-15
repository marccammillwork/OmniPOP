"""
Labor and Overhead Calculator
Calculates labor hours and overhead costs based on unit type and specifications
"""

import os
import json
import time
from typing import Dict, List, Optional, Any, Tuple


class LaborCalculator:
    """Calculates labor hours and overhead costs for unit production"""
    
    BASE_HOURS_BY_UNIT_TYPE = {
        "Endcap": 4.0,
        "Bookcase": 3.5,
        "Slice Rack": 5.0,
        "Bunker": 2.5
    }
    
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser("~"), ".omnipop_pricing_config.json")
        self.config = self._load_config()
        self.historical_data = self._load_historical_data()
        
    def _load_config(self) -> Dict:
        """Load pricing configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Default configuration
        return {
            "overhead_rate_per_hour": 30.0,
            "default_profit_margin_percent": 30.0,
            "labor_complexity_multipliers": {
                "per_shelf": 0.5,
                "canopy_addition": 2.0,
                "per_inch_side_wall": 0.1,
                "wire_shelf_factor": 0.3,
                "fascia_addition": 1.5,
                "per_column": 1.0,
                "per_pole": 0.5
            }
        }
    
    def _save_config(self):
        """Save pricing configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Error saving pricing config: {e}")
    
    def _load_historical_data(self) -> List[Dict]:
        """Load historical labor data for verification"""
        historical_file = os.path.join(os.path.expanduser("~"), ".omnipop_historical_labor.json")
        if os.path.exists(historical_file):
            try:
                with open(historical_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []
    
    def _save_historical_data(self):
        """Save historical labor data"""
        historical_file = os.path.join(os.path.expanduser("~"), ".omnipop_historical_labor.json")
        try:
            with open(historical_file, 'w') as f:
                json.dump(self.historical_data, f, indent=2)
        except IOError as e:
            print(f"Error saving historical data: {e}")
    
    def calculate(self, unit_type: str, width: float, height: float, depth: float,
                 part_count: int, has_canopy: bool = False, has_fascia: bool = False,
                 shelf_count: int = 0, wire_shelves: bool = False, 
                 side_wall_length: float = 0, column_count: int = 0,
                 pole_count: int = 0) -> Dict[str, Any]:
        """Calculate labor hours and overhead costs"""
        
        # For now, return 0 for all labor and overhead calculations
        # This allows us to focus on getting materials pricing working
        breakdown = {
            'base_hours': 0.0,
            'complexity_factors': {},
            'total_hours': 0.0,
            'overhead_rate': self.config['overhead_rate_per_hour'],
            'overhead_cost': 0.0,
            'labor_cost': 0.0,
            'unit_type': unit_type,
            'dimensions': f"{width}\" × {depth}\" × {height}\"",
            'part_count': part_count
        }
        
        return breakdown
    
    def _add_historical_record(self, breakdown: Dict):
        """Add calculation to historical data"""
        record = {
            'timestamp': time.time(),
            'unit_type': breakdown['unit_type'],
            'dimensions': breakdown['dimensions'],
            'part_count': breakdown['part_count'],
            'total_hours': breakdown['total_hours'],
            'overhead_cost': breakdown['overhead_cost'],
            'complexity_factors': breakdown['complexity_factors']
        }
        
        self.historical_data.append(record)
        
        # Keep only last 1000 records
        if len(self.historical_data) > 1000:
            self.historical_data = self.historical_data[-1000:]
        
        self._save_historical_data()
    
    def get_historical_analysis(self, unit_type: str = None, days: int = 30) -> Dict[str, Any]:
        """Analyze historical labor data"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        recent_data = [record for record in self.historical_data 
                      if record['timestamp'] > cutoff_time]
        
        if unit_type:
            recent_data = [record for record in recent_data 
                          if record['unit_type'] == unit_type]
        
        if not recent_data:
            return {
                'record_count': 0,
                'average_hours': 0,
                'average_cost': 0,
                'hour_range': (0, 0),
                'cost_range': (0, 0)
            }
        
        hours = [record['total_hours'] for record in recent_data]
        costs = [record['overhead_cost'] for record in recent_data]
        
        return {
            'record_count': len(recent_data),
            'average_hours': sum(hours) / len(hours),
            'average_cost': sum(costs) / len(costs),
            'hour_range': (min(hours), max(hours)),
            'cost_range': (min(costs), max(costs)),
            'total_hours': sum(hours),
            'total_cost': sum(costs)
        }
    
    def update_config(self, new_config: Dict):
        """Update pricing configuration"""
        self.config.update(new_config)
        self._save_config()
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self.config.copy()
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = {
            "overhead_rate_per_hour": 30.0,
            "default_profit_margin_percent": 30.0,
            "labor_complexity_multipliers": {
                "per_shelf": 0.5,
                "canopy_addition": 2.0,
                "per_inch_side_wall": 0.1,
                "wire_shelf_factor": 0.3,
                "fascia_addition": 1.5,
                "per_column": 1.0,
                "per_pole": 0.5
            }
        }
        self._save_config()
    
    def calculate_profit_margin(self, material_cost: float, labor_cost: float, 
                              overhead_cost: float, profit_percent: float = None) -> Dict[str, Any]:
        """Calculate profit margin and total price"""
        if profit_percent is None:
            profit_percent = self.config['default_profit_margin_percent']
        
        subtotal = material_cost + labor_cost + overhead_cost
        profit_amount = subtotal * (profit_percent / 100)
        total_price = subtotal + profit_amount
        
        return {
            'material_cost': material_cost,
            'labor_cost': labor_cost,
            'overhead_cost': overhead_cost,
            'subtotal': subtotal,
            'profit_percent': profit_percent,
            'profit_amount': profit_amount,
            'total_price': total_price
        }
    
    def get_efficiency_metrics(self) -> Dict[str, Any]:
        """Get efficiency metrics from historical data"""
        if not self.historical_data:
            return {
                'total_units': 0,
                'total_hours': 0,
                'average_hours_per_unit': 0,
                'most_common_unit_type': None,
                'efficiency_trend': 'No data'
            }
        
        # Analyze by unit type
        unit_type_counts = {}
        unit_type_hours = {}
        
        for record in self.historical_data:
            unit_type = record['unit_type']
            unit_type_counts[unit_type] = unit_type_counts.get(unit_type, 0) + 1
            unit_type_hours[unit_type] = unit_type_hours.get(unit_type, 0) + record['total_hours']
        
        # Find most common unit type
        most_common = max(unit_type_counts.items(), key=lambda x: x[1])[0] if unit_type_counts else None
        
        # Calculate efficiency trend (last 30 days vs previous 30 days)
        now = time.time()
        recent_cutoff = now - (30 * 24 * 60 * 60)
        older_cutoff = now - (60 * 24 * 60 * 60)
        
        recent_data = [r for r in self.historical_data if r['timestamp'] > recent_cutoff]
        older_data = [r for r in self.historical_data 
                     if older_cutoff < r['timestamp'] <= recent_cutoff]
        
        if recent_data and older_data:
            recent_avg = sum(r['total_hours'] for r in recent_data) / len(recent_data)
            older_avg = sum(r['total_hours'] for r in older_data) / len(older_data)
            
            if recent_avg < older_avg:
                trend = 'Improving'
            elif recent_avg > older_avg:
                trend = 'Declining'
            else:
                trend = 'Stable'
        else:
            trend = 'Insufficient data'
        
        return {
            'total_units': len(self.historical_data),
            'total_hours': sum(r['total_hours'] for r in self.historical_data),
            'average_hours_per_unit': sum(r['total_hours'] for r in self.historical_data) / len(self.historical_data) if self.historical_data else 0,
            'most_common_unit_type': most_common,
            'efficiency_trend': trend,
            'unit_type_breakdown': unit_type_counts
        }


# Test function
if __name__ == "__main__":
    calculator = LaborCalculator()
    
    # Test calculation
    result = calculator.calculate(
        unit_type="Endcap",
        width=36,
        height=90,
        depth=30,
        part_count=15,
        has_canopy=True,
        shelf_count=4,
        side_wall_length=24,
        column_count=1,
        pole_count=2
    )
    
    print("Labor Calculation Result:")
    print(f"Total Hours: {result['total_hours']:.2f}")
    print(f"Overhead Cost: ${result['overhead_cost']:.2f}")
    print(f"Complexity Factors: {result['complexity_factors']}")
    
    # Test profit calculation
    profit_result = calculator.calculate_profit_margin(
        material_cost=500.0,
        labor_cost=result['labor_cost'],
        overhead_cost=result['overhead_cost'],
        profit_percent=30.0
    )
    
    print(f"\nTotal Price: ${profit_result['total_price']:.2f}")
    
    # Test historical analysis
    analysis = calculator.get_historical_analysis()
    print(f"\nHistorical Analysis: {analysis['record_count']} records")
