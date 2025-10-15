"""
Materials Manager Dialog
Manages mapping between OmniPOP materials and Zoho Books items
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Any, Optional
import json
import os


class MaterialsManagerDialog:
    """Dialog for managing material mappings"""
    
    def __init__(self, parent, zoho_client, pricing_manager):
        self.parent = parent
        self.zoho_client = zoho_client
        self.pricing_manager = pricing_manager
        self.material_mappings = self._load_material_mappings()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Materials Manager")
        self.dialog.geometry("1000x700")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (1000 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (700 // 2)
        self.dialog.geometry(f"1000x700+{x}+{y}")
        
        self._create_widgets()
        self._load_data()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame
        main_frame = tk.Frame(self.dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Materials Manager", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Create paned window for split view
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Left side - Zoho Books items
        left_frame = ttk.Frame(paned_window)
        paned_window.add(left_frame, weight=1)
        
        tk.Label(left_frame, text="Zoho Books Items", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Zoho items treeview
        self.zoho_tree = ttk.Treeview(left_frame, columns=("Name", "Rate", "Unit"), 
                                     show="headings", height=15)
        self.zoho_tree.heading("Name", text="Item Name")
        self.zoho_tree.heading("Rate", text="Rate")
        self.zoho_tree.heading("Unit", text="Unit")
        
        self.zoho_tree.column("Name", width=300)
        self.zoho_tree.column("Rate", width=100)
        self.zoho_tree.column("Unit", width=80)
        
        # Zoho items scrollbar
        zoho_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, 
                                     command=self.zoho_tree.yview)
        self.zoho_tree.configure(yscrollcommand=zoho_scrollbar.set)
        
        self.zoho_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        zoho_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right side - OmniPOP materials
        right_frame = ttk.Frame(paned_window)
        paned_window.add(right_frame, weight=1)
        
        tk.Label(right_frame, text="OmniPOP Materials", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # OmniPOP materials treeview
        self.omnipop_tree = ttk.Treeview(right_frame, columns=("Material", "Zoho Item", "Unit Type", "Rate"), 
                                        show="headings", height=15)
        self.omnipop_tree.heading("Material", text="OmniPOP Material")
        self.omnipop_tree.heading("Zoho Item", text="Mapped Zoho Item")
        self.omnipop_tree.heading("Unit Type", text="Unit Type")
        self.omnipop_tree.heading("Rate", text="Rate")
        
        self.omnipop_tree.column("Material", width=150)
        self.omnipop_tree.column("Zoho Item", width=200)
        self.omnipop_tree.column("Unit Type", width=100)
        self.omnipop_tree.column("Rate", width=100)
        
        # OmniPOP materials scrollbar
        omnipop_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, 
                                        command=self.omnipop_tree.yview)
        self.omnipop_tree.configure(yscrollcommand=omnipop_scrollbar.set)
        
        self.omnipop_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        omnipop_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Mapping controls
        mapping_frame = tk.Frame(main_frame)
        mapping_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(mapping_frame, text="Material Mapping:", 
                font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        # Unit type conversion
        tk.Label(mapping_frame, text="From:").pack(side=tk.LEFT, padx=(0, 5))
        self.source_unit_type_var = tk.StringVar(value="PCS")
        source_unit_combo = ttk.Combobox(mapping_frame, textvariable=self.source_unit_type_var, 
                                        values=["EA", "PCS", "LI", "SI"], width=5)
        source_unit_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(mapping_frame, text="To:").pack(side=tk.LEFT, padx=(0, 5))
        self.target_unit_type_var = tk.StringVar(value="SI")
        target_unit_combo = ttk.Combobox(mapping_frame, textvariable=self.target_unit_type_var, 
                                        values=["EA", "PCS", "LI", "SI"], width=5)
        target_unit_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # Conversion dimensions (for PCS to SI conversion)
        tk.Label(mapping_frame, text="Piece Width:").pack(side=tk.LEFT, padx=(0, 5))
        self.piece_width_var = tk.StringVar(value="48")
        piece_width_entry = tk.Entry(mapping_frame, textvariable=self.piece_width_var, width=8)
        piece_width_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(mapping_frame, text="Piece Height:").pack(side=tk.LEFT, padx=(0, 5))
        self.piece_height_var = tk.StringVar(value="96")
        piece_height_entry = tk.Entry(mapping_frame, textvariable=self.piece_height_var, width=8)
        piece_height_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Manual price editing
        tk.Label(mapping_frame, text="Manual Price:").pack(side=tk.LEFT, padx=(0, 5))
        self.manual_price_var = tk.StringVar(value="0.00")
        manual_price_entry = tk.Entry(mapping_frame, textvariable=self.manual_price_var, width=10)
        manual_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Map button
        map_button = tk.Button(mapping_frame, text="Map Selected", 
                             command=self._map_materials,
                             bg="#4CAF50", fg="white", font=("Arial", 9, "bold"))
        map_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Unmap button
        unmap_button = tk.Button(mapping_frame, text="Unmap", 
                               command=self._unmap_material,
                               bg="#f44336", fg="white", font=("Arial", 9, "bold"))
        unmap_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Manual edit button
        manual_edit_button = tk.Button(mapping_frame, text="Edit Manually", 
                                      command=self._edit_material_manually,
                                      bg="#FF9800", fg="white", font=("Arial", 9, "bold"))
        manual_edit_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Pull from Zoho button
        pull_zoho_button = tk.Button(mapping_frame, text="Pull from Zoho", 
                                    command=self._pull_from_zoho,
                                    bg="#9C27B0", fg="white", font=("Arial", 9, "bold"))
        pull_zoho_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Refresh button
        refresh_button = tk.Button(mapping_frame, text="Refresh Zoho Data", 
                                 command=self._refresh_zoho_data,
                                 bg="#2196F3", fg="white", font=("Arial", 9, "bold"))
        refresh_button.pack(side=tk.LEFT)
        
        # Buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        save_button = tk.Button(button_frame, text="Save Mappings", 
                              command=self._save_mappings,
                              bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        save_button.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_button = tk.Button(button_frame, text="Cancel", 
                                 command=self.dialog.destroy)
        cancel_button.pack(side=tk.LEFT)
    
    def _load_material_mappings(self):
        """Load material mappings from file"""
        mapping_file = os.path.join(os.path.expanduser("~"), ".omnipop_material_mappings.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_material_mappings(self):
        """Save material mappings to file"""
        mapping_file = os.path.join(os.path.expanduser("~"), ".omnipop_material_mappings.json")
        try:
            with open(mapping_file, 'w') as f:
                json.dump(self.material_mappings, f, indent=2)
        except IOError as e:
            messagebox.showerror("Error", f"Failed to save mappings: {e}")
    
    def _load_data(self):
        """Load data into the dialog"""
        self._load_zoho_items()
        self._load_omnipop_materials()
    
    def _load_zoho_items(self):
        """Load Zoho Books items"""
        try:
            # Get items from Zoho Books
            items = self.zoho_client.get_items()
            if items and 'items' in items:
                for item in items['items']:
                    name = item.get('name', '')
                    rate = item.get('purchase_rate', item.get('rate', 0))
                    unit = item.get('unit', '')
                    
                    self.zoho_tree.insert("", tk.END, values=(name, f"${rate:.2f}", unit))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Zoho Books items: {e}")
    
    def _load_omnipop_materials(self):
        """Load OmniPOP materials"""
        # Clear existing items
        for item in self.omnipop_tree.get_children():
            self.omnipop_tree.delete(item)

        # Define fixed OmniPOP material types
        omnipop_materials = [
                # Core Materials
                "Melamine Black",
                "Melamine White",
                "Melamine Gray",
                "Melamine Cherry",
                "Melamine Spring Blossom",
                "Melamine Hardrock Maple",
                "Slatwall",
                "Diamond Plate",
                "Crown Molding",
                
                # Shelving
                "Wire Shelf 12in",
                "Wire Shelf 16in",
                "Wire Shelf 24in",
                "Wire Shelf 36in",
                "Wire Shelf 48in",

                # Hardware & Fasteners
                "PVC Poles",
                "Thin Bumper",
                "Thick Bumper",
                "Screws",
                "Dowels",
                "Glue",
                "Brackets",
                "Standards",
                "Staples",

                # Finishing & Trim
                "Price Channel Tag Molding",
                "T Molding",
                "Edge Banding",
                "Metal Corners",
                "Plastic Corners",
                
                # Accessories
                "Eggcrate",
                "Eggcrate Support",
                "Caster Wheels",
                "Furniture Slides",
                "Header Logos",
                "Panel Logos"
          ]
          
        for material in omnipop_materials:
            # Get mapping info
            mapping_info = self.material_mappings.get(material)
            
            zoho_item = 'Not Mapped'
            unit_type = 'SF'
            rate = 0.0

            if isinstance(mapping_info, dict):
                zoho_item = mapping_info.get('zoho_item', 'Not Mapped')
                source_unit = mapping_info.get('source_unit_type', 'SI')
                target_unit = mapping_info.get('target_unit_type', 'SI')
                rate = mapping_info.get('rate', 0)
                
                
                # Calculate converted rate and show piece dimensions if available
                if 'piece_dimensions' in mapping_info:
                    piece_width = mapping_info['piece_dimensions'].get('width', 0)
                    piece_height = mapping_info['piece_dimensions'].get('height', 0)
                    piece_sq_inches = piece_width * piece_height
                    
                    if source_unit == 'PCS' and target_unit == 'SI':
                        # Convert from price per piece to price per square inch
                        old_rate = rate
                        rate = rate / piece_sq_inches if piece_sq_inches > 0 else 0
                        unit_type = 'SI'
                        zoho_item = f"{zoho_item} ({piece_width}x{piece_height})"
                    elif source_unit == 'PCS' and target_unit == 'PCS':
                        # Keep as pieces but show dimensions
                        unit_type = 'PCS'
                        zoho_item = f"{zoho_item} ({piece_width}x{piece_height})"
                    else:
                        unit_type = target_unit
                        zoho_item = f"{zoho_item} ({piece_width}x{piece_height})"
                else:
                    # No piece dimensions, handle other conversions
                    if source_unit == 'PCS' and target_unit == 'SI':
                        # PCS to SI without piece dimensions - use default 48x96
                        piece_width = 48
                        piece_height = 96
                        piece_sq_inches = piece_width * piece_height
                        rate = rate / piece_sq_inches if piece_sq_inches > 0 else 0
                        unit_type = 'SI'
                        zoho_item = f"{zoho_item} ({piece_width}x{piece_height})"
                    else:
                        # Use target unit type as-is
                        unit_type = target_unit
            elif isinstance(mapping_info, str) and mapping_info:
                # Handle old string-based format
                zoho_item = mapping_info
                unit_type = 'SI'
            
            self.omnipop_tree.insert("", tk.END, values=(
                material, zoho_item, unit_type, f"${rate:.2f}"
            ))
    
    def _map_materials(self):
        """Map selected materials"""
        # Get selected Zoho item
        zoho_selection = self.zoho_tree.selection()
        if not zoho_selection:
            messagebox.showwarning("Warning", "Please select a Zoho Books item")
            return
        
        # Get selected OmniPOP material
        omnipop_selection = self.omnipop_tree.selection()
        if not omnipop_selection:
            messagebox.showwarning("Warning", "Please select an OmniPOP material")
            return
        
        # Get item details
        zoho_item = self.zoho_tree.item(zoho_selection[0])
        zoho_values = zoho_item['values']
        zoho_name = zoho_values[0]
        zoho_rate = float(zoho_values[1].replace('$', ''))
        
        omnipop_item = self.omnipop_tree.item(omnipop_selection[0])
        omnipop_values = omnipop_item['values']
        omnipop_material = omnipop_values[0]
        
        # Get rate (from Zoho or manual)
        try:
            manual_rate = float(self.manual_price_var.get())
            if manual_rate > 0:
                rate = manual_rate
            else:
                rate = zoho_rate
        except ValueError:
            rate = zoho_rate
        
        # Update mapping
        mapping_data = {
            'zoho_item': zoho_name,
            'source_unit_type': self.source_unit_type_var.get(),
            'target_unit_type': self.target_unit_type_var.get(),
            'rate': rate
        }
        
        # Add conversion dimensions if needed
        if self.source_unit_type_var.get() == 'PCS' and self.target_unit_type_var.get() == 'SI':
            try:
                piece_width = float(self.piece_width_var.get())
                piece_height = float(self.piece_height_var.get())
                mapping_data['piece_dimensions'] = {
                    'width': piece_width,
                    'height': piece_height
                }
            except ValueError:
                messagebox.showerror("Error", "Please enter valid piece dimensions")
                return
        
        self.material_mappings[omnipop_material] = mapping_data
        
        # Update display
        self._load_omnipop_materials()
        
        messagebox.showinfo("Success", f"Mapped {omnipop_material} to {zoho_name}")
    
    def _unmap_material(self):
        """Unmap selected material"""
        omnipop_selection = self.omnipop_tree.selection()
        if not omnipop_selection:
            messagebox.showwarning("Warning", "Please select an OmniPOP material to unmap")
            return
        
        omnipop_item = self.omnipop_tree.item(omnipop_selection[0])
        omnipop_values = omnipop_item['values']
        omnipop_material = omnipop_values[0]
        
        # Remove mapping
        if omnipop_material in self.material_mappings:
            del self.material_mappings[omnipop_material]
        
        # Update display
        self._load_omnipop_materials()
        
        messagebox.showinfo("Success", f"Unmapped {omnipop_material}")
    
    def _refresh_zoho_data(self):
        """Refresh Zoho Books data"""
        try:
            # Clear and reload Zoho items
            for item in self.zoho_tree.get_children():
                self.zoho_tree.delete(item)
            
            self._load_zoho_items()
            messagebox.showinfo("Success", "Zoho Books data refreshed")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh Zoho data: {e}")
    
    def _edit_material_manually(self):
        """Edit material manually without Zoho Books"""
        omnipop_selection = self.omnipop_tree.selection()
        if not omnipop_selection:
            messagebox.showwarning("Warning", "Please select an OmniPOP material to edit")
            return
        
        omnipop_item = self.omnipop_tree.item(omnipop_selection[0])
        omnipop_values = omnipop_item['values']
        omnipop_material = omnipop_values[0]
        
        # Get manual values
        try:
            manual_rate = float(self.manual_price_var.get())
            if manual_rate <= 0:
                messagebox.showerror("Error", "Please enter a valid price")
                return
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid price")
            return
        
        # Create manual mapping
        mapping_data = {
            'zoho_item': 'Manual Entry',
            'source_unit_type': self.source_unit_type_var.get(),
            'target_unit_type': self.target_unit_type_var.get(),
            'rate': manual_rate
        }
        
        # Add piece dimensions if needed
        if self.source_unit_type_var.get() == 'PCS' and self.target_unit_type_var.get() in ['SI']:
            try:
                piece_width = float(self.piece_width_var.get())
                piece_height = float(self.piece_height_var.get())
                mapping_data['piece_dimensions'] = {
                    'width': piece_width,
                    'height': piece_height
                }
            except ValueError:
                messagebox.showerror("Error", "Please enter valid piece dimensions")
                return
        
        self.material_mappings[omnipop_material] = mapping_data
        self._load_omnipop_materials()
        messagebox.showinfo("Success", f"Manually edited {omnipop_material}")
    
    def _pull_from_zoho(self):
        """Pull data from selected Zoho Books item"""
        zoho_selection = self.zoho_tree.selection()
        omnipop_selection = self.omnipop_tree.selection()
        
        if not zoho_selection:
            messagebox.showwarning("Warning", "Please select a Zoho Books item")
            return
        
        if not omnipop_selection:
            messagebox.showwarning("Warning", "Please select an OmniPOP material")
            return
        
        # Get Zoho item details
        zoho_item = self.zoho_tree.item(zoho_selection[0])
        zoho_values = zoho_item['values']
        zoho_name = zoho_values[0]
        zoho_rate = float(zoho_values[1].replace('$', ''))
        
        # Update the manual price field with Zoho rate
        self.manual_price_var.set(str(zoho_rate))
        
        messagebox.showinfo("Success", f"Pulled data from {zoho_name}: ${zoho_rate:.2f}")
    
    def _save_mappings(self):
        """Save material mappings"""
        self._save_material_mappings()
        
        # Update pricing manager with new mappings
        self.pricing_manager.material_mappings = self.material_mappings
        
        messagebox.showinfo("Success", "Material mappings saved successfully")
        self.dialog.destroy()


def show_materials_manager(parent, zoho_client, pricing_manager):
    """Show materials manager dialog"""
    dialog = MaterialsManagerDialog(parent, zoho_client, pricing_manager)
    dialog.dialog.wait_window()
