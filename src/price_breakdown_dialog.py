"""
Price Breakdown Dialog
Shows detailed material costs with rates, units, and totals
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any


class PriceBreakdownDialog:
    """Modal dialog showing detailed price breakdown"""
    
    def __init__(self, parent, pricing_data: Dict[str, Any]):
        self.parent = parent
        self.pricing_data = pricing_data
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Price Breakdown")
        self.dialog.geometry("800x600")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"800x600+{x}+{y}")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame
        main_frame = tk.Frame(self.dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Price Breakdown", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Materials tab
        materials_frame = ttk.Frame(notebook)
        notebook.add(materials_frame, text="Materials")
        self._create_materials_tab(materials_frame)
        
        # Labor tab
        labor_frame = ttk.Frame(notebook)
        notebook.add(labor_frame, text="Labor & Overhead")
        self._create_labor_tab(labor_frame)
        
        # Summary tab
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="Summary")
        self._create_summary_tab(summary_frame)
        
        # Close button
        close_button = tk.Button(main_frame, text="Close", 
                                command=self.dialog.destroy,
                                bg="#4CAF50", fg="white", 
                                font=("Arial", 10, "bold"))
        close_button.pack(pady=(20, 0))
    
    def _create_materials_tab(self, parent):
        """Create materials breakdown tab"""
        # Materials breakdown frame
        materials_frame = tk.Frame(parent, padx=10, pady=10)
        materials_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        tk.Label(materials_frame, text="Material Costs", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Create treeview for materials
        columns = ("Material", "Zoho Item", "Unit Type", "Rate/Unit", "Quantity", "Total Cost")
        tree = ttk.Treeview(materials_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        tree.heading("Material", text="OmniPOP Material")
        tree.heading("Zoho Item", text="Zoho Books Item")
        tree.heading("Unit Type", text="Unit Type")
        tree.heading("Rate/Unit", text="Rate/Unit")
        tree.heading("Quantity", text="Quantity")
        tree.heading("Total Cost", text="Total Cost")
        
        tree.column("Material", width=150)
        tree.column("Zoho Item", width=200)
        tree.column("Unit Type", width=80)
        tree.column("Rate/Unit", width=100)
        tree.column("Quantity", width=80)
        tree.column("Total Cost", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(materials_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate materials data
        self._populate_materials_tree(tree)
        
        # Total materials cost
        total_frame = tk.Frame(materials_frame)
        total_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Label(total_frame, text="Total Materials Cost:", 
                font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        total_cost = self.pricing_data.get('material_cost', 0)
        tk.Label(total_frame, text=f"${total_cost:,.2f}", 
                font=("Arial", 10, "bold"), fg="green").pack(side=tk.RIGHT)
    
    def _create_labor_tab(self, parent):
        """Create labor and overhead tab"""
        labor_frame = tk.Frame(parent, padx=10, pady=10)
        labor_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        tk.Label(labor_frame, text="Labor & Overhead Costs", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Labor details
        labor_data = self.pricing_data.get('labor_data', {})
        
        # Base hours
        base_hours = labor_data.get('base_hours', 0)
        tk.Label(labor_frame, text=f"Base Hours: {base_hours:.1f} hrs", 
                font=("Arial", 10)).pack(anchor=tk.W, pady=2)
        
        # Complexity factors
        factors = labor_data.get('complexity_factors', {})
        if factors:
            tk.Label(labor_frame, text="Complexity Factors:", 
                    font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
            
            for factor, value in factors.items():
                tk.Label(labor_frame, text=f"  {factor}: {value:.1f} hrs", 
                        font=("Arial", 9)).pack(anchor=tk.W, pady=1)
        
        # Total hours
        total_hours = labor_data.get('total_hours', 0)
        tk.Label(labor_frame, text=f"Total Hours: {total_hours:.1f} hrs", 
                font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
        
        # Labor cost
        labor_cost = self.pricing_data.get('labor_cost', 0)
        tk.Label(labor_frame, text=f"Labor Cost: ${labor_cost:,.2f}", 
                font=("Arial", 10, "bold"), fg="blue").pack(anchor=tk.W, pady=5)
        
        # Overhead cost
        overhead_cost = self.pricing_data.get('overhead_cost', 0)
        tk.Label(labor_frame, text=f"Overhead Cost: ${overhead_cost:,.2f}", 
                font=("Arial", 10, "bold"), fg="orange").pack(anchor=tk.W, pady=5)
    
    def _create_summary_tab(self, parent):
        """Create summary tab"""
        summary_frame = tk.Frame(parent, padx=10, pady=10)
        summary_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        tk.Label(summary_frame, text="Pricing Summary", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 20))
        
        # Summary details
        material_cost = self.pricing_data.get('material_cost', 0)
        labor_cost = self.pricing_data.get('labor_cost', 0)
        overhead_cost = self.pricing_data.get('overhead_cost', 0)
        total_cost = self.pricing_data.get('total_cost', 0)
        
        # Create summary table
        summary_data = [
            ("Materials", f"${material_cost:,.2f}"),
            ("Labor", f"${labor_cost:,.2f}"),
            ("Overhead", f"${overhead_cost:,.2f}"),
            ("", ""),  # Separator
            ("TOTAL", f"${total_cost:,.2f}")
        ]
        
        for i, (label, value) in enumerate(summary_data):
            if label == "":  # Separator
                tk.Frame(summary_frame, height=2, bg="gray").pack(fill=tk.X, pady=5)
            else:
                row_frame = tk.Frame(summary_frame)
                row_frame.pack(fill=tk.X, pady=2)
                
                tk.Label(row_frame, text=label, font=("Arial", 10)).pack(side=tk.LEFT)
                tk.Label(row_frame, text=value, font=("Arial", 10, "bold"), 
                        fg="green" if label == "TOTAL" else "black").pack(side=tk.RIGHT)
    
    def _populate_materials_tree(self, tree):
        """Populate materials tree with data"""
        materials_breakdown = self.pricing_data.get('materials_breakdown', [])
        
        for item in materials_breakdown:
            tree.insert("", tk.END, values=(
                item.get('name', ''),
                item.get('zoho_item', ''),
                item.get('unit_type', ''),
                f"${item.get('rate', 0):.2f}",
                f"{item.get('quantity', 0):.2f}",
                f"${item.get('cost', 0):.2f}"
            ))


def show_price_breakdown(parent, pricing_data):
    """Show price breakdown dialog"""
    dialog = PriceBreakdownDialog(parent, pricing_data)
    dialog.dialog.wait_window()
