"""
Pricing Settings Dialog
Modal dialog for configuring pricing parameters
"""

import tkinter as tk
from tkinter import ttk, messagebox
from labor_calculator import LaborCalculator


class PricingSettingsDialog:
    """Dialog for configuring pricing settings"""
    
    def __init__(self, parent, labor_calculator: LaborCalculator, zoho_client=None, pricing_manager=None):
        self.parent = parent
        self.labor_calculator = labor_calculator
        self.zoho_client = zoho_client
        self.pricing_manager = pricing_manager
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Pricing Settings")
        self.dialog.geometry("500x600")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"500x600+{x}+{y}")
        
        self._create_widgets()
        self._load_current_settings()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame with scrollbar
        main_frame = tk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Title
        title_label = tk.Label(scrollable_frame, text="Pricing Configuration", 
                              font=("Arial", 14, "bold"), fg="#2E7D32")
        title_label.pack(pady=(0, 20))
        
        # Overhead Rate Section
        overhead_frame = tk.LabelFrame(scrollable_frame, text="Overhead Rate", 
                                     font=("Arial", 10, "bold"), padx=10, pady=10)
        overhead_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(overhead_frame, text="Overhead Rate per Hour ($):").pack(anchor=tk.W)
        self.overhead_rate_var = tk.StringVar()
        self.overhead_rate_entry = tk.Entry(overhead_frame, textvariable=self.overhead_rate_var,
                                           font=("Arial", 10), width=20)
        self.overhead_rate_entry.pack(anchor=tk.W, pady=(5, 0))
        
        # Materials Manager Section
        materials_frame = tk.LabelFrame(scrollable_frame, text="Materials Management", 
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
        materials_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(materials_frame, text="Manage material mappings between OmniPOP and Zoho Books:").pack(anchor=tk.W)
        
        materials_button = tk.Button(materials_frame, text="Open Materials Manager", 
                                   command=self._open_materials_manager,
                                   bg="#2196F3", fg="white", 
                                   font=("Arial", 10, "bold"))
        materials_button.pack(anchor=tk.W, pady=(10, 0))
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Button frame
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Buttons
        self.save_button = tk.Button(button_frame, text="Save Settings", 
                                    command=self._save_settings, 
                                    bg="#4CAF50", fg="white", 
                                    font=("Arial", 10, "bold"),
                                    padx=20, pady=8)
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.reset_button = tk.Button(button_frame, text="Reset to Defaults", 
                                     command=self._reset_defaults,
                                     bg="#FF9800", fg="white",
                                     font=("Arial", 10),
                                     padx=15, pady=8)
        self.reset_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_button = tk.Button(button_frame, text="Cancel", 
                                      command=self._cancel,
                                      font=("Arial", 10),
                                      padx=20, pady=8)
        self.cancel_button.pack(side=tk.LEFT)
    
    def _load_current_settings(self):
        """Load current settings into the form"""
        config = self.labor_calculator.get_config()
        
        # Load overhead rate
        self.overhead_rate_var.set(str(config.get('overhead_rate_per_hour', 30.0)))
    
    def _save_settings(self):
        """Save settings to configuration"""
        try:
            # Validate and collect settings
            new_config = {}
            
            # Overhead rate
            try:
                overhead_rate = float(self.overhead_rate_var.get())
                if overhead_rate < 0:
                    raise ValueError("Overhead rate must be positive")
                new_config['overhead_rate_per_hour'] = overhead_rate
            except ValueError as e:
                messagebox.showerror("Invalid Input", f"Overhead rate: {e}")
                return
            
            
            # Save configuration
            self.labor_calculator.update_config(new_config)
            
            messagebox.showinfo("Settings Saved", "Pricing settings have been saved successfully.")
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def _reset_defaults(self):
        """Reset settings to defaults"""
        if messagebox.askyesno("Reset to Defaults", 
                              "Are you sure you want to reset all settings to defaults?"):
            self.labor_calculator.reset_to_defaults()
            self._load_current_settings()
            messagebox.showinfo("Settings Reset", "Settings have been reset to defaults.")
    
    def _open_materials_manager(self):
        """Open materials manager dialog"""
        if self.zoho_client and self.pricing_manager:
            from materials_manager_dialog import show_materials_manager
            show_materials_manager(self.dialog, self.zoho_client, self.pricing_manager)
        else:
            messagebox.showwarning("Warning", "Zoho Books connection required for materials manager")
    
    def _cancel(self):
        """Cancel without saving"""
        self.result = False
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result


# Test function
if __name__ == "__main__":
    from labor_calculator import LaborCalculator
    
    root = tk.Tk()
    root.withdraw()
    
    calculator = LaborCalculator()
    dialog = PricingSettingsDialog(root, calculator)
    result = dialog.show()
    
    if result:
        print("Settings saved!")
    else:
        print("Settings cancelled.")
    
    root.destroy()
