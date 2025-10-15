import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk  # pyright: ignore[reportMissingImports]
import os
import sys
import math
import json

# Import pricing modules
from zoho_auth import ZohoAuth
from zoho_client import ZohoBooksClient
from pricing_manager import PricingManager
from labor_calculator import LaborCalculator
from auth_dialog import PricingAuthDialog
from pricing_settings_dialog import PricingSettingsDialog

class OmniPOPApp:
    def __init__(self, master):
        self.master = master
        self._last_canvas_sizes = {}
        self.display_unit = 'in'  # 'in' for inches, 'mm' for millimeters
        master.title("OmniPOP Design Portal")
        master.geometry("1800x1000")  # Increased window size for 3 viewports
        master.state('zoomed')

        # Initialize constants
        self.base_thickness = 5.25  # base is 5.25"
        self.deck_thickness = 0.75  # deck is 0.75"
        self.shelf_thickness = 0.75
        self.std_offset = 1.0
        self.fullWallVar = tk.BooleanVar(value=False)
        self.part_list = []
        self.unit_type_settings = {}
        self._loading_settings = False
        self._width_warning = False  # Track if width is insufficient for wire shelves

        # Part structure for CAD export
        self.parts = {
            'base': {'thickness': 5.25, 'material': 'MDF'},
            'deck': {'thickness': 0.75, 'material': 'Melamine'},
            'base_panel': {'thickness': 5, 'material': 'MDF'},
            'side_walls': {'thickness': 0.75, 'material': 'Melamine'},
            'back_panel': {'thickness': 0.75, 'material': 'Melamine'},
            'standards': {'thickness': 1, 'material': 'Steel'},
            'shelves': {'thickness': 0.75, 'material': 'Melamine'},
            'top': {'thickness': 8, 'material': 'MDF'}
        }
        
        # Method to get material name with color
        self.get_material_name = lambda material: f"{material} {self.melamine_color_var.get()}" if material == "Melamine" else material

        # Menu Bar
        self.menu_bar = tk.Menu(master)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_file)
        
        # Open submenu with recent files
        self.open_menu = tk.Menu(file_menu, tearoff=0)
        self.open_menu.add_command(label="Open...", command=self.open_file)
        self.open_menu.add_separator()
        self.open_menu.add_command(label="(No recent files)", state="disabled")
        file_menu.add_cascade(label="Open", menu=self.open_menu)
        
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_as_file)
        file_menu.add_separator()
        
        # Export submenu
        export_menu = tk.Menu(file_menu, tearoff=0)
        export_menu.add_command(label="Export DXF", command=self.export_dxf)
        export_menu.add_command(label="Export AutoLISP", command=self.export_autolisp)
        export_menu.add_command(label="Export to CAD", command=self.export_to_cad)
        file_menu.add_cascade(label="Export", menu=export_menu)
        
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=master.quit)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        
        # Pricing Menu
        pricing_menu = tk.Menu(self.menu_bar, tearoff=0)
        pricing_menu.add_command(label="Authenticate Zoho Books...", command=self.authenticate_zoho)
        pricing_menu.add_command(label="Re-authenticate...", command=self.reauthenticate_zoho)
        pricing_menu.add_command(label="Refresh Pricing Data", command=self.refresh_pricing_data)
        pricing_menu.add_separator()
        pricing_menu.add_command(label="View Current Estimate", command=self.toggle_pricing_panel)
        pricing_menu.add_separator()
        pricing_menu.add_command(label="Pricing Settings...", command=self.open_pricing_settings)
        self.menu_bar.add_cascade(label="Pricing", menu=pricing_menu)
        
        # Initialize file tracking
        self.current_file = None
        self.recent_files = []
        self.config_file = os.path.join(os.path.expanduser("~"), ".omnipop_recent_files.json")
        self.load_recent_files()
        
        # Initialize pricing system
        self.zoho_auth = ZohoAuth()
        self.zoho_client = ZohoBooksClient(self.zoho_auth)
        self.pricing_manager = PricingManager(self.zoho_auth, self.zoho_client)
        self.labor_calculator = LaborCalculator()
        self.pricing_panel = None
        self.pricing_data_loaded = False
        
        master.config(menu=self.menu_bar)

        # Create a main frame to hold the paned window and the info bar
        main_frame = ttk.Frame(master)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Main horizontal paned window for left/right split
        self.main_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # UI Frame (Left Side)
        self.left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.left_frame, weight=1)

        # Graphics Frame (Right Side)
        self.right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.right_frame, weight=4)

        # Info Bar at the bottom
        self.info_bar = ttk.Frame(main_frame, relief=tk.SUNKEN)
        self.info_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        self.parts_count_var = tk.StringVar(value="Parts: 0")
        self.parts_count_label = ttk.Label(self.info_bar, textvariable=self.parts_count_var)
        self.parts_count_label.pack(side=tk.RIGHT, padx=5)
        
        self.file_label_var = tk.StringVar(value="New File")
        self.file_label = ttk.Label(self.info_bar, textvariable=self.file_label_var)
        self.file_label.pack(side=tk.LEFT, padx=5)

        # Viewport control frame
        self.viewport_controls = ttk.Frame(self.right_frame)
        self.viewport_controls.pack(fill=tk.X, padx=5, pady=2)

        # Viewport toggle buttons
        self.front_view_var = tk.BooleanVar(value=True)
        self.top_view_var = tk.BooleanVar(value=True)
        self.side_view_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(self.viewport_controls, text="Front View", variable=self.front_view_var, 
                       command=self.toggle_viewport).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(self.viewport_controls, text="Top View", variable=self.top_view_var, 
                       command=self.toggle_viewport).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(self.viewport_controls, text="Side View", variable=self.side_view_var, 
                       command=self.toggle_viewport).pack(side=tk.LEFT, padx=5)

        # Unit toggle button
        self.unit_toggle_button = ttk.Button(self.viewport_controls, text="Show in mm", command=self.toggle_units)
        self.unit_toggle_button.pack(side=tk.LEFT, padx=5)

        # Top right viewport container (fixed height for top area)
        self.viewport_container = ttk.Frame(self.right_frame)
        self.viewport_container.pack(fill=tk.BOTH, expand=True, pady=5)

        # Main viewport container with simple vertical paned window
        self.viewport_paned = ttk.PanedWindow(self.viewport_container, orient=tk.VERTICAL)
        self.viewport_paned.pack(fill=tk.BOTH, expand=True)

        # Top row container for front and top views
        self.top_row_container = ttk.Frame(self.viewport_paned)
        self.top_row_paned = ttk.PanedWindow(self.top_row_container, orient=tk.HORIZONTAL)
        self.top_row_paned.pack(fill=tk.BOTH, expand=True)

        # Viewport frames
        self.front_viewport_frame = ttk.Frame(self.top_row_paned)
        self.top_viewport_frame = ttk.Frame(self.top_row_paned)
        self.side_viewport_frame = ttk.Frame(self.viewport_paned)

        # Add viewports to paned windows
        self.top_row_paned.add(self.front_viewport_frame, weight=1)
        self.top_row_paned.add(self.top_viewport_frame, weight=1)
        self.viewport_paned.add(self.top_row_container, weight=2)
        self.viewport_paned.add(self.side_viewport_frame, weight=1)  # Same width as top view

        # Front Canvas
        self.front_canvas_frame = ttk.Frame(self.front_viewport_frame)
        self.front_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.canvas_front = tk.Canvas(self.front_canvas_frame, width=400, height=300, bg="white")
        self.canvas_front.pack(fill=tk.BOTH, expand=True)
        self.canvas_front.bind("<Configure>", self.on_canvas_resize)

        # Top Canvas
        self.top_canvas_frame = ttk.Frame(self.top_viewport_frame)
        self.top_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.canvas_top = tk.Canvas(self.top_canvas_frame, width=400, height=300, bg="white")
        self.canvas_top.pack(fill=tk.BOTH, expand=True)
        self.canvas_top.bind("<Configure>", self.on_canvas_resize)

        # Side Canvas (NEW)
        self.side_canvas_frame = ttk.Frame(self.side_viewport_frame)
        self.side_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.canvas_side = tk.Canvas(self.side_canvas_frame, width=400, height=300, bg="white")
        self.canvas_side.pack(fill=tk.BOTH, expand=True)
        self.canvas_side.bind("<Configure>", self.on_canvas_resize)

        self.create_ui_elements(self.left_frame)

        # Set initial defaults based on the starting unit type
        self.on_unit_type_change()
        
        # Initialize pricing data on startup if authenticated
        if self.is_zoho_authenticated():
            try:
                self.pricing_manager.fetch_and_cache_pricing()
                self.pricing_data_loaded = True
            except Exception as e:
                print(f"Warning: Could not load pricing data on startup: {e}")

    def toggle_units(self):
        """Toggles the display units between inches and millimeters."""
        if self.display_unit == 'in':
            self.display_unit = 'mm'
            self.unit_toggle_button.config(text="Show in in")
        else:
            self.display_unit = 'in'
            self.unit_toggle_button.config(text="Show in mm")
        self.calculate_values()

    def _get_current_settings(self):
        """Gathers all current settings into a dictionary."""
        settings = {
            'unit_type': self.unitTypeVar.get(),
            'width': self.width_var.get(),
            'depth': self.depth_var.get(),
            'height': self.height_var.get(),
            'side_wall_length': self.sideWallLengthVar.get(),
            'side_wall_toggle': self.sideWallToggleVar.get(),
            'full_wall': self.fullWallVar.get(),
            'top_option': self.top_var.get(),
            'base_option': self.base_var.get(),
            'shelf_type': self.shelfTypeVar.get(),
            'shelf_material': self.shelfMaterialVar.get(),
            'num_shelves': self.numShelvesVar.get(),
            'shelf_spacings': [e['var'].get() for e in self.manualShelfEntries]
        }
        return settings

    def _apply_settings(self, settings):
        """Applies a dictionary of settings to the UI."""
        try:
            self._loading_settings = True
            self.unitTypeVar.set(settings.get('unit_type', 'Endcap'))
            self.width_var.set(settings.get('width', 48.0))
            self.depth_var.set(settings.get('depth', 48.0))
            self.height_var.set(settings.get('height', 96.0))
            self.sideWallLengthVar.set(settings.get('side_wall_length', 25.0))
            self.sideWallToggleVar.set(settings.get('side_wall_toggle', True))
            self.fullWallVar.set(settings.get('full_wall', False))
            self.top_var.set(settings.get('top_option', 'Canopy'))
            self.base_var.set(settings.get('base_option', 'Base'))
            self.shelfTypeVar.set(settings.get('shelf_type', 'Fixed'))
            self.shelfMaterialVar.set(settings.get('shelf_material', 'Melamine'))
            
            # This will trigger on_shelf_count_change, which rebuilds the entries
            self.numShelvesVar.set(settings.get('num_shelves', 0))

            # Wait for shelf entries to be created, then set their values
            self.master.update_idletasks()
            
            spacings = settings.get('shelf_spacings', [])
            for i, spacing in enumerate(spacings):
                if i < len(self.manualShelfEntries):
                    self.manualShelfEntries[i]['var'].set(spacing)
        finally:
            self._loading_settings = False
        
        self.toggle_side_wall_input()
        self.calculate_values()

    def new_file(self) -> None:
        """Prompts to save and then resets the application to its default state."""
        response = messagebox.askyesnocancel("New File", "Do you want to save the current file before creating a new one?")
        if response is None:  # Cancel
            return
        if response is True:  # Yes
            if not self.save_file():
                return # User cancelled the save operation

        # Reset to default state
        default_settings = {
            'unit_type': 'Endcap', 'width': 48.0, 'depth': 48.0, 'height': 90.0,
            'side_wall_length': 25.0, 'side_wall_toggle': True, 'full_wall': False,
            'top_option': 'Canopy', 'base_option': 'Base', 'shelf_type': 'Fixed',
            'shelf_material': 'Melamine', 'num_shelves': 0, 'shelf_spacings': []
        }
        self._apply_settings(default_settings)
        # We need to specifically call on_unit_type_change to set the correct defaults for the new unit type
        self.on_unit_type_change()
        
        # Reset file tracking
        self.current_file = None
        self.file_label_var.set("New File")

    def open_file(self):
        """Prompts to save, then opens a file and applies the settings."""
        response = messagebox.askyesnocancel("Open File", "Do you want to save the current file before opening a new one?")
        if response is None:
            return
        if response is True:
            if not self.save_file():
                return

        filepath = filedialog.askopenfilename(
            title="Open OmniPOP File",
            filetypes=[("OmniPOP Files", "*.omnipop"), ("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r') as f:
                settings = json.load(f)
            self._apply_settings(settings)
            # Update current file and add to recent files
            self.current_file = filepath
            self.file_label_var.set(os.path.basename(filepath))
            self.add_to_recent_files(filepath)
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            messagebox.showerror("Error Opening File", f"Failed to open or read the file.\nError: {e}")

    def load_recent_files(self):
        """Loads recent files from the configuration file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.recent_files = data.get('recent_files', [])
                    # Filter out files that no longer exist
                    self.recent_files = [f for f in self.recent_files if os.path.exists(f)]
                    # Keep only the last 10 recent files
                    self.recent_files = self.recent_files[:10]
            else:
                self.recent_files = []
            self.update_recent_files_menu()
        except (json.JSONDecodeError, IOError):
            self.recent_files = []
            self.update_recent_files_menu()

    def save_recent_files(self):
        """Saves recent files to the configuration file."""
        try:
            data = {'recent_files': self.recent_files}
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass  # Silently fail if we can't save

    def add_to_recent_files(self, filepath):
        """Adds a file to the recent files list."""
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        # Keep only the last 10 recent files
        self.recent_files = self.recent_files[:10]
        self.update_recent_files_menu()
        self.save_recent_files()

    def update_recent_files_menu(self):
        """Updates the recent files submenu."""
        # Clear existing recent file items
        for i in range(self.open_menu.index("end") - 1, 1, -1):  # Go backwards to avoid index issues
            self.open_menu.delete(i)
        
        if self.recent_files:
            for filepath in self.recent_files:
                filename = os.path.basename(filepath)
                self.open_menu.add_command(label=filename, command=lambda f=filepath: self.open_recent_file(f))
        else:
            self.open_menu.add_command(label="(No recent files)", state="disabled")

    def open_recent_file(self, filepath):
        """Opens a recent file."""
        try:
            with open(filepath, 'r') as f:
                settings = json.load(f)
            self._apply_settings(settings)
            self.current_file = filepath
            self.file_label_var.set(os.path.basename(filepath))
            self.add_to_recent_files(filepath)
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            messagebox.showerror("Error Opening File", f"Failed to open or read the file.\nError: {e}")
            # Remove from recent files if it can't be opened
            if filepath in self.recent_files:
                self.recent_files.remove(filepath)
                self.update_recent_files_menu()

    def save_file(self):
        """Saves the current settings to a file."""
        if not hasattr(self, 'current_file') or self.current_file is None:
            return self.save_as_file()
        
        settings = self._get_current_settings()
        try:
            with open(self.current_file, 'w') as f:
                json.dump(settings, f, indent=4)
            # Add to recent files
            self.file_label_var.set(os.path.basename(self.current_file))
            self.add_to_recent_files(self.current_file)
            messagebox.showinfo("File Saved", f"Design saved successfully to:\n{self.current_file}")
            return True # Success
        except IOError as e:
            messagebox.showerror("Error Saving File", f"Failed to save the file.\nError: {e}")
            return False

    def save_as_file(self):
        """Saves the current settings to a new file."""
        filepath = filedialog.asksaveasfilename(
            title="Save OmniPOP File As",
            defaultextension=".omnipop",
            filetypes=[("OmniPOP Files", "*.omnipop"), ("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="New Design.omnipop"
        )
        if not filepath:
            return False # User cancelled

        settings = self._get_current_settings()
        try:
            with open(filepath, 'w') as f:
                json.dump(settings, f, indent=4)
            # Update current file and add to recent files
            self.current_file = filepath
            self.file_label_var.set(os.path.basename(filepath))
            self.add_to_recent_files(filepath)
            messagebox.showinfo("File Saved", f"Design saved successfully to:\n{filepath}")
            return True # Success
        except IOError as e:
            messagebox.showerror("Error Saving File", f"Failed to save the file.\nError: {e}")
            return False

    def export_autolisp(self):
        """Exports the current design as an AutoLISP file."""
        # Prompt for the 5-digit order number
        order_number = simpledialog.askstring(
            "Order Number",
            "Please enter the 5-digit order number for this unit:",
            parent=self.master
        )
        if not order_number:
            return # User cancelled or entered nothing

        # Get unit type and dimensions for filename
        unit_type = self.unitTypeVar.get()
        width = self.width_var.get() if self.width_var.get() else 48.0
        depth = self.depth_var.get() if self.depth_var.get() else 48.0
        height = self.height_var.get() if self.height_var.get() else 96.0
        
        # Create default filename using the order number, with dimensions first
        default_filename = f"{order_number} - {width}x{depth}x{height} {unit_type}.lsp"
        
        filepath = filedialog.asksaveasfilename(
            title="Export as AutoLISP",
            defaultextension=".lsp",
            filetypes=[("AutoLISP Files", "*.lsp"), ("All Files", "*.*")],
            initialfile=default_filename
        )
        if not filepath:
            return

        # Auto-save current file before export
        if hasattr(self, 'current_file') and self.current_file:
            self.save_file()

        try:
            lisp_code = self._generate_autolisp_code()
            with open(filepath, 'w') as f:
                f.write(lisp_code)
            messagebox.showinfo("Export Successful", f"AutoLISP file saved to:\n{filepath}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Failed to save AutoLISP file.\nError: {e}")

    def export_dxf(self):
        """Exports the current design as a DXF file."""
        # Prompt for the 5-digit order number
        order_number = simpledialog.askstring(
            "Order Number",
            "Please enter the 5-digit order number for this unit:",
            parent=self.master
        )
        if not order_number:
            return # User cancelled or entered nothing

        # Get unit type and dimensions for filename
        unit_type = self.unitTypeVar.get()
        width = self.width_var.get() if self.width_var.get() else 48.0
        depth = self.depth_var.get() if self.depth_var.get() else 48.0
        height = self.height_var.get() if self.height_var.get() else 96.0
        
        # Create default filename using the order number, with dimensions first
        default_filename = f"{order_number} - {width}x{depth}x{height} {unit_type}.dxf"
        
        filepath = filedialog.asksaveasfilename(
            title="Export as DXF",
            defaultextension=".dxf",
            filetypes=[("DXF Files", "*.dxf"), ("All Files", "*.*")],
            initialfile=default_filename
        )
        
        if not filepath:
            return

        # Auto-save current file before export
        if hasattr(self, 'current_file') and self.current_file:
            self.save_file()

        try:
            self._generate_dxf_file(filepath)
            messagebox.showinfo("Export DXF", f"DXF file exported successfully to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export DXF file.\nError: {e}")

    def _generate_dxf_file(self, filepath):
        """Generates a complete DXF file based on current design parameters."""
        unit_type = self.unitTypeVar.get()
        width = float(self.width_var.get()) if self.width_var.get() else 48.0
        depth = float(self.depth_var.get()) if self.depth_var.get() else 48.0
        height = float(self.height_var.get()) if self.height_var.get() else 90.0
        sw_length = float(self.sideWallLengthVar.get()) if self.sideWallToggleVar.get() else 25.0
        
        # Convert to mm for DXF (standard CAD units)
        width_mm = width * 25.4
        depth_mm = depth * 25.4
        height_mm = height * 25.4
        sw_length_mm = sw_length * 25.4
        
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            
            # Entities Section
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Generate entities based on unit type
            if unit_type == "Endcap":
                self._generate_endcap_dxf_entities(f, width_mm, depth_mm, height_mm)
            elif unit_type == "Bookcase":
                self._generate_bookcase_dxf_entities(f, width_mm, depth_mm, height_mm, sw_length_mm)
            elif unit_type == "Slice Rack":
                self._generate_slice_rack_dxf_entities(f, width_mm, depth_mm, height_mm, sw_length_mm)
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _write_dxf_header(self, f):
        """Writes the DXF header section."""
        f.write("  0\n")
        f.write("SECTION\n")
        f.write("  2\n")
        f.write("HEADER\n")
        f.write("  9\n")
        f.write("$ACADVER\n")
        f.write("  1\n")
        f.write("AC1015\n")
        f.write("  9\n")
        f.write("$DWGCODEPAGE\n")
        f.write("  3\n")
        f.write("ANSI_1252\n")
        f.write("  9\n")
        f.write("$INSBASE\n")
        f.write(" 10\n")
        f.write("0.0\n")
        f.write(" 20\n")
        f.write("0.0\n")
        f.write(" 30\n")
        f.write("0.0\n")
        f.write("  0\n")
        f.write("ENDSEC\n")

    def _write_dxf_layers(self, f):
        """Writes the DXF layers section."""
        f.write("  0\n")
        f.write("SECTION\n")
        f.write("  2\n")
        f.write("TABLES\n")
        
        # Layer Table
        f.write("  0\n")
        f.write("TABLE\n")
        f.write("  2\n")
        f.write("LAYER\n")
        f.write(" 70\n")
        f.write("     4\n")
        
        # Define layers
        layers = ["0", "Dimensions", "Hardware", "Defpoints", "Construction"]
        for layer in layers:
            f.write("  0\n")
            f.write("LAYER\n")
            f.write("  2\n")
            f.write(f"{layer}\n")
            f.write(" 70\n")
            f.write("     0\n")
            f.write(" 62\n")
            f.write("     7\n")
            f.write("  6\n")
            f.write("CONTINUOUS\n")
        
        f.write("  0\n")
        f.write("ENDTAB\n")
        f.write("  0\n")
        f.write("ENDSEC\n")

    def _generate_endcap_dxf_entities(self, f, width_mm, depth_mm, height_mm):
        """Generates DXF entities for Endcap unit type."""
        # Calculate dimensions
        base_thickness_mm = 5.25 * 25.4  # 5.25" to mm
        deck_thickness_mm = 0.75 * 25.4  # 0.75" to mm
        top_thickness_mm = 8 * 25.4      # 8" canopy
        
        # Column dimensions
        col_width = 8 + (2 * int((width_mm/25.4 - 48) / 12)) if width_mm/25.4 > 48 else 8
        col_width_mm = col_width * 25.4
        col_depth = 10 + (2 * int((depth_mm/25.4 - 48) / 6)) if depth_mm/25.4 > 48 else 10
        col_depth_mm = col_depth * 25.4
        
        # Pole positions
        x_positions = self.compute_pole_positions_width(width_mm/25.4)
        x_positions_mm = [x * 25.4 for x in x_positions]
        front_dist_mm = self.pole_front_distance(depth_mm/25.4) * 25.4
        
        # Front View - Main outline
        self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
        self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
        self._add_dxf_line(f, width_mm, 0, width_mm, height_mm, "0")  # Right
        self._add_dxf_line(f, 0, height_mm, width_mm, height_mm, "0")  # Top
        
        # Canopy (top section)
        self._add_dxf_line(f, 0, height_mm - top_thickness_mm, width_mm, height_mm - top_thickness_mm, "0")
        
        # Base
        self._add_dxf_line(f, 0, base_thickness_mm, width_mm, base_thickness_mm, "0")
        
        # Column outline (interior structure)
        col_x_start = (width_mm - col_width_mm) / 2
        self._add_dxf_line(f, col_x_start, base_thickness_mm, col_x_start, height_mm - top_thickness_mm, "0")
        self._add_dxf_line(f, col_x_start + col_width_mm, base_thickness_mm, col_x_start + col_width_mm, height_mm - top_thickness_mm, "0")
        
        # Column front and back
        self._add_dxf_line(f, col_x_start, base_thickness_mm, col_x_start + col_width_mm, base_thickness_mm, "0")
        self._add_dxf_line(f, col_x_start, height_mm - top_thickness_mm, col_x_start + col_width_mm, height_mm - top_thickness_mm, "0")
        
        # Poles (hardware)
        pole_radius_mm = 0.75 * 25.4  # 1.5" diameter
        for x_pos in x_positions_mm:
            self._add_dxf_circle(f, x_pos, front_dist_mm, pole_radius_mm, "Hardware")
        
        # Dimension lines and text
        self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
        
        # Column dimensions
        self._add_dimension_line(f, col_x_start, -60, col_x_start + col_width_mm, -60, f"{col_width:.1f}\"", "Dimensions")
        
        # Top View
        top_y_offset = height_mm + 150
        self._add_dxf_line(f, 0, top_y_offset, width_mm, top_y_offset, "0")  # Front
        self._add_dxf_line(f, 0, top_y_offset, 0, top_y_offset + depth_mm, "0")  # Left
        self._add_dxf_line(f, width_mm, top_y_offset, width_mm, top_y_offset + depth_mm, "0")  # Right
        self._add_dxf_line(f, 0, top_y_offset + depth_mm, width_mm, top_y_offset + depth_mm, "0")  # Back
        
        # Back panel
        back_thickness_mm = 0.75 * 25.4
        self._add_dxf_line(f, 0, top_y_offset, width_mm, top_y_offset + back_thickness_mm, "0")
        
        # Column in top view
        col_y_start = top_y_offset + depth_mm - col_depth_mm
        self._add_dxf_line(f, col_x_start, col_y_start, col_x_start + col_width_mm, col_y_start, "0")
        self._add_dxf_line(f, col_x_start, col_y_start + col_depth_mm, col_x_start + col_width_mm, col_y_start + col_depth_mm, "0")
        self._add_dxf_line(f, col_x_start, col_y_start, col_x_start, col_y_start + col_depth_mm, "0")
        self._add_dxf_line(f, col_x_start + col_width_mm, col_y_start, col_x_start + col_width_mm, col_y_start + col_depth_mm, "0")
        
        # Poles in top view
        for x_pos in x_positions_mm:
            self._add_dxf_circle(f, x_pos, top_y_offset + depth_mm - front_dist_mm, pole_radius_mm, "Hardware")
        
        # Top view dimensions
        self._add_dimension_line(f, 0, top_y_offset - 30, width_mm, top_y_offset - 30, f"{width_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, -30, top_y_offset, -30, top_y_offset + depth_mm, f"{depth_mm/25.4:.1f}\"", "Dimensions")

    def _generate_bookcase_dxf_entities(self, f, width_mm, depth_mm, height_mm, sw_length_mm):
        """Generates DXF entities for Bookcase unit type."""
        # Similar structure but with side walls
        base_thickness_mm = 5.25 * 25.4
        deck_thickness_mm = 0.75 * 25.4
        wall_thickness_mm = 0.75 * 25.4
        
        # Front View
        self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
        self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
        self._add_dxf_line(f, width_mm, 0, width_mm, height_mm, "0")  # Right
        self._add_dxf_line(f, 0, height_mm, width_mm, height_mm, "0")  # Top
        
        # Base
        self._add_dxf_line(f, 0, base_thickness_mm, width_mm, base_thickness_mm, "0")
        
        # Side walls
        self._add_dxf_line(f, 0, 0, wall_thickness_mm, height_mm, "0")  # Left wall
        self._add_dxf_line(f, width_mm - wall_thickness_mm, 0, width_mm, height_mm, "0")  # Right wall
        
        # Standards (vertical supports)
        std1_x = wall_thickness_mm + (width_mm - 2 * wall_thickness_mm) * 0.25
        std2_x = wall_thickness_mm + (width_mm - 2 * wall_thickness_mm) * 0.75
        self._add_dxf_line(f, std1_x, base_thickness_mm, std1_x, height_mm, "Hardware")
        self._add_dxf_line(f, std2_x, base_thickness_mm, std2_x, height_mm, "Hardware")
        
        # Dimension lines
        self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
        
        # Top View
        top_y_offset = height_mm + 150
        self._add_dxf_line(f, 0, top_y_offset, width_mm, top_y_offset, "0")  # Front
        self._add_dxf_line(f, 0, top_y_offset, 0, top_y_offset + depth_mm, "0")  # Left
        self._add_dxf_line(f, width_mm, top_y_offset, width_mm, top_y_offset + depth_mm, "0")  # Right
        self._add_dxf_line(f, 0, top_y_offset + depth_mm, width_mm, top_y_offset + depth_mm, "0")  # Back
        
        # Back panel
        back_thickness_mm = 0.75 * 25.4
        self._add_dxf_line(f, 0, top_y_offset, width_mm, top_y_offset + back_thickness_mm, "0")
        
        # Side walls in top view
        self._add_dxf_line(f, 0, top_y_offset + back_thickness_mm, 0, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        self._add_dxf_line(f, wall_thickness_mm, top_y_offset + back_thickness_mm, wall_thickness_mm, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        self._add_dxf_line(f, width_mm - wall_thickness_mm, top_y_offset + back_thickness_mm, width_mm - wall_thickness_mm, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        self._add_dxf_line(f, width_mm, top_y_offset + back_thickness_mm, width_mm, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        
        # Standards in top view
        std_size = 1 * 25.4
        self._add_dxf_line(f, std1_x, top_y_offset + back_thickness_mm, std1_x + std_size, top_y_offset + back_thickness_mm, "Hardware")
        self._add_dxf_line(f, std1_x, top_y_offset + back_thickness_mm, std1_x, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std1_x + std_size, top_y_offset + back_thickness_mm, std1_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std1_x, top_y_offset + back_thickness_mm + std_size, std1_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        
        self._add_dxf_line(f, std2_x, top_y_offset + back_thickness_mm, std2_x + std_size, top_y_offset + back_thickness_mm, "Hardware")
        self._add_dxf_line(f, std2_x, top_y_offset + back_thickness_mm, std2_x, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std2_x + std_size, top_y_offset + back_thickness_mm, std2_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std2_x, top_y_offset + back_thickness_mm + std_size, std2_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        
        # Top view dimensions
        self._add_dimension_line(f, 0, top_y_offset - 30, width_mm, top_y_offset - 30, f"{width_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, -30, top_y_offset, -30, top_y_offset + depth_mm, f"{depth_mm/25.4:.1f}\"", "Dimensions")

    def _generate_slice_rack_dxf_entities(self, f, width_mm, depth_mm, height_mm, sw_length_mm):
        """Generates DXF entities for Slice Rack unit type."""
        # Similar to bookcase but with specific slice rack features
        base_thickness_mm = 5.25 * 25.4
        wall_thickness_mm = 0.75 * 25.4
        
        # Front View
        self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
        self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
        self._add_dxf_line(f, width_mm, 0, width_mm, height_mm, "0")  # Right
        self._add_dxf_line(f, 0, height_mm, width_mm, height_mm, "0")  # Top
        
        # Base
        self._add_dxf_line(f, 0, base_thickness_mm, width_mm, base_thickness_mm, "0")
        
        # Side walls
        self._add_dxf_line(f, 0, 0, wall_thickness_mm, height_mm, "0")  # Left wall
        self._add_dxf_line(f, width_mm - wall_thickness_mm, 0, width_mm, height_mm, "0")  # Right wall
        
        # 6" panel
        panel_height_mm = 6 * 25.4
        panel_y = base_thickness_mm
        self._add_dxf_line(f, wall_thickness_mm, panel_y, width_mm - wall_thickness_mm, panel_y, "0")
        self._add_dxf_line(f, wall_thickness_mm, panel_y + panel_height_mm, width_mm - wall_thickness_mm, panel_y + panel_height_mm, "0")
        self._add_dxf_line(f, wall_thickness_mm, panel_y, wall_thickness_mm, panel_y + panel_height_mm, "0")
        self._add_dxf_line(f, width_mm - wall_thickness_mm, panel_y, width_mm - wall_thickness_mm, panel_y + panel_height_mm, "0")
        
        # Standards (vertical supports)
        std1_x = wall_thickness_mm + (width_mm - 2 * wall_thickness_mm) * 0.25
        std2_x = wall_thickness_mm + (width_mm - 2 * wall_thickness_mm) * 0.75
        std_height_mm = 68.125 * 25.4  # 68 1/8" standards
        self._add_dxf_line(f, std1_x, panel_y, std1_x, panel_y + std_height_mm, "Hardware")
        self._add_dxf_line(f, std2_x, panel_y, std2_x, panel_y + std_height_mm, "Hardware")
        
        # Dimension lines
        self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, wall_thickness_mm, -60, width_mm - wall_thickness_mm, -60, f"{panel_height_mm/25.4:.1f}\"", "Dimensions")
        
        # Top View
        top_y_offset = height_mm + 150
        self._add_dxf_line(f, 0, top_y_offset, width_mm, top_y_offset, "0")  # Front
        self._add_dxf_line(f, 0, top_y_offset, 0, top_y_offset + depth_mm, "0")  # Left
        self._add_dxf_line(f, width_mm, top_y_offset, width_mm, top_y_offset + depth_mm, "0")  # Right
        self._add_dxf_line(f, 0, top_y_offset + depth_mm, width_mm, top_y_offset + depth_mm, "0")  # Back
        
        # Back panel
        back_thickness_mm = 0.75 * 25.4
        self._add_dxf_line(f, 0, top_y_offset, width_mm, top_y_offset + back_thickness_mm, "0")
        
        # Side walls in top view
        self._add_dxf_line(f, 0, top_y_offset + back_thickness_mm, 0, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        self._add_dxf_line(f, wall_thickness_mm, top_y_offset + back_thickness_mm, wall_thickness_mm, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        self._add_dxf_line(f, width_mm - wall_thickness_mm, top_y_offset + back_thickness_mm, width_mm - wall_thickness_mm, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        self._add_dxf_line(f, width_mm, top_y_offset + back_thickness_mm, width_mm, top_y_offset + back_thickness_mm + sw_length_mm, "0")
        
        # Standards in top view
        std_size = 1 * 25.4
        self._add_dxf_line(f, std1_x, top_y_offset + back_thickness_mm, std1_x + std_size, top_y_offset + back_thickness_mm, "Hardware")
        self._add_dxf_line(f, std1_x, top_y_offset + back_thickness_mm, std1_x, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std1_x + std_size, top_y_offset + back_thickness_mm, std1_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std1_x, top_y_offset + back_thickness_mm + std_size, std1_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        
        self._add_dxf_line(f, std2_x, top_y_offset + back_thickness_mm, std2_x + std_size, top_y_offset + back_thickness_mm, "Hardware")
        self._add_dxf_line(f, std2_x, top_y_offset + back_thickness_mm, std2_x, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std2_x + std_size, top_y_offset + back_thickness_mm, std2_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        self._add_dxf_line(f, std2_x, top_y_offset + back_thickness_mm + std_size, std2_x + std_size, top_y_offset + back_thickness_mm + std_size, "Hardware")
        
        # Top view dimensions
        self._add_dimension_line(f, 0, top_y_offset - 30, width_mm, top_y_offset - 30, f"{width_mm/25.4:.1f}\"", "Dimensions")
        self._add_dimension_line(f, -30, top_y_offset, -30, top_y_offset + depth_mm, f"{depth_mm/25.4:.1f}\"", "Dimensions")

    def _generate_autolisp_code(self):
        """Generates AutoLISP code based on current design parameters."""
        unit_type = self.unitTypeVar.get()
        width = self.width_var.get()
        depth = self.depth_var.get()
        height = self.height_var.get()
        sw_length = self.sideWallLengthVar.get() if self.sideWallToggleVar.get() else 0
        shelf_type = self.shelfTypeVar.get()
        shelf_material = self.shelfMaterialVar.get()
        shelf_spacings = [entry['var'].get() for entry in self.manualShelfEntries]
        
        # Convert inches to mm for CAD
        width_mm = width * 25.4
        depth_mm = depth * 25.4
        height_mm = height * 25.4
        sw_length_mm = sw_length * 25.4
        
        # Material thickness in mm
        material_thickness = 20  # 20mm = ~0.75"
        
        lisp_code = f""";;{unit_type}AutoLISP.lsp
;;Generated by OmniPOP Design Portal
(defun c:{unit_type}AutoLISP (/ savedOSMODE *error* materialThickness baseHeight canopyHeight sleeperHeight midHeight totalDepth totalHeight totalWidth sideDepth)

\t;;Prompt User for Insertion Point
\t(setq insertionPoint (getpoint "\\nSpecify the Insertion Point : "))

\t;;Will run if there is an error
\t(defun *error* (errorMessage)
\t\t(if savedOSMODE (setvar "OSMODE" savedOSMODE))
\t\t(if (and errorMessage (not (wcmatch (strcase errorMessage) "*QUIT*,*CANCEL*")))
\t\t\t(princ (strcat "\\nError: " errorMessage))
\t\t)
\t\t(setq *error* nil)
\t\t(princ)
\t)

\t;;Save settings
\t(setq savedOSMODE (getvar "OSMODE"))
\t(setvar "OSMODE" 0)

\t;;Dimensions from OmniPOP
\t(setq totalWidth {width_mm:.1f})
\t(setq totalDepth {depth_mm:.1f})
\t(setq totalHeight {height_mm:.1f})
\t(setq sideDepth {sw_length_mm:.1f})
\t
\t;;Constant Dimensions
\t(setq materialThickness {material_thickness})
\t(setq baseHeight 153)
\t(setq canopyHeight 203)
\t(setq sleeperHeight 133)
\t(setq midHeight (- (/ totalHeight 2) 10))
\t(setq eightRadius 4)
\t(setq fiveRadius 2.5)
\t
\t;;Layer Creation
\t(command "-LAYER" "N" "Back" "C" "150" "Back" "")
\t(command "-LAYER" "N" "Base" "C" "140" "Base" "")
\t(command "-LAYER" "N" "Deck" "C" "60" "Deck" "")
\t(command "-LAYER" "N" "Support" "C" "122" "Support" "")
\t(command "-LAYER" "N" "Shelf" "C" "100" "Shelf" "")
\t(command "-LAYER" "N" "Canopy" "C" "200" "Canopy" "")
\t(command "-LAYER" "N" "VBORED19P5" "C" "52" "VBORED19P5" "")
\t(command "-LAYER" "N" "VBORED15" "C" "40" "VBORED15" "")
\t(command "-LAYER" "N" "PARTD19P5" "C" "1" "PARTD19P5" "")
\t
\t;;Unit Type: {unit_type}
\t;;Shelf Type: {shelf_type}
\t;;Shelf Material: {shelf_material}
\t;;Number of Shelves: {len(shelf_spacings)}
\t
\t;;TODO: Add specific drawing commands for {unit_type}
\t;;This is a template - specific geometry needs to be implemented
\t
\t;;Restore settings
\t(if savedOSMODE (setvar "OSMODE" savedOSMODE))
\t(setq *error* nil)
\t(princ "\\nOriginal settings restored.")
\t(princ)
)
(princ)
"""
        return lisp_code

    def export_to_cad(self):
        """Exports the current design to multiple CAD files (overall + individual parts)."""
        # Prompt for the 5-digit order number
        order_number = simpledialog.askstring(
            "Order Number",
            "Please enter the 5-digit order number for this project:",
            parent=self.master
        )
        if not order_number:
            return # User cancelled or entered nothing

        # Get unit type and dimensions for folder name
        unit_type = self.unitTypeVar.get()
        width = self.width_var.get() if self.width_var.get() else 48.0
        depth = self.depth_var.get() if self.depth_var.get() else 48.0
        height = self.height_var.get() if self.height_var.get() else 96.0
        
        # Create default folder name and part number using the order number, with dimensions first
        default_folder_name = f"{order_number} - {width}x{depth}x{height}_{unit_type}"
        
        # Get the export directory
        export_dir = filedialog.askdirectory(
            title="Select Export Directory for CAD Files"
        )
        if not export_dir:
            return

        # Use the folder name as the part number base
        part_number = default_folder_name

        # Auto-save current file before export
        if hasattr(self, 'current_file') and self.current_file:
            self.save_file()

        try:
            # Create the main folder
            full_export_path = os.path.join(export_dir, default_folder_name)
            os.makedirs(full_export_path, exist_ok=True)
            
            # Calculate total parts count
            total_parts = sum(part.get('qty', 1) for part in self.part_list)
            
            # Export overall DXF with parts count in filename
            overall_dxf_path = os.path.join(full_export_path, f"{part_number} - Overall ({total_parts} parts).dxf")
            self._export_overall_dxf(overall_dxf_path)
            
            # Export individual part DXF files
            self._export_part_dxfs(full_export_path, part_number)
            
            # Open the exported folder in Windows File Explorer
            try:
                os.startfile(full_export_path)
            except Exception as e:
                print(f"Could not open folder in File Explorer: {e}")
            
            messagebox.showinfo("Export Successful", 
                f"CAD files exported successfully to:\n{full_export_path}\n\n"
                f"Generated files:\n"
                f"• {part_number} - Overall ({total_parts} parts).dxf\n"
                f"• Individual part DXF files\n\n"
                f"Folder opened in File Explorer.")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CAD files.\nError: {e}")

    def _export_overall_dxf(self, filepath):
        """Exports an overall DXF of the assembled unit."""
        # This can be expanded to draw the full assembly
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\nSECTION\n2\nENTITIES\n")
            # Placeholder text
            self._add_dxf_text(f, 10, 10, "Overall Assembly View - Not Yet Implemented", "0")
            f.write("  0\nENDSEC\n0\nEOF\n")

    def _export_part_dxfs(self, export_dir, part_number):
        """Exports individual DXF files for each part in the part_list."""
        # Group parts by name and dimensions to combine identical parts
        part_groups = {}
        for part in self.part_list:
            # Create a key based on name and dimensions
            key = f"{part['name']}_{part.get('w', 0)}_{part.get('h', 0)}_{part.get('th', 0)}"
            
            if key not in part_groups:
                part_groups[key] = {
                    'name': part['name'],
                    'w': part.get('w', 0),
                    'h': part.get('h', 0),
                    'th': part.get('th', 0),
                    'qty': 0
                }
            
            part_groups[key]['qty'] += part.get('qty', 1)
        
        for part_key, part_data in part_groups.items():
            part_name = part_data['name']
            qty = part_data['qty']
            
            # Create filename
            filename = f"{part_number} - {qty} {part_name}.dxf"
            filepath = os.path.join(export_dir, filename)
            
            # Generate the DXF file for this part
            self._generate_part_dxf(filepath, part_name, part_data, qty)

    def _generate_part_dxf(self, filepath, part_name, part_data, qty):
        """Generates a DXF file for a single part type with accurate dimensions and geometry."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            
            # Entities Section
            f.write("0\nSECTION\n")
            f.write("2\nENTITIES\n")
            
            # Get current unit configuration for context
        unit_type = self.unitTypeVar.get()
        top_option = self.top_var.get()
        shelf_type = self.shelfTypeVar.get()
        shelf_material = self.shelfMaterialVar.get()
        sw_length = float(self.sideWallLengthVar.get()) if self.sideWallToggleVar.get() else 0
        unit_depth = float(self.depth_var.get()) if self.depth_var.get() else 48.0
        
        # Convert part dimensions to mm
        w_mm = part_data.get('w', 0) * 25.4
        h_mm = part_data.get('h', 0) * 25.4
        th_mm = part_data.get('th', 0) * 25.4
        
        # Generate accurate part geometry based on part type
        if part_name == 'Back Panel':
            self._draw_back_panel_dxf(f, w_mm, h_mm, th_mm)
        elif 'Base' in part_name: # Covers "Base Front" and "Base Side"
            self._draw_base_dxf(f, w_mm, h_mm, th_mm, unit_type)
        elif part_name == 'Deck':
            self._draw_deck_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Shelf':
            self._draw_shelf_dxf(f, w_mm, h_mm, th_mm, unit_type, shelf_type, shelf_material, sw_length * 25.4)
        elif part_name == 'Side Wall':
            self._draw_side_wall_dxf(f, w_mm, h_mm, th_mm, top_option, unit_depth * 25.4)
        elif part_name == 'Canopy Front':
            self._draw_canopy_front_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Canopy Back':
            self._draw_canopy_back_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Canopy Side':
            self._draw_canopy_side_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Canopy Support':
            self._draw_canopy_support_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Fascia Front':
            self._draw_fascia_front_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Fascia Side':
            self._draw_fascia_side_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Fascia Support':
            self._draw_fascia_support_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Column Front':
            self._draw_column_front_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Column Side':
            self._draw_column_side_dxf(f, w_mm, h_mm, th_mm)
        elif part_name == 'Base Panel':
            self._draw_base_panel_dxf(f, w_mm, h_mm, th_mm)
        else:
            self._draw_simple_rectangle_dxf(f, w_mm, h_mm, th_mm)
        
        # Add dimensions and labels
        self._add_part_dimensions(f, part_name, w_mm, h_mm, th_mm, qty)
        
        f.write("0\nENDSEC\n")
        f.write("0\nEOF\n")

    def _draw_back_panel_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a back panel with accurate dimensions."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_base_dxf(self, f, width_mm, height_mm, thickness_mm, unit_type):
        """Draws a base with accurate dimensions and any required cutouts."""
        # Base outline
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)
        
        # Add column cutout for Endcap units
        if unit_type == "Endcap":
            # Calculate column dimensions
            col_width = 8 + (2 * int((width_mm/25.4 - 48) / 12)) if width_mm/25.4 > 48 else 8
            col_width_mm = col_width * 25.4
            col_depth = 10 + (2 * int((height_mm/25.4 - 48) / 6)) if height_mm/25.4 > 48 else 10
            col_depth_mm = col_depth * 25.4
            
            # Column cutout
            col_x_start = (width_mm - col_width_mm) / 2
            col_y_start = height_mm - col_depth_mm
            self._add_dxf_line(f, col_x_start, col_y_start, col_x_start + col_width_mm, col_y_start, "0")
            self._add_dxf_line(f, col_x_start, col_y_start, col_x_start, height_mm, "0")
            self._add_dxf_line(f, col_x_start + col_width_mm, col_y_start, col_x_start + col_width_mm, height_mm, "0")

    def _draw_deck_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a deck panel with accurate dimensions."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_shelf_dxf(self, f, width_mm, height_mm, thickness_mm, unit_type, shelf_type, shelf_material, sw_length_mm):
        """Draws a shelf with accurate dimensions and radiused corners if needed."""
        actual_depth_mm = height_mm # Renaming for clarity in this function
        
        # Check if shelf should have radiused corners
        should_be_rounded = False
        if shelf_material == "Melamine":
            effective_shelf_depth = actual_depth_mm + self.parts['standards']['thickness'] * 25.4 if shelf_type == "Standard & Brackets" else 0
            if sw_length_mm < effective_shelf_depth:
                should_be_rounded = True
        
        if should_be_rounded:
            # Draw shelf with radiused front corners
            radius_mm = 25.4  # 1" radius
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Back edge
            self._add_dxf_line(f, width_mm, 0, width_mm, actual_depth_mm - radius_mm, "0")  # Right edge
            self._add_dxf_line(f, 0, 0, 0, actual_depth_mm - radius_mm, "0")  # Left edge
            
            # Front-right corner arc
            cx1, cy1 = width_mm - radius_mm, actual_depth_mm - radius_mm
            self._add_dxf_arc(f, cx1, cy1, radius_mm, 0, 90, "0")
            
            # Front-left corner arc
            cx2, cy2 = radius_mm, actual_depth_mm - radius_mm
            self._add_dxf_arc(f, cx2, cy2, radius_mm, 90, 180, "0")
        else:
            # Draw simple rectangular shelf
            self._draw_simple_rectangle_dxf(f, width_mm, actual_depth_mm, thickness_mm)

    def _draw_side_wall_dxf(self, f, width_mm, height_mm, thickness_mm, top_option, unit_depth_mm):
        """Draws a side wall with accurate dimensions and radiused corners if needed."""
        # width_mm here is the length of the wall
        length_mm = width_mm
        
        # Check if side wall should have radiused corners
        should_be_rounded = False
        if top_option == "No Top":
            should_be_rounded = True
        elif top_option == "Fascia" and length_mm < unit_depth_mm - (self.parts['back_panel']['thickness'] * 25.4):
            should_be_rounded = True
        
        if should_be_rounded:
            # Draw side wall with radiused top-front corner
            radius_mm = 50.8  # 2" radius
            self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Back edge
            self._add_dxf_line(f, 0, height_mm, length_mm - radius_mm, height_mm, "0")  # Top edge
            self._add_dxf_line(f, length_mm, 0, length_mm, height_mm - radius_mm, "0")  # Front edge
            
            # Top-front corner arc
            cx, cy = length_mm - radius_mm, height_mm - radius_mm
            self._add_dxf_arc(f, cx, cy, radius_mm, 0, 90, "0")
            
            # Bottom edge
            self._add_dxf_line(f, 0, 0, length_mm, 0, "0")
        else:
            # Draw simple rectangular side wall
            self._draw_simple_rectangle_dxf(f, length_mm, height_mm, thickness_mm)

    def _draw_canopy_front_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a canopy front panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_canopy_back_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a canopy back panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_canopy_side_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a canopy side panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_canopy_support_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a canopy support panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_fascia_front_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a fascia front panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_fascia_side_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a fascia side panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_fascia_support_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a fascia support panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_column_front_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a column front panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_column_side_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a column side panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_base_panel_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a base panel."""
        self._draw_simple_rectangle_dxf(f, width_mm, height_mm, thickness_mm)

    def _draw_simple_rectangle_dxf(self, f, width_mm, height_mm, thickness_mm):
        """Draws a simple rectangle for any part. height_mm is used as the second dimension on a 2D plane."""
        self._add_dxf_line(f, 0, 0, width_mm, 0, "0")
        self._add_dxf_line(f, width_mm, 0, width_mm, height_mm, "0")
        self._add_dxf_line(f, width_mm, height_mm, 0, height_mm, "0")
        self._add_dxf_line(f, 0, height_mm, 0, 0, "0")

    def _add_dxf_line(self, f, x1, y1, x2, y2, layer):
        """Adds a line entity to the DXF file."""
        f.write("  0\n")
        f.write("LINE\n")
        f.write("  8\n")
        f.write(f"{layer}\n")
        f.write(" 10\n")
        f.write(f"{x1:.6f}\n")
        f.write(" 20\n")
        f.write(f"{y1:.6f}\n")
        f.write(" 30\n")
        f.write("0.0\n")
        f.write(" 11\n")
        f.write(f"{x2:.6f}\n")
        f.write(" 21\n")
        f.write(f"{y2:.6f}\n")
        f.write(" 31\n")
        f.write("0.0\n")

    def _add_dxf_circle(self, f, x, y, radius, layer):
        """Adds a circle entity to the DXF file."""
        f.write("  0\n")
        f.write("CIRCLE\n")
        f.write("  8\n")
        f.write(f"{layer}\n")
        f.write(" 10\n")
        f.write(f"{x:.6f}\n")
        f.write(" 20\n")
        f.write(f"{y:.6f}\n")
        f.write(" 30\n")
        f.write("0.0\n")
        f.write(" 40\n")
        f.write(f"{radius:.6f}\n")

    def _add_dxf_text(self, f, x, y, text, layer):
        """Adds a text entity to the DXF file."""
        f.write("  0\n")
        f.write("TEXT\n")
        f.write("  8\n")
        f.write(f"{layer}\n")
        f.write(" 10\n")
        f.write(f"{x:.6f}\n")
        f.write(" 20\n")
        f.write(f"{y:.6f}\n")
        f.write(" 30\n")
        f.write("0.0\n")
        f.write(" 40\n")
        f.write("30.0\n")
        f.write("  1\n")
        f.write(f"{text}\n")

    def _add_dimension_line(self, f, x1, y1, x2, y2, text, layer):
        """Adds a dimension line with arrows and text to the DXF file."""
        # Dimension line
        self._add_dxf_line(f, x1, y1, x2, y2, layer)
        
        # Extension lines
        ext_length = 20
        if x1 == x2:  # Vertical dimension
            self._add_dxf_line(f, x1 - ext_length, y1, x1 + ext_length, y1, layer)
            self._add_dxf_line(f, x2 - ext_length, y2, x2 + ext_length, y2, layer)
            # Text position
            text_x = x1 - 50
            text_y = (y1 + y2) / 2
        else:  # Horizontal dimension
            self._add_dxf_line(f, x1, y1 - ext_length, x1, y1 + ext_length, layer)
            self._add_dxf_line(f, x2, y2 - ext_length, x2, y2 + ext_length, layer)
            # Text position
            text_x = (x1 + x2) / 2
            text_y = y1 - 50
        
        # Dimension text
        self._add_dxf_text(f, text_x, text_y, text, layer)

    def _add_dxf_arc(self, f, cx, cy, radius, start_angle, end_angle, layer):
        """Adds an arc entity to the DXF file."""
        f.write("  0\n")
        f.write("ARC\n")
        f.write("  8\n")
        f.write(f"{layer}\n")
        f.write(" 10\n")
        f.write(f"{cx:.6f}\n")
        f.write(" 20\n")
        f.write(f"{cy:.6f}\n")
        f.write(" 30\n")
        f.write("0.0\n")
        f.write(" 40\n")
        f.write(f"{radius:.6f}\n")
        f.write(" 50\n")
        f.write(f"{start_angle:.6f}\n")
        f.write(" 51\n")
        f.write(f"{end_angle:.6f}\n")

    def _add_part_dimensions(self, f, part_name, w_mm, h_mm, th_mm, qty):
        """Adds dimensions and labels to the part drawing."""
        # Add dimensions
        if w_mm > 0:
            self._add_dxf_text(f, w_mm/2, -20, f"Width: {w_mm:.1f}mm", "Dimensions")
        if h_mm > 0:
            self._add_dxf_text(f, w_mm + 20, h_mm/2, f"Height: {h_mm:.1f}mm", "Dimensions")
        if th_mm > 0:
            self._add_dxf_text(f, w_mm/2, h_mm + 20, f"Thickness: {th_mm:.1f}mm", "Dimensions")
        
        # Add quantity if > 1
        if qty > 1:
            self._add_dxf_text(f, w_mm/2, -40, f"Quantity: {qty}", "Dimensions")
        
        # Add part name
        self._add_dxf_text(f, w_mm/2, -60, f"Part: {part_name}", "Dimensions")

    def _generate_base_front_part(self, filepath, width_mm, thickness_mm, col_width_mm, col_depth_mm):
        """Generates the base front panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Base front outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, thickness_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, thickness_mm, "0")  # Right
            self._add_dxf_line(f, 0, thickness_mm, width_mm, thickness_mm, "0")  # Top
            
            # Column cutout
            col_x_start = (width_mm - col_width_mm) / 2
            col_y_start = thickness_mm - col_depth_mm
            self._add_dxf_line(f, col_x_start, col_y_start, col_x_start + col_width_mm, col_y_start, "0")
            self._add_dxf_line(f, col_x_start, col_y_start, col_x_start, thickness_mm, "0")
            self._add_dxf_line(f, col_x_start + col_width_mm, col_y_start, col_x_start + col_width_mm, thickness_mm, "0")
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, thickness_mm, f"{thickness_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_column_front_part(self, filepath, width_mm, height_mm, thickness_mm):
        """Generates the column front panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Column front outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, height_mm, "0")  # Right
            self._add_dxf_line(f, 0, height_mm, width_mm, height_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_deck_part(self, filepath, width_mm, depth_mm, thickness_mm):
        """Generates the deck panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Deck outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, depth_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, depth_mm, "0")  # Right
            self._add_dxf_line(f, 0, depth_mm, width_mm, depth_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, depth_mm, f"{depth_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_top_shelf_part(self, filepath, width_mm, depth_mm, thickness_mm):
        """Generates the top shelf panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Top shelf outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, depth_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, depth_mm, "0")  # Right
            self._add_dxf_line(f, 0, depth_mm, width_mm, depth_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, depth_mm, f"{depth_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_canopy_front_part(self, filepath, width_mm, thickness_mm, wall_thickness_mm):
        """Generates the canopy front panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Canopy front outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, thickness_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, thickness_mm, "0")  # Right
            self._add_dxf_line(f, 0, thickness_mm, width_mm, thickness_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, thickness_mm, f"{thickness_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_canopy_side_part(self, filepath, depth_mm, thickness_mm, wall_thickness_mm):
        """Generates the canopy side panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Canopy side outline
            self._add_dxf_line(f, 0, 0, depth_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, thickness_mm, "0")  # Left
            self._add_dxf_line(f, depth_mm, 0, depth_mm, thickness_mm, "0")  # Right
            self._add_dxf_line(f, 0, thickness_mm, depth_mm, thickness_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, depth_mm, -30, f"{depth_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, thickness_mm, f"{thickness_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_canopy_support_part(self, filepath, width_mm, depth_mm, thickness_mm):
        """Generates the canopy support DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Canopy support outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, depth_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, depth_mm, "0")  # Right
            self._add_dxf_line(f, 0, depth_mm, width_mm, depth_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, depth_mm, f"{depth_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_column_side_part(self, filepath, depth_mm, height_mm, thickness_mm):
        """Generates the column side panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Column side outline
            self._add_dxf_line(f, 0, 0, depth_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
            self._add_dxf_line(f, depth_mm, 0, depth_mm, height_mm, "0")  # Right
            self._add_dxf_line(f, 0, height_mm, depth_mm, height_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, depth_mm, -30, f"{depth_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_base_sleeper_part(self, filepath, width_mm, thickness_mm, wall_thickness_mm):
        """Generates the base sleeper DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Base sleeper outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, thickness_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, thickness_mm, "0")  # Right
            self._add_dxf_line(f, 0, thickness_mm, width_mm, thickness_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, thickness_mm, f"{thickness_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _write_dxf_header(self, f):
        """Writes the DXF header section."""
        f.write("  0\n")
        f.write("SECTION\n")
        f.write("  2\n")
        f.write("HEADER\n")
        f.write("  9\n")
        f.write("$ACADVER\n")
        f.write("  1\n")
        f.write("AC1015\n")
        f.write("  9\n")
        f.write("$DWGCODEPAGE\n")
        f.write("  3\n")
        f.write("ANSI_1252\n")
        f.write("  9\n")
        f.write("$INSBASE\n")
        f.write(" 10\n")
        f.write("0.0\n")
        f.write(" 20\n")
        f.write("0.0\n")
        f.write(" 30\n")
        f.write("0.0\n")
        f.write("  0\n")
        f.write("ENDSEC\n")

    def _write_dxf_layers(self, f):
        """Writes the DXF layers section."""
        f.write("  0\n")
        f.write("SECTION\n")
        f.write("  2\n")
        f.write("TABLES\n")
        f.write("  0\n")
        f.write("TABLE\n")
        f.write("  2\n")
        f.write("LAYER\n")
        f.write(" 70\n")
        f.write("     4\n")
        
        # Define layers
        layers = ["0", "Dimensions", "Hardware", "Defpoints", "Construction"]
        for layer in layers:
            f.write("  0\n")
            f.write("LAYER\n")
            f.write("  2\n")
            f.write(f"{layer}\n")
            f.write(" 70\n")
            f.write("     0\n")
            f.write(" 62\n")
            f.write("     7\n")
            f.write("  6\n")
            f.write("CONTINUOUS\n")
        
        f.write("  0\n")
        f.write("ENDTAB\n")
        f.write("  0\n")
        f.write("ENDSEC\n")

    def _generate_bookcase_parts(self, export_dir, part_number, width_mm, depth_mm, height_mm, sw_length_mm):
        """Generates individual DXF files for Bookcase unit parts."""
        # Calculate dimensions
        base_thickness_mm = 5.25 * 25.4
        wall_thickness_mm = 1 * 25.4
        back_thickness_mm = 0.75 * 25.4
        
        # Generate individual parts
        parts = [
            ("1 Back", self._generate_back_part, (width_mm, height_mm, back_thickness_mm)),
            ("1 Base Front", self._generate_base_front_part, (width_mm, base_thickness_mm, 0, 0)),
            ("1 Side Wall Left", self._generate_side_wall_part, (sw_length_mm, height_mm, wall_thickness_mm)),
            ("1 Side Wall Right", self._generate_side_wall_part, (sw_length_mm, height_mm, wall_thickness_mm)),
            ("1 Deck", self._generate_deck_part, (width_mm, depth_mm, 0.75 * 25.4)),
        ]
        
        for part_name, generator_func, args in parts:
            part_filename = f"{part_number} - {part_name}.dxf"
            part_filepath = os.path.join(export_dir, part_filename)
            generator_func(part_filepath, *args)

    def _generate_slice_rack_parts(self, export_dir, part_number, width_mm, depth_mm, height_mm, sw_length_mm):
        """Generates individual DXF files for Slice Rack unit parts."""
        # Calculate dimensions
        base_thickness_mm = 5.25 * 25.4
        wall_thickness_mm = 1 * 25.4
        back_thickness_mm = 0.75 * 25.4
        panel_height_mm = 6 * 25.4
        
        # Generate individual parts
        parts = [
            ("1 Back", self._generate_back_part, (width_mm, height_mm, back_thickness_mm)),
            ("1 Base Front", self._generate_base_front_part, (width_mm, base_thickness_mm, 0, 0)),
            ("1 Side Wall Left", self._generate_side_wall_part, (sw_length_mm, height_mm, wall_thickness_mm)),
            ("1 Side Wall Right", self._generate_side_wall_part, (sw_length_mm, height_mm, wall_thickness_mm)),
            ("1 Deck", self._generate_deck_part, (width_mm, depth_mm, 0.75 * 25.4)),
            ("1 Panel", self._generate_panel_part, (width_mm - 2 * wall_thickness_mm, panel_height_mm, wall_thickness_mm)),
        ]
        
        for part_name, generator_func, args in parts:
            part_filename = f"{part_number} - {part_name}.dxf"
            part_filepath = os.path.join(export_dir, part_filename)
            generator_func(part_filepath, *args)

    def _generate_side_wall_part(self, filepath, length_mm, height_mm, thickness_mm):
        """Generates a side wall DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Side wall outline
            self._add_dxf_line(f, 0, 0, length_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
            self._add_dxf_line(f, length_mm, 0, length_mm, height_mm, "0")  # Right
            self._add_dxf_line(f, 0, height_mm, length_mm, height_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, length_mm, -30, f"{length_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _generate_panel_part(self, filepath, width_mm, height_mm, thickness_mm):
        """Generates a panel DXF file."""
        with open(filepath, 'w') as f:
            self._write_dxf_header(f)
            self._write_dxf_layers(f)
            f.write("  0\n")
            f.write("SECTION\n")
            f.write("  2\n")
            f.write("ENTITIES\n")
            
            # Panel outline
            self._add_dxf_line(f, 0, 0, width_mm, 0, "0")  # Bottom
            self._add_dxf_line(f, 0, 0, 0, height_mm, "0")  # Left
            self._add_dxf_line(f, width_mm, 0, width_mm, height_mm, "0")  # Right
            self._add_dxf_line(f, 0, height_mm, width_mm, height_mm, "0")  # Top
            
            # Dimensions
            self._add_dimension_line(f, 0, -30, width_mm, -30, f"{width_mm/25.4:.1f}\"", "Dimensions")
            self._add_dimension_line(f, -30, 0, -30, height_mm, f"{height_mm/25.4:.1f}\"", "Dimensions")
            
            f.write("  0\n")
            f.write("ENDSEC\n")
            f.write("  0\n")
            f.write("EOF\n")

    def _get_unit_parts(self, unit_type, shelf_type, shelf_material, num_shelves):
        """Returns a dictionary of parts for the specified unit type."""
        parts = {}
        
        # Common parts for all units
        parts["Back Panel"] = {
            "description": "Main back panel",
            "material": "Plywood/MDF",
            "dimensions": f"{self.width_var.get()}\" x {self.height_var.get()}\""
        }
        
        parts["Deck Panel"] = {
            "description": "Bottom deck panel", 
            "material": "Plywood/MDF",
            "dimensions": f"{self.width_var.get()}\" x {self.depth_var.get()}\""
        }
        
        # Unit-specific parts
        if unit_type == "Bookcase":
            if self.sideWallToggleVar.get():
                parts["Left Side Wall"] = {
                    "description": "Left side wall panel",
                    "material": "Plywood/MDF", 
                    "dimensions": f"{self.sideWallLengthVar.get()}\" x {self.height_var.get()}\""
                }
                parts["Right Side Wall"] = {
                    "description": "Right side wall panel",
                    "material": "Plywood/MDF",
                    "dimensions": f"{self.sideWallLengthVar.get()}\" x {self.height_var.get()}\""
                }
            
            # Add shelves
            for i in range(num_shelves):
                parts[f"Shelf {i+1}"] = {
                    "description": f"Fixed shelf {i+1}",
                    "material": shelf_material,
                    "dimensions": f"{self.width_var.get()}\" x {self.depth_var.get()}\""
                }
                
        elif unit_type == "Slice Rack":
            # Slice rack specific parts
            parts["Left End Panel"] = {
                "description": "Left end panel",
                "material": "Plywood/MDF",
                "dimensions": f"{self.depth_var.get()}\" x {self.height_var.get()}\""
            }
            parts["Right End Panel"] = {
                "description": "Right end panel", 
                "material": "Plywood/MDF",
                "dimensions": f"{self.depth_var.get()}\" x {self.height_var.get()}\""
            }
            
        elif unit_type == "Bunker":
            # Bunker specific parts
            parts["Front Panel"] = {
                "description": "Front panel",
                "material": "Plywood/MDF",
                "dimensions": f"{self.width_var.get()}\" x {self.height_var.get()}\""
            }
            parts["Left Side Panel"] = {
                "description": "Left side panel",
                "material": "Plywood/MDF", 
                "dimensions": f"{self.depth_var.get()}\" x {self.height_var.get()}\""
            }
            parts["Right Side Panel"] = {
                "description": "Right side panel",
                "material": "Plywood/MDF",
                "dimensions": f"{self.depth_var.get()}\" x {self.height_var.get()}\""
            }
            
        elif unit_type == "Endcap":
            # Endcap specific parts
            parts["Side Panel"] = {
                "description": "Side panel",
                "material": "Plywood/MDF",
                "dimensions": f"{self.depth_var.get()}\" x {self.height_var.get()}\""
            }
        
        # Add top and base parts
        if self.top_var.get() != "No Top":
            parts["Top Panel"] = {
                "description": f"{self.top_var.get()} top panel",
                "material": "Plywood/MDF",
                "dimensions": f"{self.width_var.get()}\" x {self.depth_var.get()}\""
            }
            
        if self.base_var.get() != "No Base":
            parts["Base Panel"] = {
                "description": f"{self.base_var.get()} base panel", 
                "material": "Plywood/MDF",
                "dimensions": f"{self.width_var.get()}\" x {self.depth_var.get()}\""
            }
        
        return parts

    def load_logo(self):
        """Attempt to load the logo image with proper error handling."""
        try:
            # Determine the base path to handle running as a script or a bundled app
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller creates a temp folder and stores path in _MEIPASS
                base_path = sys._MEIPASS
            else:
                base_path = os.path.abspath(".")

            logo_path = os.path.join(base_path, 'assets', 'logo.png')
            
            # Check if logo file exists before attempting to open
            if not os.path.exists(logo_path):
                print(f"Logo file not found at: {logo_path}")
                return None
                
            # Attempt to open and process the logo image
            logo_image = Image.open(logo_path)
            # Resize the logo to fit your UI. Adjust dimensions as needed.
            logo_image = logo_image.resize((250, 60), Image.Resampling.LANCZOS) 
            
            # Convert to PhotoImage for Tkinter
            logo_photo = ImageTk.PhotoImage(logo_image)
            return logo_photo
            
        except (FileNotFoundError, IOError, OSError) as e:
            print(f"Error loading logo image: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error loading logo: {e}")
            return None

    def display_logo_or_fallback(self, parent):
        """Display logo image or fallback text if logo is not available."""
        logo_photo = self.load_logo()
        
        if logo_photo:
            # Display the logo image
            logo_label = ttk.Label(parent, image=logo_photo)
            # IMPORTANT: Keep a reference to prevent garbage collection
            logo_label.image = logo_photo
            logo_label.pack(pady=(5, 15))
            print("Logo loaded successfully")
        else:
            # Display fallback text with enhanced styling
            logo_label = ttk.Label(
                parent, 
                text="OmniPOP Design Portal", 
                font=("Arial", 18, "bold"),
                foreground="#2E86AB"  # Professional blue color
            )
            logo_label.pack(pady=(5, 15))
            print("Using fallback text logo")

    def create_ui_elements(self, parent):
        # --- Add Logo with Enhanced Fallback ---
        self.display_logo_or_fallback(parent)

        # Global list for manual shelf entries
        self.manualShelfEntries = []

        # Reset to defaults button
        self.reset_button = ttk.Button(parent, text="Reset to Defaults", command=self.reset_all_unit_types_to_default)
        self.reset_button.pack(pady=5)

        ttk.Label(parent, text="Select Unit Type:").pack(pady=5)
        self.unitTypeVar = tk.StringVar(value="Endcap")
        self.unitTypeCombo = ttk.Combobox(parent, textvariable=self.unitTypeVar,
                                     values=["Endcap", "Bookcase", "Slice Rack", "Bunker"], state="readonly")
        self.unitTypeCombo.pack(pady=5)
        self.unitTypeCombo.bind("<<ComboboxSelected>>", self.on_unit_type_change)

        # Unit Width with Override checkbox
        width_frame = ttk.Frame(parent)
        width_frame.pack(pady=5)
        
        ttk.Label(width_frame, text="Unit Width (in):").pack()
        
        width_input_frame = ttk.Frame(width_frame)
        width_input_frame.pack()
        
        self.width_var = tk.DoubleVar(value=48.0)
        self.entry_width = ttk.Spinbox(width_input_frame, from_=0, to=1000, increment=0.25, textvariable=self.width_var, width=10, format="%.2f")
        self.entry_width.pack(side=tk.LEFT, padx=(0, 5))
        
        self.width_override_var = tk.BooleanVar(value=False)
        self.width_override_check = ttk.Checkbutton(width_input_frame, text="Override", variable=self.width_override_var, command=self.on_width_override_toggle)
        self.width_override_check.pack(side=tk.LEFT)
        
        self.width_var.trace_add("write", self.on_width_change)

        ttk.Label(parent, text="Unit Depth (in):").pack()
        self.depth_var = tk.DoubleVar(value=48.0)
        self.entry_depth = ttk.Spinbox(parent, from_=0, to=1000, increment=0.25, textvariable=self.depth_var, width=10, format="%.2f")
        self.entry_depth.pack()
        self.depth_var.trace_add("write", self.calculate_values)

        ttk.Label(parent, text="Total Height (in):").pack()
        self.height_var = tk.DoubleVar(value=96.0)
        self.entry_height = ttk.Spinbox(parent, from_=0, to=1000, increment=0.25, textvariable=self.height_var, width=10, format="%.2f")
        self.entry_height.pack()
        self.height_var.trace_add("write", self.calculate_values)

        # Side Wall Length spinbox placed immediately after Total Height.
        self.sideWallFrame = ttk.Frame(parent)

        self.sideWallToggleVar = tk.BooleanVar(value=True)
        self.sideWallCheck = ttk.Checkbutton(self.sideWallFrame, variable=self.sideWallToggleVar, command=lambda: (self.toggle_side_wall_input(), self.calculate_values()))
        self.sideWallCheck.pack(side=tk.LEFT, padx=2)

        ttk.Label(self.sideWallFrame, text="Side Wall Length (in):").pack(side=tk.LEFT, padx=2)
        self.sideWallLengthVar = tk.DoubleVar(value=25.0)
        self.sideWallSpin = ttk.Spinbox(self.sideWallFrame, from_=0, to=100, increment=0.25, textvariable=self.sideWallLengthVar, width=10, format="%.2f")
        self.sideWallSpin.pack(side=tk.LEFT, padx=2)
        self.sideWallLengthVar.trace_add("write", self.calculate_values)

        self.fullWallCheck = ttk.Checkbutton(self.sideWallFrame, text="Full Wall", variable=self.fullWallVar, command=self.on_full_wall_toggle)
        self.fullWallCheck.pack(side=tk.LEFT, padx=5)
        
        self.sideWallFrame.pack(pady=5)

        ttk.Label(parent, text="Top Option:").pack(pady=5)
        self.top_var = tk.StringVar()
        self.top_combo = ttk.Combobox(parent, textvariable=self.top_var, values=["Canopy", "Fascia", "No Top", "Solid Top"], state="readonly")
        self.top_combo.current(0)
        self.top_combo.pack()
        self.top_combo.bind("<<ComboboxSelected>>", self.calculate_values)
        self.top_var.trace("w", self.calculate_values)

        ttk.Label(parent, text="Base Option:").pack(pady=5)
        self.base_var = tk.StringVar()
        self.base_combo = ttk.Combobox(parent, textvariable=self.base_var, values=["Base", "No Base"], state="readonly")
        self.base_combo.current(0)
        self.base_combo.pack()
        self.base_combo.bind("<<ComboboxSelected>>", self.calculate_values)
        self.base_var.trace("w", self.calculate_values)

        # Shelf Configuration Frame
        self.shelfFeatureFrame = ttk.Frame(parent, relief=tk.RIDGE, borderwidth=2)
        self.shelfFeatureFrame.pack(fill=tk.X, padx=5, pady=5)

        shelf_config_frame = ttk.Frame(self.shelfFeatureFrame)
        shelf_config_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(shelf_config_frame, text="Shelving Type:").pack(side=tk.LEFT, padx=(0, 5))
        self.shelfTypeVar = tk.StringVar(value="Fixed")
        self.shelfTypeCombo = ttk.Combobox(shelf_config_frame, textvariable=self.shelfTypeVar,
                                           values=["Fixed", "Pins", "Clips", "Standard & Brackets"],
                                           state="readonly", width=18)
        self.shelfTypeCombo.pack(side=tk.LEFT, padx=5)
        self.shelfTypeCombo.bind("<<ComboboxSelected>>", self.calculate_values)

        material_frame = ttk.Frame(shelf_config_frame)
        material_frame.pack(side=tk.LEFT, padx=20)
        self.shelfMaterialVar = tk.StringVar(value="Melamine")
        ttk.Radiobutton(material_frame, text="Melamine (3/4\")", variable=self.shelfMaterialVar, value="Melamine", command=self.on_shelf_material_change).pack(anchor='w')
        ttk.Radiobutton(material_frame, text="Wire (1/4\")", variable=self.shelfMaterialVar, value="Wire", command=self.on_shelf_material_change).pack(anchor='w')
        
        # Color selection for melamine
        color_frame = ttk.Frame(shelf_config_frame)
        color_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(color_frame, text="Melamine Color:").pack(anchor='w')
        self.melamine_color_var = tk.StringVar(value="Black")
        self.melamine_color_combo = ttk.Combobox(color_frame, textvariable=self.melamine_color_var,
                                               values=["Black", "White", "Gray", "Cherry", "Spring Blossom", "Hardrock Maple"],
                                               state="readonly", width=12)
        self.melamine_color_combo.pack(anchor='w')
        self.melamine_color_combo.bind("<<ComboboxSelected>>", self.on_melamine_color_change)
        
        # Wire shelf width selector (only visible when Wire is selected) - on its own row
        self.wire_shelf_frame = ttk.Frame(self.shelfFeatureFrame)
        ttk.Label(self.wire_shelf_frame, text="Wire Shelf Width:").pack(side=tk.LEFT, padx=(5, 5))
        self.wire_shelf_width_var = tk.StringVar(value="24")
        self.wire_shelf_combo = ttk.Combobox(self.wire_shelf_frame, textvariable=self.wire_shelf_width_var,
                                             values=["12", "16", "24", "36", "48"],
                                             state="readonly", width=8)
        self.wire_shelf_combo.pack(side=tk.LEFT)
        self.wire_shelf_combo.bind("<<ComboboxSelected>>", self.on_wire_shelf_width_change)
        # Initially hidden - will be shown/hidden by on_shelf_material_change

        # Shelf Management Frame
        self.shelf_management_frame = ttk.Frame(self.shelfFeatureFrame)
        self.shelf_management_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(self.shelf_management_frame, text="Number of Shelves:").pack(side=tk.LEFT, padx=2)
        self.numShelvesVar = tk.IntVar(value=0)
        self.shelf_spinbox = ttk.Spinbox(self.shelf_management_frame, from_=0, to=20, width=5, textvariable=self.numShelvesVar)
        self.shelf_spinbox.pack(side=tk.LEFT, padx=2)
        self.numShelvesVar.trace_add("write", self.on_shelf_count_change)

        self.manualShelfEntriesFrame = ttk.Frame(self.shelfFeatureFrame)
        self.manualShelfEntriesFrame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(self.manualShelfEntriesFrame, text="Shelf Spacings (from bottom up):").pack()

        self.shelfOutputFrame = ttk.Frame(self.shelfFeatureFrame)
        self.shelfOutputFrame.pack(fill=tk.X, padx=5, pady=5)
        self.lbl_shelves = ttk.Label(self.shelfOutputFrame, text="Number of Shelves: 0")
        self.lbl_shelves.pack(pady=2)
        # These labels will be replaced by the dynamic editable fields
        # They are kept for backward compatibility but will be hidden
        self.lbl_col_width = ttk.Label(self.shelfOutputFrame, text="")
        self.lbl_col_depth = ttk.Label(self.shelfOutputFrame, text="")
        self.lbl_pole_front = ttk.Label(self.shelfOutputFrame, text="")
        self.lbl_pole_side = ttk.Label(self.shelfOutputFrame, text="")

        # Frame for manual pole and column inputs
        self.manual_pole_col_frame = ttk.Frame(self.shelfFeatureFrame)
        self.manual_pole_col_frame.pack(fill=tk.X, padx=5, pady=5)
        self.pole_spacing_entries = []
        self.column_dim_entries = {}

        # Additional bindings for instant updates
        for widget in [self.entry_width, self.entry_depth, self.entry_height, self.sideWallSpin]:
            widget.bind("<KeyRelease>", self.calculate_values)
            widget.bind("<FocusOut>", self.calculate_values)
            widget.bind("<Button-1>", self.calculate_values)
        
        # Create pricing panel (initially hidden)
        self.create_pricing_panel(parent)

    def get_column_width(self, unit_width):
        """Calculate default column width based on unit width."""
        return 8 + (2 * int((unit_width - 48) / 12)) if unit_width > 48 else 8
    
    def get_column_depth(self, unit_depth):
        """Calculate default column depth based on unit depth."""
        return 10 + (2 * int((unit_depth - 48) / 6)) if unit_depth > 48 else 10

    def _update_dynamic_pole_column_ui(self):
        """Dynamically creates and manages input fields for pole and column dimensions."""
        # Clear previous manual entries
        for widget in self.manual_pole_col_frame.winfo_children():
            widget.destroy()
        self.pole_spacing_entries = []
        self.column_dim_entries = {}
        self.pole_front_entries = []

        unit_type = self.unitTypeVar.get()
        unit_width = self.width_var.get()
        unit_depth = self.depth_var.get()

        if unit_type == "Endcap":
            # --- POLE SIDE POSITIONS UI ---
            default_pole_positions = self.compute_pole_positions_width(unit_width)
            if default_pole_positions:
                ttk.Label(self.manual_pole_col_frame, text="Pole Side Positions (from edge):").pack(anchor=tk.W)
                for i, pos in enumerate(default_pole_positions):
                    frame = ttk.Frame(self.manual_pole_col_frame)
                    frame.pack(fill=tk.X, padx=20)
                    ttk.Label(frame, text=f"Pole {i+1}:", width=8).pack(side=tk.LEFT)
                    var = tk.DoubleVar(value=round(pos, 2))
                    entry = ttk.Spinbox(frame, from_=0, to=unit_width, increment=0.25, textvariable=var, width=8, format="%.2f")
                    entry.pack(side=tk.LEFT, padx=5)
                    entry.bind("<KeyRelease>", self.calculate_values)
                    entry.bind("<FocusOut>", self.calculate_values)
                    self.pole_spacing_entries.append(var)

            # --- POLE FRONT SPACING UI ---
            default_front_distance = self.pole_front_distance(unit_depth)
            ttk.Label(self.manual_pole_col_frame, text="Pole Front Spacing (from back):").pack(anchor=tk.W)
            front_frame = ttk.Frame(self.manual_pole_col_frame)
            front_frame.pack(fill=tk.X, padx=20)
            ttk.Label(front_frame, text="Distance:", width=8).pack(side=tk.LEFT)
            front_var = tk.DoubleVar(value=round(default_front_distance, 2))
            front_entry = ttk.Spinbox(front_frame, from_=0, to=unit_depth, increment=0.25, textvariable=front_var, width=8, format="%.2f")
            front_entry.pack(side=tk.LEFT, padx=5)
            front_entry.bind("<KeyRelease>", self.calculate_values)
            front_entry.bind("<FocusOut>", self.calculate_values)
            self.pole_front_entries = [front_var]

            # --- COLUMN UI ---
            default_col_width = self.get_column_width(unit_width)
            default_col_depth = self.get_column_depth(unit_depth)

            col_frame = ttk.Frame(self.manual_pole_col_frame)
            col_frame.pack(fill=tk.X, pady=(10, 0))
            ttk.Label(col_frame, text="Column Dimensions:").pack(anchor=tk.W)

            w_frame = ttk.Frame(col_frame)
            w_frame.pack(fill=tk.X, padx=20)
            ttk.Label(w_frame, text="Width:", width=8).pack(side=tk.LEFT)
            cw_var = tk.DoubleVar(value=round(default_col_width, 2))
            cw_entry = ttk.Spinbox(w_frame, from_=0, to=unit_width, increment=0.25, textvariable=cw_var, width=8, format="%.2f")
            cw_entry.pack(side=tk.LEFT, padx=5)
            cw_entry.bind("<KeyRelease>", self.calculate_values)
            cw_entry.bind("<FocusOut>", self.calculate_values)

            d_frame = ttk.Frame(col_frame)
            d_frame.pack(fill=tk.X, padx=20)
            ttk.Label(d_frame, text="Depth:", width=8).pack(side=tk.LEFT)
            cd_var = tk.DoubleVar(value=round(default_col_depth, 2))
            cd_entry = ttk.Spinbox(d_frame, from_=0, to=unit_depth, increment=0.25, textvariable=cd_var, width=8, format="%.2f")
            cd_entry.pack(side=tk.LEFT, padx=5)
            cd_entry.bind("<KeyRelease>", self.calculate_values)
            cd_entry.bind("<FocusOut>", self.calculate_values)

            self.column_dim_entries = {'w': cw_var, 'd': cd_var}

    def calculate_values(self, *args):
        try:
            if self._loading_settings: # Prevent re-calculation loops when loading settings
                return

            self.part_list = [] # Reset once at the beginning

            sel = self.unitTypeVar.get()
            unit_width = self.width_var.get()
            unit_depth = self.depth_var.get()
            total_height = self.height_var.get()
            base_thickness = self.base_thickness if self.base_var.get() == "Base" else 0
            deck_thickness = self.deck_thickness # Deck is always present if base exists
            
            # --- POLE & COLUMN CALCULATION ---
            pole_positions_width = []
            pole_positions_depth = []
            num_columns = 0
            col_width = 0
            col_depth = 0
            
            if sel == "Endcap":
                # Use manual values from UI if available, otherwise use defaults
                if self.pole_spacing_entries:
                    try:
                        pole_positions_width = [var.get() for var in self.pole_spacing_entries]
                    except tk.TclError: # Handles case where UI is updating
                        pole_positions_width = self.compute_pole_positions_width(unit_width)
                else:
                    pole_positions_width = self.compute_pole_positions_width(unit_width)
                
                # Use manual front distance if available
                if hasattr(self, 'pole_front_entries') and self.pole_front_entries:
                    try:
                        pole_positions_depth = [self.pole_front_entries[0].get()]
                    except tk.TclError: # Handles case where UI is updating
                        pole_positions_depth = [self.pole_front_distance(unit_depth)]
                else:
                    pole_positions_depth = [self.pole_front_distance(unit_depth)]

                num_columns = 1
                if self.column_dim_entries.get('w') and self.column_dim_entries.get('d'):
                    try:
                        col_width = self.column_dim_entries['w'].get()
                        col_depth = self.column_dim_entries['d'].get()
                    except tk.TclError: # Handles case where UI is updating
                        col_width = self.get_column_width(unit_width)
                        col_depth = self.get_column_depth(unit_depth)
                else:
                    col_width = self.get_column_width(unit_width)
                    col_depth = self.get_column_depth(unit_depth)

            
            top_option = self.top_var.get()
            top_thickness = 0
            if top_option in ["Canopy", "Fascia"]:
                top_thickness = 8
            elif top_option == "Solid Top":
                top_thickness = 0.75

            shelf_type = self.shelfTypeVar.get()
            shelf_material = self.shelfMaterialVar.get()
            panel_is_required = shelf_type == "Standard & Brackets"

            shelf_thickness = 0.25 if shelf_material == "Wire" else self.shelf_thickness
            
            shelf_spacings = [entry['var'].get() for entry in self.manualShelfEntries]

            sw_length = self.sideWallLengthVar.get() if self.sideWallToggleVar.get() else 0

            # --- PART CALCULATION LOGIC ---
            
            # 1. Back Panel (common to all but should be conditional)
            if sel in ["Bookcase", "Slice Rack", "Bunker", "Endcap"]:
                self.part_list.append({
                    'name': 'Back Panel', 
                    'w': unit_width, 
                    'h': total_height, 
                    'th': self.parts['back_panel']['thickness'],
                    'material': self.get_material_name(self.parts['back_panel']['material'])
                })

            # 2. Base & Deck
            if base_thickness > 0:
                # Base Front - full unit width
                self.part_list.append({'name': 'Base Front', 'w': unit_width, 'h': base_thickness, 'th': 0.75, 'qty': 1, 'material': self.get_material_name('Melamine')})
                
                # Base Sides - unit depth minus back panel and base front thickness
                back_panel_thickness_inches = self.parts['back_panel']['thickness']
                base_side_length = unit_depth - back_panel_thickness_inches - 0.75  # 0.75" for base front thickness
                self.part_list.append({'name': 'Base Side', 'w': base_side_length, 'h': base_thickness, 'th': 0.75, 'qty': 2, 'material': self.get_material_name('Melamine')})
                
            if deck_thickness > 0 and base_thickness > 0: # Deck only exists with a base
                # Deck dowels into the back panel, so it's less deep than the overall unit
                back_panel_thickness_inches = self.parts['back_panel']['thickness']
                deck_depth = unit_depth - back_panel_thickness_inches
                self.part_list.append({'name': 'Deck', 'w': unit_width, 'h': deck_depth, 'th': deck_thickness, 'material': self.get_material_name('Melamine')})

            # 3. Top
            if top_thickness > 0:
                if top_option == "Canopy":
                    self.part_list.append({'name': 'Canopy Front', 'w': unit_width, 'h': top_thickness, 'th': 0.75, 'material': self.get_material_name('Melamine')})
                    self.part_list.append({'name': 'Canopy Back', 'w': unit_width, 'h': top_thickness, 'th': 0.75, 'material': self.get_material_name('Melamine')})
                    # Canopy sides sit inside the front and back, so they're shorter
                    canopy_side_width = unit_depth - (2 * 0.75)  # Subtract thickness of front and back
                    self.part_list.append({'name': 'Canopy Side', 'w': canopy_side_width, 'h': top_thickness, 'th': 0.75, 'qty': 2, 'material': self.get_material_name('Melamine')})
                    if sel == "Endcap":
                        x_positions = pole_positions_width # Use the potentially overridden values
                        num_supports = len(x_positions)
                        if num_supports > 0:
                            # Canopy supports run between front and back, so height is unit depth minus front and back thickness
                            canopy_support_height = unit_depth - (2 * 0.75)  # Subtract thickness of front and back
                            self.part_list.append({
                                'name': 'Canopy Support',
                                'w': 6,
                                'h': canopy_support_height,
                                'th': 0.75,
                                'qty': num_supports
                            })
                elif top_option == "Fascia":
                    fascia_height = 8
                    fascia_thickness = 0.75
                    
                    # For Endcap units, create Fascia like Canopy but without back panel
                    if sel == "Endcap":
                        # Fascia Front (like Canopy Front)
                        self.part_list.append({'name': 'Fascia Front', 'w': unit_width, 'h': fascia_height, 'th': 0.75})
                        
                        # Fascia sides sit inside the front, so they're shorter (no back panel to subtract)
                        fascia_side_width = unit_depth - 0.75  # Subtract thickness of front only
                        self.part_list.append({'name': 'Fascia Side', 'w': fascia_side_width, 'h': fascia_height, 'th': 0.75, 'qty': 2})
                        
                        # Add Fascia Supports (2 supports like Canopy Supports)
                        fascia_support_height = unit_depth - 0.75  # Subtract thickness of front only
                        self.part_list.append({
                            'name': 'Fascia Support',
                            'w': 6,
                            'h': fascia_support_height,
                            'th': 0.75,
                            'qty': 2
                        })
                    else:
                        # For other units, just the main Fascia panel
                        self.part_list.append({'name': 'Fascia', 'w': unit_width, 'h': fascia_height, 'th': fascia_thickness})
                elif top_option == "Solid Top":
                    self.part_list.append({'name': 'Solid Top', 'w': unit_width, 'h': unit_depth, 'th': top_thickness})

            # 4. Shelves
            three_mm_in_inches = 0.11811
            back_panel_thickness_inches = self.parts['back_panel']['thickness']
            standard_thickness_inches = self.parts['standards']['thickness'] if shelf_type == "Standard & Brackets" else 0
            shelf_depth_inches = unit_depth - back_panel_thickness_inches - standard_thickness_inches - three_mm_in_inches
            
            side_wall_thickness = self.parts['side_walls']['thickness']
            shelf_width = unit_width - (2 * side_wall_thickness) if sw_length > 0 else unit_width
            
            for _ in shelf_spacings:
                self.part_list.append({'name': 'Shelf', 'w': shelf_width, 'h': shelf_depth_inches, 'th': shelf_thickness, 'material': self.get_material_name('Melamine')})
            
            # 5. Side Walls
            if sel in ["Bookcase", "Slice Rack", "Bunker"] and sw_length > 0:
                # Calculate correct side wall height
                # Side walls sit on top of deck and go to top of back panel
                deck_height = deck_thickness if deck_thickness > 0 else 0
                base_height = base_thickness if base_thickness > 0 else 0
                side_wall_height = total_height - base_height - deck_height
                
                self.part_list.append({
                    'name': 'Side Wall', 
                    'w': sw_length, 
                    'h': side_wall_height, 
                    'th': self.parts['side_walls']['thickness'], 
                    'qty': 2,
                    'material': self.get_material_name('Melamine')
                })
            
            # 6. Base Panel
            if panel_is_required:
                self.part_list.append({
                    'name': 'Base Panel', 
                    'w': unit_width, 
                    'h': 5, # Height is 5"
                    'th': self.parts['base_panel']['thickness']
                })
            
            # 7. Endcap-specific parts (Columns)
            if sel == "Endcap":
                column_height = 0
                # Calculate column height first based on the new rules
                if shelf_spacings:
                    # From top of deck to bottom of top shelf
                    # This is the sum of all spacings plus the thickness of all shelves below the top one.
                    num_shelves = len(shelf_spacings)
                    if num_shelves > 0:
                        column_height = sum(shelf_spacings) + (num_shelves - 1) * shelf_thickness
                    else: # This case should not be hit if shelf_spacings is not empty, but as a fallback:
                        column_height = total_height - base_thickness - deck_thickness - top_thickness
                else:
                    # No shelves
                    if top_option in ["Canopy", "Fascia"]:
                        # From top of deck to bottom of canopy
                        column_height = total_height - base_thickness - deck_thickness - top_thickness
                    else: # No canopy
                        # To top of back minus 1/8th of total height
                        column_top_from_floor = total_height * (7/8)
                        deck_top_from_floor = base_thickness + deck_thickness
                        column_height = column_top_from_floor - deck_top_from_floor

                # Column dimensions are now calculated earlier in the function
                # and may be overridden by manual inputs
                
                # Per user feedback, an Endcap unit ALWAYS has exactly one column.
                # The number of poles is a separate concept for visual drawing only.
                num_columns = 1 
                
                self.part_list.append({'name': 'Column Side', 'w': col_depth, 'h': column_height, 'th': 0.75, 'qty': 2 * num_columns})
                self.part_list.append({'name': 'Column Front', 'w': col_width - 1.5, 'h': column_height, 'th': 0.75, 'qty': num_columns})

            # --- UI & DRAWING LOGIC ---
            self.lbl_shelves.config(text=f"Number of Shelves: {len(self.manualShelfEntries)}")

            if sel == "Endcap":
                # Use the calculated values (potentially from manual inputs)
                x_positions = pole_positions_width
                front_dist = pole_positions_depth[0] if pole_positions_depth else self.pole_front_distance(unit_depth)
                
                # Clear old labels since we now use editable fields
                self.lbl_col_width.config(text="")
                self.lbl_col_depth.config(text="")
                self.lbl_pole_front.config(text="")
                self.lbl_pole_side.config(text="")
                
                self.draw_endcap(unit_width, unit_depth, total_height, top_thickness, base_thickness,
                            col_width, col_depth, shelf_thickness, shelf_spacings, x_positions, front_dist, shelf_type, column_height, shelf_material)
            elif sel in ["Bookcase", "Slice Rack", "Bunker"]:
                self.lbl_col_width.config(text="")
                self.lbl_col_depth.config(text="")
                self.lbl_pole_front.config(text="")
                self.lbl_pole_side.config(text="")
                if sel == "Bookcase":
                    self.draw_bookcase(unit_width, unit_depth, total_height, top_thickness, base_thickness,
                                  shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material)
                elif sel == "Slice Rack":
                    self.draw_slice_rack(unit_width, unit_depth, total_height, top_thickness, base_thickness,
                                    shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material)
                elif sel == "Bunker":
                    self.draw_bunker(unit_width, unit_depth, total_height, top_thickness, base_thickness,
                                     shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material)
            
            self._update_parts_count_display()
            
            # Update pricing display if authenticated
            if self.is_zoho_authenticated():
                self.update_pricing_display()

        except Exception as ex:
            print("Error in calculate_values:", ex)
            # You might want to handle specific errors, e.g., from self.width_var.get()
            self.lbl_col_width.config(text="Invalid input!")
            self.lbl_col_depth.config(text="")
            self.lbl_pole_front.config(text="")
            self.lbl_pole_side.config(text="")
            self.lbl_shelves.config(text="")

    def _update_parts_count_display(self):
        """Updates the parts count label in the info bar."""
        count = 0
        for part in self.part_list:
            count += part.get('qty', 1)
        self.parts_count_var.set(f"Parts: {count}")

    def reset_all_unit_types_to_default(self):
        """Resets all unit types to their default settings."""
        self.unit_type_settings.clear()
        self.on_unit_type_change()

    def on_unit_type_change(self, event=None):
        """Handle changes to the unit type dropdown."""
        # --- Save current state before changing anything ---
        if hasattr(self, 'current_unit_type') and self.current_unit_type:
            previous_unit_type = self.current_unit_type
            if not self._loading_settings:
                self.unit_type_settings[previous_unit_type] = {
                    'width': self.width_var.get(),
                    'depth': self.depth_var.get(),
                    'height': self.height_var.get(),
                    'side_wall_length': self.sideWallLengthVar.get(),
                    'side_wall_toggle': self.sideWallToggleVar.get(),
                    'full_wall': self.fullWallVar.get(),
                    'top_option': self.top_var.get(),
                    'base_option': self.base_var.get(),
                    'shelf_type': self.shelfTypeVar.get(),
                    'shelf_material': self.shelfMaterialVar.get(),
                    'num_shelves': self.numShelvesVar.get(),
                    'shelf_spacings': [e['var'].get() for e in self.manualShelfEntries]
                }

        unit_type = self.unitTypeVar.get()
        self.current_unit_type = unit_type

        # --- Update Dynamic UI ---
        # This will create/destroy pole and column input fields as needed
        self._update_dynamic_pole_column_ui()

        # --- Load new state or apply defaults ---
        if unit_type in self.unit_type_settings:
            try:
                self._loading_settings = True
                settings = self.unit_type_settings[unit_type]
                
                self.width_var.set(settings['width'])
                self.depth_var.set(settings['depth'])
                self.height_var.set(settings['height'])
                self.sideWallLengthVar.set(settings['side_wall_length'])
                self.sideWallToggleVar.set(settings['side_wall_toggle'])
                self.fullWallVar.set(settings['full_wall'])
                self.top_var.set(settings['top_option'])
                self.base_var.set(settings['base_option'])
                self.shelfTypeVar.set(settings['shelf_type'])
                self.shelfMaterialVar.set(settings['shelf_material'])
                
                self.numShelvesVar.set(settings['num_shelves'])
                
                for i, spacing in enumerate(settings['shelf_spacings']):
                    if i < len(self.manualShelfEntries):
                        self.manualShelfEntries[i]['var'].set(spacing)
            finally:
                self._loading_settings = False
            
            self.toggle_side_wall_input()
            self.calculate_values()
        else:
            # Set available shelving types based on unit type
            if unit_type == "Bunker":
                self.shelfTypeCombo.config(values=["Fixed", "Pins", "Clips"])
            else:
                self.shelfTypeCombo.config(values=["Fixed", "Pins", "Clips", "Standard & Brackets"])

            if unit_type == "Slice Rack":
                self.shelfTypeVar.set("Standard & Brackets")
                self.shelfMaterialVar.set("Wire")
                self.width_var.set(48.0)
                self.depth_var.set(21.0)
                self.height_var.set(96.0)
            elif unit_type == "Endcap":
                self.shelfTypeVar.set("Fixed")
                self.shelfMaterialVar.set("Melamine")
                self.width_var.set(48.0)
                self.depth_var.set(48.0)
                self.height_var.set(90.0)
            elif unit_type == "Bookcase":
                self.shelfTypeVar.set("Fixed")
                self.shelfMaterialVar.set("Melamine")
                self.width_var.set(24.0)
                self.depth_var.set(24.0)
                self.height_var.set(90.0)
            elif unit_type == "Bunker":
                self.shelfTypeVar.set("Fixed")
                self.shelfMaterialVar.set("Melamine")
                self.width_var.set(36.0)
                self.depth_var.set(16.0)
                self.height_var.set(32.0)
                self.top_var.set("Solid Top")
                self.base_var.set("Base")
                self.numShelvesVar.set(2)
            else: # Default fallback
                self.shelfTypeVar.set("Fixed")

            # Set default side wall length for applicable units
            if unit_type in ["Bookcase", "Slice Rack", "Bunker"]:
                unit_depth = self.depth_var.get()
                default_sw_length = (unit_depth / 2) + 0.75
                self.sideWallLengthVar.set(default_sw_length)

            self.fullWallVar.set(False)
            self.toggle_side_wall_input()
            
            # Handle wire shelf frame visibility and auto-adjust width for Slice Rack
            if unit_type == "Slice Rack" and self.shelfMaterialVar.get() == "Wire":
                # Pack before shelf_management_frame using before= parameter
                self.wire_shelf_frame.pack(fill=tk.X, padx=5, pady=(0, 5), before=self.shelf_management_frame)
                if not self.width_override_var.get():
                    self.auto_adjust_width_for_wire_shelf()
            else:
                self.wire_shelf_frame.pack_forget()
            
            self.on_shelf_count_change()

    def on_full_wall_toggle(self, *args):
        """Handles toggling the 'Full Wall' checkbox."""
        self.toggle_side_wall_input()
        
        if self.fullWallVar.get():
            unit_depth = self.depth_var.get()
            full_length = unit_depth - self.parts['back_panel']['thickness']
            self.sideWallLengthVar.set(full_length)
        else:
            unit_depth = self.depth_var.get()
            default_length = (unit_depth / 2) + 0.75
            self.sideWallLengthVar.set(default_length)

    # -------------------- CALCULATION FUNCTIONS --------------------
    def compute_pole_positions_width(self, width):
        """Return pole x-positions (in inches)."""
        base_positions = [14, width - 14]
        if width > 54:
            extra = int((width - 54) / 12)  # one extra pole per 12" beyond 54
            total = 2 + extra
            spacing = (width - 28) / (total - 1)
            return [14 + i * spacing for i in range(total)]
        return base_positions

    def _format_measurement(self, value_in_inches):
        """Formats a measurement in inches into the current display unit (in or mm)."""
        if self.display_unit == 'mm':
            value_mm = value_in_inches * 25.4
            return f"{value_mm:.0f}mm"
        else:  # 'in'
            return f"{value_in_inches:.2f}\""

    def pole_front_distance(self, depth):
        """Return front distance (in inches) for pole placement."""
        if depth >= 48:
            return 14
        elif 36 <= depth <= 46:
            return 12
        else:
            return 10

    def calculate_column_parts(self, col_width, col_depth):
        """Calculate dimensions for 3-piece column construction (2 sides + 1 front)."""
        # Column parts for 3-piece construction
        side_thickness = 0.75  # Standard thickness for sides
        front_thickness = 0.75  # Standard thickness for front
        
        # Two side pieces (left and right)
        side_width = col_width
        side_depth = col_depth
        side_height = col_depth  # Height equals depth for sides
        
        # One front piece
        front_width = col_width - (2 * side_thickness)  # Width minus both side thicknesses
        front_depth = front_thickness
        front_height = col_depth
        
        return {
            'left_side': {'width': side_width, 'depth': side_depth, 'height': side_height, 'thickness': side_thickness},
            'right_side': {'width': side_width, 'depth': side_depth, 'height': side_height, 'thickness': side_thickness},
            'front': {'width': front_width, 'depth': front_depth, 'height': front_height, 'thickness': front_thickness}
        }

    def mm_to_in(self, mm):
        """Converts millimeters to inches."""
        return mm / 25.4

    def _calculate_shelf_y_positions(self, start_y, shelf_spacings, shelf_thickness, scale):
        """Calculates the center Y coordinates for each shelf."""
        shelf_y_centers = []
        current_y = start_y
        if not shelf_spacings:
            return shelf_y_centers

        for sp in shelf_spacings:
            shelf_bottom = current_y - sp * scale
            shelf_top = shelf_bottom - (shelf_thickness * scale)
            shelf_center_y = (shelf_top + shelf_bottom) / 2
            shelf_y_centers.append(shelf_center_y)
            current_y = shelf_top
        return shelf_y_centers

    # -------------------- DRAWING HELPER FUNCTIONS --------------------
    def _setup_front_canvas(self, width, height):
        """Clears and sets up the front canvas with a base frame and measurement arrows."""
        self.canvas_front.delete("all")
        margin = 50  # Larger margin for better visibility
        cf_w, cf_h = self.canvas_front.winfo_width(), self.canvas_front.winfo_height()
        if cf_w <= 1 or cf_h <= 1: return 0, 0, 0, 0, 0 # Avoid drawing if canvas not ready
        scale = min((cf_w - 2 * margin) / width, (cf_h - 2 * margin) / height)
        
        # Center the drawing in the canvas
        drawing_width = width * scale
        drawing_height = height * scale
        x0 = (cf_w - drawing_width) / 2
        y0 = (cf_h - drawing_height) / 2
        x1 = x0 + drawing_width
        y1 = y0 + drawing_height

        self.canvas_front.create_rectangle(x0, y0, x1, y1, outline="black", fill="lightgray")
        # Width measurement (horizontal) - in viewport white space
        # Use red color if width is insufficient for wire shelves
        width_color = "red" if self._width_warning else "black"
        self.canvas_front.create_line(x0, y0 - 20, x1, y0 - 20, arrow=tk.BOTH, width=2, fill=width_color)
        self.canvas_front.create_text((x0 + x1) / 2, y0 - 35, text=self._format_measurement(width), font=("Arial", 12), fill=width_color)
        # Height measurement (vertical) - in viewport white space
        arrow_x = x1 + 20
        self.canvas_front.create_line(arrow_x, y0, arrow_x, y1, arrow=tk.BOTH, width=2)
        self.canvas_front.create_text(arrow_x + 10, (y0 + y1) / 2, text=self._format_measurement(height), font=("Arial", 12), anchor="w", fill="black")
        return x0, y0, x1, y1, scale

    def _draw_front_canopy(self, x0, y0, x1, top_thickness, scale, top_option, sw_length):
        """Draws the canopy on the front canvas if applicable."""
        canopy_h = 0
        if top_thickness > 0:
            canopy_h = top_thickness * scale
            
            if top_option == "Fascia":
                if self.unitTypeVar.get() == "Endcap":
                    # For Endcap units, draw Fascia as one piece (like Canopy Front)
                    self.canvas_front.create_rectangle(x0, y0, x1, y0 + canopy_h, fill="orange", outline="black")
                else:
                    # For other units, just the main Fascia panel
                    wall_th_scaled = self.parts['side_walls']['thickness'] * scale if sw_length > 0 else 0
                    fascia_x0 = x0 + wall_th_scaled
                    fascia_x1 = x1 - wall_th_scaled
                    self.canvas_front.create_rectangle(fascia_x0, y0, fascia_x1, y0 + canopy_h, fill="orange", outline="black")
            else: # Canopy or Solid Top
                self.canvas_front.create_rectangle(x0, y0, x1, y0 + canopy_h, fill="orange", outline="black")

        return canopy_h

    def _draw_front_base_and_deck(self, x0, x1, y1, base_thickness, deck_thickness, scale):
        """Draws the base and deck on the front canvas."""
        base_h = 0
        if base_thickness > 0:
            base_h = base_thickness * scale
            self.canvas_front.create_rectangle(x0, y1 - base_h, x1, y1, fill="brown", outline="black")  # Base

        deck_y = y1 - base_h  # Top of base, or bottom of unit if no base

        if deck_thickness > 0:
            deck_h = deck_thickness * scale
            self.canvas_front.create_rectangle(x0, deck_y - deck_h, x1, deck_y, fill="slategray", outline="black")  # Deck
        else:
            deck_h = 0
            
        return deck_y, deck_h

    def _draw_front_shelves(self, x_start, x_end, start_y, shelf_spacings, shelf_thickness, scale):
        """Draws shelves and spacing measurements on the front canvas."""
        current_y = start_y
        if not shelf_spacings:
            return current_y

        for sp in shelf_spacings:
            shelf_bottom = current_y - sp * scale
            shelf_top = shelf_bottom - (shelf_thickness * scale)
            self.canvas_front.create_rectangle(x_start, shelf_top, x_end, shelf_bottom, fill="tan", outline="black")
            gap_mid = (current_y + shelf_bottom) / 2
            self.canvas_front.create_text((x_start + x_end) / 2, gap_mid, text=self._format_measurement(sp), font=("Arial", 10), fill="black")
            current_y = shelf_top
        return current_y

    def _draw_ts_measurement(self, x0, y1, highest_shelf_top_y, base_thickness, deck_thickness, shelf_spacings, shelf_thickness):
        """Draws the 'Top of Shelf' (TS) measurement on the front canvas."""
        if shelf_spacings:
            ts_height = (base_thickness + deck_thickness) + sum(shelf_spacings) + (len(shelf_spacings) * shelf_thickness)
            ts_arrow_x = x0 - 70
            self.canvas_front.create_line(ts_arrow_x, y1, ts_arrow_x, highest_shelf_top_y, arrow=tk.BOTH, fill="black")
            self.canvas_front.create_text(ts_arrow_x - 5, (y1 + highest_shelf_top_y) / 2, text=f"TS {self._format_measurement(ts_height)}", font=("Arial", 10), anchor="e", fill="black")

    def _draw_gap_above_shelves(self, canvas, highest_shelf_top_y, upper_bound, scale, x_start, x_end, shelf_spacings):
        """Draws the measurement for the gap between the top shelf and the canopy."""
        if not shelf_spacings:
            return
            
        gap_above = (highest_shelf_top_y - upper_bound) / scale
        if gap_above > 0.1: # Threshold to avoid tiny labels
            mid_gap_y = (highest_shelf_top_y + upper_bound) / 2
            mid_gap_x = (x_start + x_end) / 2
            canvas.create_text(mid_gap_x, mid_gap_y, text=self._format_measurement(gap_above), font=("Arial", 10), fill="black")

    def _setup_top_canvas(self, width, depth):
        """Clears and sets up the top canvas with a base frame and measurement arrows."""
        self.canvas_top.delete("all")
        margin_top = 50  # Larger margin for better visibility
        ct_w, ct_h = self.canvas_top.winfo_width(), self.canvas_top.winfo_height()
        if ct_w <= 1 or ct_h <= 1: return 0, 0, 0, 0, 0, 0
        scale_top = min((ct_w - 2 * margin_top) / width, (ct_h - 2 * margin_top) / depth)
        
        # Center the drawing in the canvas
        drawing_width = width * scale_top
        drawing_height = depth * scale_top
        x0t = (ct_w - drawing_width) / 2
        y0t = (ct_h - drawing_height) / 2
        x1t = x0t + drawing_width
        y1t = y0t + drawing_height

        self.canvas_top.create_rectangle(x0t, y0t, x1t, y1t, outline="black", fill="slategray")
        # Width measurement (horizontal) - in viewport white space
        # Use red color if width is insufficient for wire shelves
        width_color = "red" if self._width_warning else "black"
        self.canvas_top.create_line(x0t, y0t - 20, x1t, y0t - 20, arrow=tk.BOTH, width=2, fill=width_color)
        self.canvas_top.create_text((x0t + x1t) / 2, y0t - 35, text=self._format_measurement(width), font=("Arial", 12), fill=width_color)
        # Depth measurement (vertical) - in viewport white space
        arrow_y = x0t - 20
        self.canvas_top.create_line(arrow_y, y0t, arrow_y, y1t, arrow=tk.BOTH, width=2)
        self.canvas_top.create_text(arrow_y - 10, (y0t + y1t) / 2, text=self._format_measurement(depth), font=("Arial", 12), anchor="e", fill="black")
        
        back_th = self.parts['back_panel']['thickness'] * scale_top
        self.canvas_top.create_rectangle(x0t, y0t, x1t, y0t + back_th, fill="lightgray", outline="black")
        return x0t, y0t, x1t, y1t, scale_top, back_th

    def _setup_side_canvas(self, depth, height):
        """Clears and sets up the side canvas with a base frame and measurement arrows."""
        self.canvas_side.delete("all")
        margin_side = 50  # Larger margin for better visibility
        cs_w, cs_h = self.canvas_side.winfo_width(), self.canvas_side.winfo_height()
        if cs_w <= 1 or cs_h <= 1: return 0, 0, 0, 0, 0, 0
        scale_side = min((cs_w - 2 * margin_side) / depth, (cs_h - 2 * margin_side) / height)
        
        # Center the drawing in the canvas
        drawing_width = depth * scale_side
        drawing_height = height * scale_side
        x0s = (cs_w - drawing_width) / 2
        y0s = (cs_h - drawing_height) / 2
        x1s = x0s + drawing_width
        y1s = y0s + drawing_height

        self.canvas_side.create_rectangle(x0s, y0s, x1s, y1s, outline="", fill="")

        # Back panel is now drawn in a dedicated function to handle canopy height
        back_th_side = self.parts['back_panel']['thickness'] * scale_side

        # Height measurement (vertical)
        arrow_x = x1s + 20
        self.canvas_side.create_line(arrow_x, y0s, arrow_x, y1s, arrow=tk.BOTH, width=2)
        self.canvas_side.create_text(arrow_x + 10, (y0s + y1s) / 2, text=self._format_measurement(height), font=("Arial", 12), anchor="w", fill="black")
        
        # Depth measurement (horizontal) - in viewport white space
        self.canvas_side.create_line(x0s, y0s - 20, x1s, y0s - 20, arrow=tk.BOTH, width=2)
        self.canvas_side.create_text((x0s + x1s) / 2, y0s - 35, text=self._format_measurement(depth), font=("Arial", 12), fill="black")
        return x0s, y0s, x1s, y1s, scale_side, back_th_side

    def _draw_top_side_walls(self, x0t, x1t, y0t, y1t, sw_length, scale_top, back_th, shelf_type="Fixed"):
        """Draws side walls on the top canvas, checking for overhang."""
        wall_th_top = self.parts['side_walls']['thickness'] * scale_top
        wall_y_start, wall_y_end = y0t + back_th, y0t + back_th + (sw_length * scale_top)
        overhang = wall_y_end > y1t

        for wall_x_start in [x0t, x1t - wall_th_top]:
            wall_x_end = wall_x_start + wall_th_top
            self.canvas_top.create_rectangle(wall_x_start, wall_y_start, wall_x_end, min(wall_y_end, y1t), fill="darkgray", outline="black")
            if overhang:
                self.canvas_top.create_rectangle(wall_x_start, y1t, wall_x_end, wall_y_end, fill="red", outline="red")

        self.sideWallSpin.config(foreground="red" if overhang else "black")
        self.canvas_top.create_text(x1t + 2 * scale_top, wall_y_start + (sw_length * scale_top) / 2, text=self._format_measurement(sw_length), font=("Arial", 10), anchor="w", fill="black")

        # Draw top-down line boring holes for Pins/Clips
        if shelf_type in ["Pins", "Clips"]:
            hole_dia = 0.25 * scale_top  # 1/4" hole
            front_hole_y = wall_y_start + (3 * scale_top)
            back_hole_y = wall_y_end - (3 * scale_top)
            
            for wall_x_start in [x0t, x1t - wall_th_top]:
                hole_x = wall_x_start + wall_th_top / 2
                if front_hole_y < min(wall_y_end, y1t):
                    self.canvas_top.create_oval(hole_x - hole_dia / 2, front_hole_y - hole_dia / 2, hole_x + hole_dia / 2, front_hole_y + hole_dia / 2, fill="black", outline="")
                if back_hole_y > wall_y_start and back_hole_y < min(wall_y_end, y1t):
                    self.canvas_top.create_oval(hole_x - hole_dia / 2, back_hole_y - hole_dia / 2, hole_x + hole_dia / 2, back_hole_y + hole_dia / 2, fill="black", outline="")

    def _draw_front_line_boring(self, x_pos, y_start, y_end, scale):
        """Draws vertical line boring holes in the front view."""
        hole_dia = 0.1 * scale
        y_spacing = 1.25 * scale
        current_y = y_start + (2 * scale)
        while current_y < y_end - (2 * scale):
            self.canvas_front.create_oval(x_pos - hole_dia / 2, current_y - hole_dia / 2, x_pos + hole_dia / 2, current_y + hole_dia / 2, fill="gray", outline="")
            current_y += y_spacing

    # -------------------- DRAWING FUNCTIONS --------------------
    def _draw_front_standards(self, x0, x1, scale, std_start_y, upper_bound):
        """Draws vertical standards in the front view."""
        std_height = 63 * scale  # Always 63" tall
        std1_x = x0 + (self.std_offset * scale)
        std2_x = x1 - (self.std_offset * scale)
        std_end_y = std_start_y - std_height

        # Draw standards, showing overflow in red
        std_visible_end = max(std_end_y, upper_bound)
        self.canvas_front.create_line(std1_x, std_start_y, std1_x, std_visible_end, fill="black", width=2)
        self.canvas_front.create_line(std2_x, std_start_y, std2_x, std_visible_end, fill="black", width=2)
        if std_end_y < upper_bound:
            self.canvas_front.create_line(std1_x, std_visible_end, std1_x, std_end_y, fill="red", width=2)
            self.canvas_front.create_line(std2_x, std_visible_end, std2_x, std_end_y, fill="red", width=2)

    def _draw_top_standards(self, x0t, x1t, y0t, scale_top, back_th):
        """Draws standards in the top-down view."""
        std_size = self.parts['standards']['thickness'] * scale_top
        std1_x = x0t + (self.std_offset * scale_top)
        std2_x = x1t - (self.std_offset * scale_top) - std_size
        std_y = y0t + back_th
        self.canvas_top.create_rectangle(std1_x, std_y, std1_x + std_size, std_y + std_size, fill="black")
        self.canvas_top.create_rectangle(std2_x, std_y, std2_x + std_size, std_y + std_size, fill="black")

    def _draw_side_canopy(self, x0s, y0s, x1s, top_thickness, scale_side, top_option):
        """Draws the canopy or fascia on the side canvas if applicable."""
        canopy_h = 0
        if top_thickness > 0:
            canopy_h = top_thickness * scale_side
            if top_option == "Fascia":
                if self.unitTypeVar.get() == "Endcap":
                    # For Endcap units, only draw Fascia Front (full width, no side piece visible in side view)
                    self.canvas_side.create_rectangle(x0s, y0s, x1s, y0s + canopy_h, fill="orange", outline="black")  # Fascia Front
                else:
                    # For other units, just the main Fascia panel
                    fascia_width_scaled = 0.75 * scale_side
                    fascia_x0 = x1s - fascia_width_scaled
                    self.canvas_side.create_rectangle(fascia_x0, y0s, x1s, y0s + canopy_h, fill="orange", outline="black")
            else: # Canopy or Solid Top
                self.canvas_side.create_rectangle(x0s, y0s, x1s, y0s + canopy_h, fill="orange", outline="black")
        return canopy_h

    def _draw_side_base_and_deck(self, x0s, x1s, y1s, base_thickness, deck_thickness, scale_side, back_th_side):
        """Draws the base and deck on the side canvas."""
        base_h = 0
        if base_thickness > 0:
            base_h = base_thickness * scale_side
            self.canvas_side.create_rectangle(x0s + back_th_side, y1s - base_h, x1s, y1s, fill="brown", outline="black")  # Base starts after back panel

        deck_y = y1s - base_h
        
        if deck_thickness > 0:
            deck_h = deck_thickness * scale_side
            self.canvas_side.create_rectangle(x0s + back_th_side, deck_y - deck_h, x1s, deck_y, fill="slategray", outline="black")  # Deck as well
        else:
            deck_h = 0
            
        return deck_y, deck_h

    def _draw_side_shelves(self, x_start, x_end, start_y, shelf_spacings, shelf_thickness, scale_side):
        """Draws shelves and spacing measurements on the side canvas."""
        current_y = start_y
        if not shelf_spacings:
            return current_y

        for sp in shelf_spacings:
            shelf_bottom = current_y - sp * scale_side
            shelf_top = shelf_bottom - (shelf_thickness * scale_side)
            self.canvas_side.create_rectangle(x_start, shelf_top, x_end, shelf_bottom, fill="tan", outline="black")
            gap_mid = (current_y + shelf_bottom) / 2
            self.canvas_side.create_text((x_start + x_end) / 2, gap_mid, text=self._format_measurement(sp), font=("Arial", 10))
            current_y = shelf_top
        return current_y

    def _draw_side_side_walls(self, x0s, y0s, scale_side, shelf_type, sw_length, canopy_h, deck_y, deck_h, back_th_side, unit_depth, shelf_y_coords, shelf_material):
        """Draws side walls in the side view - shows the side wall profile."""
        wall_y_top = y0s + canopy_h if self.top_var.get() != "Fascia" else y0s
        wall_y_bottom = deck_y - deck_h
        
        side_wall_end_x = x0s + back_th_side + (sw_length * scale_side)
        top_option = self.top_var.get()

        if self.top_var.get() == "Fascia" and sw_length < unit_depth - self.parts['back_panel']['thickness']:
            # Draw a single polygon for the unified L-shape
            fascia_front_x = x0s + (unit_depth * scale_side)
            fascia_bottom_y = wall_y_top + (8 * scale_side) # Fascia is 8" tall
            radius = 2 * scale_side

            # Start building the points for the polygon
            points = [
                # Top-left corner of the side wall (at the back)
                x0s + back_th_side, wall_y_top,
                # Top-right corner of the fascia support (at the front)
                fascia_front_x, wall_y_top,
                # Bottom-right corner of the fascia support
                fascia_front_x, fascia_bottom_y,
                # Point on the bottom edge of fascia support where the inner curve begins
                side_wall_end_x + radius, fascia_bottom_y,
            ]

            # Calculate points for the inner radius arc
            # Center of the circle for the arc
            cx = side_wall_end_x + radius
            cy = fascia_bottom_y + radius
            
            # Generate arc points from 270 degrees down to 180 degrees
            # to trace the curve in the correct direction for the polygon
            for i in range(270, 179, -5):
                angle = math.radians(i)
                arc_x = cx + radius * math.cos(angle)
                arc_y = cy + radius * math.sin(angle)
                points.append((arc_x, arc_y))

            # Add the remaining points to close the polygon
            points.extend([
                # Bottom of the side wall (at the front)
                side_wall_end_x, wall_y_bottom,
                # Bottom-left of the side wall (at the back)
                x0s + back_th_side, wall_y_bottom,
            ])
            
            # Draw the final shape
            self.canvas_side.create_polygon(points, outline="black", width=2, fill="lightgray", stipple="gray25")
        else:
            if top_option == "No Top":
                radius = 2 * scale_side
                num_segments = 10
                
                # Polygon for wall with rounded top-front corner
                points = [
                    x0s + back_th_side, wall_y_bottom, # bottom-back
                    x0s + back_th_side, wall_y_top,    # top-back
                    side_wall_end_x - radius, wall_y_top, # top-front before curve
                ]
                
                # Arc for top-front corner (top-right on canvas)
                cx, cy = side_wall_end_x - radius, wall_y_top + radius
                for i in range(num_segments + 1):
                    angle = math.radians(270 + 90 * (i / num_segments))
                    points.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
                
                points.append(side_wall_end_x)
                points.append(wall_y_bottom) # bottom-front
                self.canvas_side.create_polygon(points, outline="black", width=2, fill="lightgray", stipple="gray25")

            else:
                # Standard rectangular wall
                self.canvas_side.create_rectangle(x0s + back_th_side, wall_y_top, side_wall_end_x, wall_y_bottom, outline="black", width=2, fill="lightgray", stipple="gray25")
        
        # Draw line boring holes for Pins/Clips (vertical holes in the side wall)
        if shelf_type in ["Pins", "Clips"]:
            hole_dia = 0.25 * scale_side  # 1/4" hole
            
            # Holes are typically inset 3" from the front and back edges of the wall
            back_hole_x = x0s + back_th_side + (3 * scale_side)
            front_hole_x = side_wall_end_x - (3 * scale_side)

            # Only draw holes if the wall is wide enough
            if front_hole_x > back_hole_x:
                y_spacing = 1.25 * scale_side
                current_y = wall_y_top + (2 * scale_side) # Start holes 2" from the top
                
                while current_y < wall_y_bottom - (2 * scale_side):
                    # Back holes
                    self.canvas_side.create_oval(back_hole_x - hole_dia / 2, current_y - hole_dia / 2, 
                                               back_hole_x + hole_dia / 2, current_y + hole_dia / 2, 
                                               fill="black", outline="")
                    # Front holes
                    self.canvas_side.create_oval(front_hole_x - hole_dia / 2, current_y - hole_dia / 2, 
                                               front_hole_x + hole_dia / 2, current_y + hole_dia / 2, 
                                               fill="black", outline="")
                    current_y += y_spacing

        # Draw dowel holes for fixed shelves, ignoring material type
        if shelf_type == "Fixed":
            self._draw_side_shelf_dowels(shelf_y_coords, x0s, side_wall_end_x, back_th_side, scale_side, shelf_type)

    def _draw_side_standards(self, x0s, scale_side, std_start_y, upper_bound):
        """Draws a standard in the side view."""
        std_height = 63 * scale_side  # 63" tall
        std_depth = self.parts['standards']['thickness'] * scale_side  # 1" deep
        std_x = x0s  # At the back
        std_end_y = std_start_y - std_height

        # Draw standard, showing overflow in red
        std_visible_end = max(std_end_y, upper_bound)
        self.canvas_side.create_rectangle(std_x, std_visible_end, std_x + std_depth, std_start_y, fill="black")

        if std_end_y < upper_bound:
            self.canvas_side.create_rectangle(std_x, std_end_y, std_x + std_depth, std_visible_end, fill="red")

    def _draw_front_side_walls(self, x0, y0, x1, scale, sw_length, canopy_h, deck_y, deck_h, shelf_type, shelf_y_coords):
        """Draws side walls in the front view."""
        wall_th_scaled = self.parts['side_walls']['thickness'] * scale
        wall_bottom = deck_y - deck_h
        wall_top = y0 + canopy_h if self.top_var.get() != "Fascia" else y0

        # Draw simple rectangular side walls without curved portions
        self.canvas_front.create_rectangle(x0, wall_top, x0 + wall_th_scaled, wall_bottom, fill="darkgray", outline="black")
        self.canvas_front.create_rectangle(x1 - wall_th_scaled, wall_top, x1, wall_bottom, fill="darkgray", outline="black")

        if shelf_type in ["Pins", "Clips"]:
            self._draw_front_line_boring(x0 + wall_th_scaled - (2 * scale / 16), wall_top, wall_bottom, scale)
            self._draw_front_line_boring(x1 - wall_th_scaled + (2 * scale / 16), wall_top, wall_bottom, scale)


    def _draw_side_shelf_dowels(self, shelf_y_coords, x0s, side_wall_end_x, back_th_side, scale_side, shelf_type):
        """Draws dowel and pinholes for fixed shelves in the side view."""
        if not shelf_y_coords or shelf_type != "Fixed":
            return

        # Corrected hole sizing using mm_to_in conversion
        hole_size = max(3, self.mm_to_in(6) * scale_side)
        screw_size = max(2, self.mm_to_in(3) * scale_side)
        pinhole_size = max(2, self.mm_to_in(2) * scale_side)
        
        # Corrected positioning using mm_to_in conversion
        inset = self.mm_to_in(50) * scale_side
        back_x = x0s + back_th_side + inset
        front_x = side_wall_end_x - inset
        center_x = (back_x + front_x) / 2
        
        # Check if there's enough space
        if front_x <= back_x:
            return

        # Draw holes for each shelf
        for y_center in shelf_y_coords:
            # Back dowel hole
            self.canvas_side.create_oval(
                back_x - hole_size/2, y_center - hole_size/2,
                back_x + hole_size/2, y_center + hole_size/2,
                outline="black", width=2, fill="white"
            )
            # Back screw hole
            self.canvas_side.create_oval(
                back_x - screw_size/2, y_center - screw_size/2,
                back_x + screw_size/2, y_center + screw_size/2,
                outline="black", width=1, fill="black"
            )
            
            # Front dowel hole
            self.canvas_side.create_oval(
                front_x - hole_size/2, y_center - hole_size/2,
                front_x + hole_size/2, y_center + hole_size/2,
                outline="black", width=2, fill="white"
            )
            # Front screw hole
            self.canvas_side.create_oval(
                front_x - screw_size/2, y_center - screw_size/2,
                front_x + screw_size/2, y_center + screw_size/2,
                outline="black", width=1, fill="black"
            )
            
            # Center pinhole
            self.canvas_side.create_oval(
                center_x - pinhole_size/2, y_center - pinhole_size/2,
                center_x + pinhole_size/2, y_center + pinhole_size/2,
                outline="black", width=1, fill="white"
            )


    def _format_spinbox_value(self, var):
        if self._is_formatting:
            return
        self._is_formatting = True
        try:
            value = float(var.get())
            # Format to 3 decimal places if needed, otherwise 2
            if abs(value - float(f"{value:.2f}")) < 1e-9:
                formatted_value = f"{value:.2f}"
            else:
                formatted_value = f"{value:.3f}"
            
            if var.get() != formatted_value:
                var.set(formatted_value)
        except (ValueError, tk.TclError):
            # Ignore if the value is not a valid float (e.g., during typing)
            pass
        finally:
            self._is_formatting = False

    def _draw_side_back_panel(self, x0s, y0s, y1s, scale_side, canopy_h):
        """Draws the back panel in the side view, accounting for canopy."""
        back_th_side = self.parts['back_panel']['thickness'] * scale_side
        wall_top_y = y0s + canopy_h if self.top_var.get() != "Fascia" else y0s
        self.canvas_side.create_rectangle(x0s, wall_top_y, x0s + back_th_side, y1s, fill="lightgray", outline="black")

    def _draw_top_shelves(self, x0t, y0t, x1t, y1t, scale_top, sw_length, back_th, shelf_spacings, shelf_type, unit_depth, shelf_material):
        """Draws a transparent representation of shelves in the top view."""
        if not shelf_spacings:
            return

        wall_th_top = self.parts['side_walls']['thickness'] * scale_top if sw_length > 0 else 0
        three_mm_in_inches = 0.11811

        if shelf_type == "Standard & Brackets":
            std_offset = self.std_offset * scale_top
            std_thickness = self.parts['standards']['thickness'] * scale_top
            bracket_clearance = three_mm_in_inches * scale_top
            shelf_x0 = x0t + std_offset + std_thickness + bracket_clearance
            shelf_x1 = x1t - (std_offset + std_thickness + bracket_clearance)
        else:
            shelf_x0 = x0t + wall_th_top
            shelf_x1 = x1t - wall_th_top
            if shelf_material == "Melamine" and shelf_type in ["Pins", "Clips"]:
                side_offset = three_mm_in_inches * scale_top
                shelf_x0 += side_offset
                shelf_x1 -= side_offset
        
        # Depth calculation
        back_panel_thickness_inches = self.parts['back_panel']['thickness']
        standard_thickness_inches = self.parts['standards']['thickness'] if shelf_type == "Standard & Brackets" else 0
        
        shelf_depth_inches = unit_depth - back_panel_thickness_inches - standard_thickness_inches - three_mm_in_inches
        shelf_depth_scaled = shelf_depth_inches * scale_top
        
        standard_thickness_scaled = standard_thickness_inches * scale_top
        shelf_y0 = y0t + back_th + standard_thickness_scaled
        shelf_y1 = shelf_y0 + shelf_depth_scaled

        should_be_rounded = False
        if shelf_material == "Melamine":
            # Condition: side walls do not fully cover the shelf edge, accounting for standard offset
            effective_shelf_depth = shelf_depth_inches + standard_thickness_inches
            if sw_length < effective_shelf_depth:
                should_be_rounded = True

        if should_be_rounded:
            radius = 1 * scale_top
            points = [
                shelf_x0, shelf_y0,
                shelf_x1, shelf_y0,
                shelf_x1, shelf_y1 - radius
            ]
            
            # Front-right (bottom-right on canvas) arc
            cx1, cy1 = shelf_x1 - radius, shelf_y1 - radius
            for i in range(0, 91, 5):
                angle = math.radians(i)
                points.extend((cx1 + radius * math.cos(angle), cy1 + radius * math.sin(angle)))

            # Front-left (bottom-left on canvas) arc
            cx2, cy2 = shelf_x0 + radius, shelf_y1 - radius
            for i in range(90, 181, 5):
                angle = math.radians(i)
                points.extend((cx2 + radius * math.cos(angle), cy2 + radius * math.sin(angle)))

            self.canvas_top.create_polygon(points, outline="black", fill="lightgray", stipple="gray50")
        else:
            self.canvas_top.create_rectangle(shelf_x0, shelf_y0, shelf_x1, shelf_y1, outline="black", fill="lightgray", stipple="gray50")

    def draw_endcap(self, width, depth, height, top_thickness, base_thickness,
                    col_width, col_depth, shelf_thickness, shelf_spacings, x_positions, front_dist, shelf_type, column_height, shelf_material):
        # FRONT VIEW for Endcap
        x0, y0, x1, y1, scale = self._setup_front_canvas(width, height)
        if not all([x0, y0, x1, y1, scale]): return # Skip if canvas not ready

        canopy_h = self._draw_front_canopy(x0, y0, x1, top_thickness, scale, self.top_var.get(), self.sideWallLengthVar.get())
        deck_y, deck_h = self._draw_front_base_and_deck(x0, x1, y1, base_thickness, self.deck_thickness, scale)

        # Column positioning - from deck to bottom of canopy
        col_w_scaled = col_width * scale
        col_x0 = x0 + ((x1 - x0) - col_w_scaled) / 2
        col_x1 = col_x0 + col_w_scaled
        col_bottom = deck_y - deck_h
        col_top = col_bottom - (column_height * scale)
        self.canvas_front.create_rectangle(col_x0, col_top, col_x1, col_bottom, outline="black", fill="lightsteelblue", width=1)

        # Poles
        pole_dia = 1.5 * scale
        pole_bottom = deck_y - deck_h
        for xp in x_positions:
            px = x0 + xp * scale
            self.canvas_front.create_rectangle(px - pole_dia / 2, y0 + canopy_h, px + pole_dia / 2, pole_bottom, outline="black", fill="dimgray")

        # Start shelves from deck level (no base panel for Endcap)
        shelf_start_y = deck_y - deck_h
        highest_shelf_top_y = self._draw_front_shelves(x0, x1, shelf_start_y, shelf_spacings, shelf_thickness, scale)
        self._draw_ts_measurement(x0, y1, highest_shelf_top_y, base_thickness, self.deck_thickness, shelf_spacings, shelf_thickness)
        upper_bound = y0 + canopy_h
        self._draw_gap_above_shelves(self.canvas_front, highest_shelf_top_y, upper_bound, scale, x0, x1, shelf_spacings)

        if shelf_type == "Standard & Brackets":
            std_start_y = deck_y - deck_h
            upper_bound = y0 + canopy_h
            self._draw_front_standards(x0, x1, scale, std_start_y, upper_bound)

        # TOP VIEW for Endcap
        x0t, y0t, x1t, y1t, scale_top, back_th = self._setup_top_canvas(width, depth)
        if not all([x0t, y0t, x1t, y1t, scale_top, back_th is not None]): return

        # Draw canopy supports if canopy exists
        if self.top_var.get() == "Canopy":
            self._draw_top_canopy_supports(x0t, y0t, y1t, scale_top, x_positions, back_th)
        # Draw fascia supports if fascia exists (for Endcap units)
        elif self.top_var.get() == "Fascia" and self.unitTypeVar.get() == "Endcap":
            self._draw_top_fascia_supports(x0t, y0t, y1t, scale_top, x_positions, back_th)

        # Endcaps don't have side walls in the same way as bookcases. sw_length should be 0.
        sw_length = 0 
        self._draw_top_shelves(x0t, y0t, x1t, y1t, scale_top, sw_length, back_th, shelf_spacings, shelf_type, depth, shelf_material)

        # Draw column in top view (3-piece construction: 2 sides + 1 front)
        col_w_top = col_width * scale_top
        col_d_top = col_depth * scale_top
        col_x0_top = x0t + ((x1t - x0t) - col_w_top) / 2
        col_x1_top = col_x0_top + col_w_top
        col_y0_top = y0t + back_th  # Start after back panel
        col_y1_top = col_y0_top + col_d_top
        
        side_thickness_scaled = 0.75 * scale_top
        # Left Side
        self.canvas_top.create_rectangle(col_x0_top, col_y0_top, col_x0_top + side_thickness_scaled, col_y1_top, outline="black", fill="lightsteelblue", width=1)
        # Right Side
        self.canvas_top.create_rectangle(col_x1_top - side_thickness_scaled, col_y0_top, col_x1_top, col_y1_top, outline="black", fill="lightsteelblue", width=1)
        # Front
        self.canvas_top.create_rectangle(col_x0_top, col_y1_top - side_thickness_scaled, col_x1_top, col_y1_top, outline="black", fill="lightsteelblue", width=1)

        # Column measurement labels
        col_center_x_top = (col_x0_top + col_x1_top) / 2
        col_center_y_top = (col_y0_top + col_y1_top) / 2
        self.canvas_top.create_text(col_center_x_top, col_y1_top + 8, text=self._format_measurement(col_width), font=("Arial", 10), fill="blue")
        self.canvas_top.create_text(col_x1_top + 15, col_center_y_top, text=self._format_measurement(col_depth), font=("Arial", 10), fill="blue")

        # Draw poles as ovals in top view.
        pole_dia_top = 1.5 * scale_top
        py_top = y1t - self.pole_front_distance(depth) * scale_top
        for xp in x_positions:
            px_top = x0t + xp * scale_top
            self.canvas_top.create_oval(px_top - pole_dia_top / 2, py_top - pole_dia_top / 2, px_top + pole_dia_top / 2, py_top + pole_dia_top / 2, outline="black", fill="dimgray")

        # Draw pole spacing labels
        if x_positions:
            # Front spacing labels for each pole
            label_y = (py_top + y1t) / 2
            for xp in x_positions:
                px_top = x0t + xp * scale_top
                self.canvas_top.create_text(px_top, label_y, text=self._format_measurement(front_dist), font=("Arial", 10), fill="black")

            # Side spacing labels
            first_pole_x = x0t + x_positions[0] * scale_top
            self.canvas_top.create_text((x0t + first_pole_x) / 2, py_top, text=self._format_measurement(x_positions[0]), font=("Arial", 10), fill="black")
            
            last_pole_x = x0t + x_positions[-1] * scale_top
            self.canvas_top.create_text((last_pole_x + x1t) / 2, py_top, text=self._format_measurement(width - x_positions[-1]), font=("Arial", 10), fill="black")

        if shelf_type == "Standard & Brackets":
            self._draw_top_standards(x0t, x1t, y0t, scale_top, back_th)

        # SIDE VIEW for Endcap
        if self.side_view_var.get():
            x0s, y0s, x1s, y1s, scale_side, back_th_side = self._setup_side_canvas(depth, height)
            if not all([x0s, y0s, x1s, y1s, scale_side, back_th_side is not None]): return

            canopy_h = self._draw_side_canopy(x0s, y0s, x1s, top_thickness, scale_side, self.top_var.get())
            deck_y, deck_h = self._draw_side_base_and_deck(x0s, x1s, y1s, base_thickness, self.deck_thickness, scale_side, back_th_side)

            # Draw column in side view (showing column depth)
            col_d_side = col_depth * scale_side
            col_x0_side = x0s + back_th_side
            col_x1_side = col_x0_side + col_d_side
            col_bottom_side = deck_y - deck_h
            col_top_side = col_bottom_side - (column_height * scale_side)
            self.canvas_side.create_rectangle(col_x0_side, col_top_side, col_x1_side, col_bottom_side, outline="black", fill="lightsteelblue", width=1)

            # Draw poles in side view (showing pole depth from front)
            pole_dia_side = 1.5 * scale_side
            pole_depth = front_dist * scale_side
            pole_bottom_side = deck_y - deck_h
            px_side = x1s - pole_depth
            self.canvas_side.create_rectangle(px_side - pole_dia_side / 2, y0s + canopy_h, 
                                            px_side + pole_dia_side / 2, pole_bottom_side, 
                                            outline="black", fill="dimgray")

            # Draw shelves in side view (showing shelf depth)
            shelf_start_y_side = deck_y - deck_h
            highest_shelf_top_y_side = self._draw_side_shelves(x0s, x1s, shelf_start_y_side, shelf_spacings, shelf_thickness, scale_side)
            upper_bound_side = y0s + canopy_h
            self._draw_gap_above_shelves(self.canvas_side, highest_shelf_top_y_side, upper_bound_side, scale_side, x0s, x1s, shelf_spacings)

            if shelf_type == "Standard & Brackets":
                std_start_y = deck_y - deck_h
                upper_bound = y0s + canopy_h
                self._draw_side_standards(x0s, scale_side, std_start_y, upper_bound)

            self._draw_side_back_panel(x0s, y0s, y1s, scale_side, canopy_h)

    def draw_bookcase(self, width, depth, height, top_thickness, base_thickness,
                      shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material):
        # FRONT VIEW for Bookcase
        x0, y0, x1, y1, scale = self._setup_front_canvas(width, height)
        if not all([x0, y0, x1, y1, scale]): return
        canopy_h = self._draw_front_canopy(x0, y0, x1, top_thickness, scale, self.top_var.get(), sw_length)
        deck_y, deck_h = self._draw_front_base_and_deck(x0, x1, y1, base_thickness, self.deck_thickness, scale)

        # Determine shelf start position and draw base panel
        shelf_start_y = deck_y - deck_h
        panel_top = 0 
        if panel_is_required:
            base_panel_h = self.parts['base_panel']['thickness'] * scale
            panel_y = deck_y - deck_h # Sits on deck
            panel_top = panel_y - base_panel_h
            self.canvas_front.create_rectangle(x0, panel_top, x1, panel_y, fill="lightblue")
            shelf_start_y = panel_top

        # Side walls define the interior space for shelves
        wall_th_scaled = self.parts['side_walls']['thickness'] * scale if sw_length > 0 else 0
        interior_x0 = x0 + wall_th_scaled
        interior_x1 = x1 - wall_th_scaled
        shelf_x0, shelf_x1 = interior_x0, interior_x1

        if shelf_type == "Standard & Brackets":
            std_offset = self.std_offset * scale
            std_thickness = self.parts['standards']['thickness'] * scale
            bracket_clearance = 0.25 * scale
            shelf_x0 = x0 + std_offset + std_thickness + bracket_clearance
            shelf_x1 = x1 - std_offset - std_thickness - bracket_clearance
        elif sw_length > 0:
            if shelf_type in ["Pins", "Clips"]:
                gap = 0.125 * scale
                shelf_x0 += gap
                shelf_x1 -= gap
            elif shelf_type == "Fixed":
                gap = 0.0625 * scale
                shelf_x0 += gap
                shelf_x1 -= gap

        # Start shelves from deck level, inside the walls
        shelf_start_y = deck_y - deck_h
        highest_shelf_top_y = self._draw_front_shelves(shelf_x0, shelf_x1, shelf_start_y, shelf_spacings, shelf_thickness, scale)
        self._draw_ts_measurement(x0, y1, highest_shelf_top_y, base_thickness, self.deck_thickness, shelf_spacings, shelf_thickness)
        upper_bound = y0 + canopy_h
        self._draw_gap_above_shelves(self.canvas_front, highest_shelf_top_y, upper_bound, scale, shelf_x0, shelf_x1, shelf_spacings)

        # Draw side walls - sit on deck, not ground
        if sw_length > 0:
            shelf_y_coords_front = self._calculate_shelf_y_positions(shelf_start_y, shelf_spacings, shelf_thickness, scale)
            self._draw_front_side_walls(x0, y0, x1, scale, sw_length, canopy_h, deck_y, deck_h, shelf_type, shelf_y_coords_front)

        if shelf_type == "Standard & Brackets":
            std_start_y = deck_y - deck_h
            upper_bound = y0 + canopy_h
            self._draw_front_standards(x0, x1, scale, std_start_y, upper_bound)

        # TOP VIEW for Bookcase
        x0t, y0t, x1t, y1t, scale_top, back_th = self._setup_top_canvas(width, depth)
        if not all([x0t, y0t, x1t, y1t, scale_top, back_th is not None]): return

        self._draw_top_shelves(x0t, y0t, x1t, y1t, scale_top, sw_length, back_th, shelf_spacings, shelf_type, depth, shelf_material)

        if sw_length > 0:
            self._draw_top_side_walls(x0t, x1t, y0t, y1t, sw_length, scale_top, back_th, shelf_type)

        if shelf_type == "Standard & Brackets":
            self._draw_top_standards(x0t, x1t, y0t, scale_top, back_th)

        # SIDE VIEW for Bookcase
        if self.side_view_var.get():
            x0s, y0s, x1s, y1s, scale_side, back_th_side = self._setup_side_canvas(depth, height)
            if not all([x0s, y0s, x1s, y1s, scale_side, back_th_side is not None]): return
            canopy_h = self._draw_side_canopy(x0s, y0s, x1s, top_thickness, scale_side, self.top_var.get())
            deck_y, deck_h = self._draw_side_base_and_deck(x0s, x1s, y1s, base_thickness, self.deck_thickness, scale_side, back_th_side)

            # Draw shelves in side view (showing shelf depth)
            shelf_start_y_side = deck_y - deck_h
            highest_shelf_top_y_side = self._draw_side_shelves(x0s, x1s, shelf_start_y_side, shelf_spacings, shelf_thickness, scale_side)
            upper_bound_side = y0s + canopy_h
            self._draw_gap_above_shelves(self.canvas_side, highest_shelf_top_y_side, upper_bound_side, scale_side, x0s, x1s, shelf_spacings)

            # Draw side walls in side view (showing wall thickness along depth)
            if sw_length > 0:
                shelf_y_coords_side = self._calculate_shelf_y_positions(deck_y - deck_h, shelf_spacings, shelf_thickness, scale_side)
                self._draw_side_side_walls(x0s, y0s, scale_side, shelf_type, sw_length, canopy_h, deck_y, deck_h, back_th_side, depth, shelf_y_coords_side, shelf_material)

            if shelf_type == "Standard & Brackets":
                std_start_y = deck_y - deck_h
                upper_bound = y0s + canopy_h
                self._draw_side_standards(x0s, scale_side, std_start_y, upper_bound)

            self._draw_side_back_panel(x0s, y0s, y1s, scale_side, canopy_h)

    def draw_slice_rack(self, width, depth, height, top_thickness, base_thickness,
                        shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material):
        # FRONT VIEW for Slice Rack
        x0, y0, x1, y1, scale = self._setup_front_canvas(width, height)
        if not all([x0, y0, x1, y1, scale]): return
        canopy_h = self._draw_front_canopy(x0, y0, x1, top_thickness, scale, self.top_var.get(), sw_length)
        deck_y, deck_h = self._draw_front_base_and_deck(x0, x1, y1, base_thickness, self.deck_thickness, scale)

        # Determine shelf start position and draw base panel
        shelf_start_y = deck_y - deck_h
        panel_top = 0
        if panel_is_required:
            base_panel_h = self.parts['base_panel']['thickness'] * scale
            panel_y = deck_y - deck_h # Sits on deck
            panel_top = panel_y - base_panel_h
            self.canvas_front.create_rectangle(x0, panel_top, x1, panel_y, fill="lightblue")
            shelf_start_y = panel_top

        # Draw shelves inside the side walls.
        wall_th_scaled = self.parts['side_walls']['thickness'] * scale if sw_length > 0 else 0
        interior_x0 = x0 + wall_th_scaled
        interior_x1 = x1 - wall_th_scaled
        shelf_x0, shelf_x1 = interior_x0, interior_x1

        if shelf_type == "Standard & Brackets":
            std_offset = self.std_offset * scale
            std_thickness = self.parts['standards']['thickness'] * scale
            bracket_clearance = 0.25 * scale
            shelf_x0 = x0 + std_offset + std_thickness + bracket_clearance
            shelf_x1 = x1 - std_offset - std_thickness - bracket_clearance
        elif sw_length > 0:
            if shelf_type in ["Pins", "Clips"]:
                gap = 0.125 * scale
                shelf_x0 += gap
                shelf_x1 -= gap
            elif shelf_type == "Fixed":
                gap = 0.0625 * scale
                shelf_x0 += gap
                shelf_x1 -= gap
        highest_shelf_top_y = self._draw_front_shelves(shelf_x0, shelf_x1, shelf_start_y, shelf_spacings, shelf_thickness, scale)
        self._draw_ts_measurement(x0, y1, highest_shelf_top_y, base_thickness, self.deck_thickness, shelf_spacings, shelf_thickness)

        # Gap above shelves
        upper_bound = y0 + canopy_h
        self._draw_gap_above_shelves(self.canvas_front, highest_shelf_top_y, upper_bound, scale, shelf_x0, shelf_x1, shelf_spacings)

        # Draw side walls - sit on deck, not ground
        if sw_length > 0:
            shelf_y_coords_front = self._calculate_shelf_y_positions(shelf_start_y, shelf_spacings, shelf_thickness, scale)
            self._draw_front_side_walls(x0, y0, x1, scale, sw_length, canopy_h, deck_y, deck_h, shelf_type, shelf_y_coords_front)

        if shelf_type == "Standard & Brackets":
            std_start = panel_top if base_thickness > 0 else y1
            upper_bound = y0 + canopy_h
            self._draw_front_standards(x0, x1, scale, std_start, upper_bound)

        # TOP VIEW for Slice Rack
        x0t, y0t, x1t, y1t, scale_top, back_th = self._setup_top_canvas(width, depth)
        if not all([x0t, y0t, x1t, y1t, scale_top, back_th is not None]): return

        self._draw_top_shelves(x0t, y0t, x1t, y1t, scale_top, sw_length, back_th, shelf_spacings, shelf_type, depth, shelf_material)

        if sw_length > 0:
            self._draw_top_side_walls(x0t, x1t, y0t, y1t, sw_length, scale_top, back_th, shelf_type)

        if shelf_type == "Standard & Brackets":
            self._draw_top_standards(x0t, x1t, y0t, scale_top, back_th)

        # SIDE VIEW for Slice Rack
        if self.side_view_var.get():
            x0s, y0s, x1s, y1s, scale_side, back_th_side = self._setup_side_canvas(depth, height)
            if not all([x0s, y0s, x1s, y1s, scale_side, back_th_side is not None]): return
            canopy_h = self._draw_side_canopy(x0s, y0s, x1s, top_thickness, scale_side, self.top_var.get())
            deck_y, deck_h = self._draw_side_base_and_deck(x0s, x1s, y1s, base_thickness, self.deck_thickness, scale_side, back_th_side)
            shelf_start_y_side = deck_y - deck_h

            # Draw base panel in side view (showing panel depth)
            panel_top = y1s 
            if panel_is_required:
                base_panel_h = self.parts['base_panel']['thickness'] * scale_side
                panel_y = deck_y - deck_h
                panel_top = panel_y - base_panel_h
                self.canvas_side.create_rectangle(x0s, panel_top, x0s + back_th_side, panel_y, fill="lightblue")

            # Draw shelves in side view (showing shelf depth)
            highest_shelf_top_y_side = self._draw_side_shelves(x0s, x1s, shelf_start_y_side, shelf_spacings, shelf_thickness, scale_side)
            upper_bound_side = y0s + canopy_h
            self._draw_gap_above_shelves(self.canvas_side, highest_shelf_top_y_side, upper_bound_side, scale_side, x0s, x1s, shelf_spacings)

            # Draw side walls in side view (showing wall thickness along depth)
            if sw_length > 0:
                shelf_y_coords_side = self._calculate_shelf_y_positions(shelf_start_y_side, shelf_spacings, shelf_thickness, scale_side)
                self._draw_side_side_walls(x0s, y0s, scale_side, shelf_type, sw_length, canopy_h, deck_y, deck_h, back_th_side, depth, shelf_y_coords_side, shelf_material)

            if shelf_type == "Standard & Brackets":
                std_start_y = deck_y - deck_h
                upper_bound = y0s + canopy_h
                self._draw_side_standards(x0s, scale_side, std_start_y, upper_bound)

            self._draw_side_back_panel(x0s, y0s, y1s, scale_side, canopy_h)

    def draw_bunker(self, width, depth, height, top_thickness, base_thickness,
                      shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material):
        # Bunker drawing is very similar to Bookcase
        self.draw_bookcase(width, depth, height, top_thickness, base_thickness,
                           shelf_thickness, shelf_spacings, sw_length, shelf_type, panel_is_required, shelf_material)

    def _add_shelf_spacing_entry(self, value=0.0):
        """Adds a new shelf spacing entry widget."""
        frame = ttk.Frame(self.manualShelfEntriesFrame)
        var = tk.DoubleVar(value=value)
        entry = ttk.Spinbox(frame, from_=0, to=100, increment=0.25, textvariable=var, width=5, format="%.2f")
        entry.pack(side=tk.LEFT, padx=2)
        var.trace_add("write", self.calculate_values)
        
        entry_data = {'frame': frame, 'var': var, 'entry': entry}
        self.manualShelfEntries.append(entry_data)
        frame.pack(side=tk.LEFT)

    def on_shelf_count_change(self, *args):
        try:
            new_count = self.numShelvesVar.get()
        except tk.TclError:
            new_count = 0 

        current_count = len(self.manualShelfEntries)

        # Add or remove entries to match the new count
        while current_count < new_count:
            self._add_shelf_spacing_entry()
            current_count += 1
        while current_count > new_count:
            entry_data = self.manualShelfEntries.pop()
            entry_data['frame'].destroy()
            current_count -= 1

        if self._loading_settings:
            return

        # Recalculate and update all entry boxes with even spacing
        if new_count > 0:
            try:
                total_height = self.height_var.get()
                top_option = self.top_var.get()
                if top_option in ["Canopy", "Fascia"]:
                    top_thickness = 8
                elif top_option == "Solid Top":
                    top_thickness = 0.75
                else:
                    top_thickness = 0
                base_thickness = self.base_thickness if self.base_var.get() == "Base" else 0
                deck_thickness = self.deck_thickness if self.base_var.get() == "Base" else 0
                shelf_material = self.shelfMaterialVar.get()
                shelf_thickness = 0.25 if shelf_material == "Wire" else self.shelf_thickness
                unit_type = self.unitTypeVar.get()

                interior_h = total_height - top_thickness - base_thickness - deck_thickness

                if unit_type == "Slice Rack" and base_thickness > 0:
                    interior_h -= self.parts['base_panel']['thickness']

                even_spacing = (interior_h - new_count * shelf_thickness) / (new_count + 1)

                for entry_data in self.manualShelfEntries:
                    entry_data['var'].set(even_spacing)
            except (ValueError, tk.TclError):
                # Handle cases where other inputs are not yet valid
                pass
        
        self.calculate_values()

    def toggle_shelf_input(self):
        # This function is no longer needed as shelf spacing is managed by the spinbox
        pass

    def toggle_side_wall_input(self):
        unit_type = self.unitTypeVar.get()
        is_endcap = unit_type == "Endcap"
        side_walls_active = self.sideWallToggleVar.get() and not is_endcap

        self.sideWallCheck.config(state=tk.DISABLED if is_endcap else tk.NORMAL)
        self.fullWallCheck.config(state=tk.NORMAL if side_walls_active else tk.DISABLED)
        
        is_full_wall = self.fullWallVar.get()
        self.sideWallSpin.config(state=tk.NORMAL if side_walls_active and not is_full_wall else tk.DISABLED)
    
    def on_shelf_material_change(self):
        """Called when shelf material changes between Melamine and Wire."""
        if self.shelfMaterialVar.get() == "Wire":
            # Pack before shelf_management_frame using before= parameter
            self.wire_shelf_frame.pack(fill=tk.X, padx=5, pady=(0, 5), before=self.shelf_management_frame)
            # If Slice Rack and not overridden, auto-adjust width
            if self.unitTypeVar.get() == "Slice Rack" and not self.width_override_var.get():
                self.auto_adjust_width_for_wire_shelf()
        else:
            self.wire_shelf_frame.pack_forget()
        
        self.calculate_values()
    
    def on_melamine_color_change(self, event=None):
        """Called when melamine color changes."""
        self.calculate_values()
    
    def on_wire_shelf_width_change(self, *args):
        """Called when wire shelf width selection changes."""
        if self.unitTypeVar.get() == "Slice Rack" and not self.width_override_var.get():
            self.auto_adjust_width_for_wire_shelf()
        self.calculate_values()
    
    def on_width_override_toggle(self):
        """Called when the width override checkbox is toggled."""
        if not self.width_override_var.get():
            # Override turned off - auto-adjust if Slice Rack with Wire shelves
            if self.unitTypeVar.get() == "Slice Rack" and self.shelfMaterialVar.get() == "Wire":
                self.auto_adjust_width_for_wire_shelf()
        self.calculate_values()
    
    def on_width_change(self, *args):
        """Called when width changes - check if we need to show warning."""
        self.check_width_warning()
        self.calculate_values()
    
    def auto_adjust_width_for_wire_shelf(self):
        """Auto-adjust unit width based on wire shelf width + 2.5 inches."""
        try:
            wire_width = float(self.wire_shelf_width_var.get())
            required_width = wire_width + 2.5
            self.width_var.set(required_width)
        except (ValueError, tk.TclError):
            pass
    
    def check_width_warning(self):
        """Check if width is insufficient for wire shelves and show warning."""
        try:
            # Only check for Slice Rack with Wire shelves and side walls
            if (self.unitTypeVar.get() == "Slice Rack" and 
                self.shelfMaterialVar.get() == "Wire" and
                self.sideWallToggleVar.get()):
                
                wire_width = float(self.wire_shelf_width_var.get())
                unit_width = self.width_var.get()
                min_required_width = wire_width + 2.5
                
                self._width_warning = unit_width < min_required_width
            else:
                self._width_warning = False
        except (ValueError, tk.TclError, AttributeError):
            self._width_warning = False

    def on_canvas_resize(self, event):
        """Handle canvas resize events to recalculate scaling and centering."""
        canvas = event.widget
        last_size = self._last_canvas_sizes.get(canvas)
        current_size = (canvas.winfo_width(), canvas.winfo_height())

        # Avoid recursion and only redraw when size actually changes.
        # Also ignore the initial (1, 1) size before the window is mapped.
        if last_size != current_size and current_size != (1, 1):
            self._last_canvas_sizes[canvas] = current_size
            self.calculate_values()

    def toggle_viewport(self):
        """Toggle visibility of viewports based on checkbox states."""
        # Forget all children from the main vertical paned window
        for child in self.viewport_paned.panes():
            self.viewport_paned.forget(child)

        front_on = self.front_view_var.get()
        top_on = self.top_view_var.get()
        side_on = self.side_view_var.get()

        # If either front or top view is on, we need the top row container
        if front_on or top_on:
            # Clear the horizontal paned window inside the top row container
            for child in self.top_row_paned.panes():
                self.top_row_paned.forget(child)
            
            if front_on:
                self.top_row_paned.add(self.front_viewport_frame, weight=1)
            if top_on:
                self.top_row_paned.add(self.top_viewport_frame, weight=1)
            
            # Add the top row container to the main vertical paned window
            self.viewport_paned.add(self.top_row_container, weight=2)

        # If the side view is on, add it to the main vertical paned window
        if side_on:
            self.viewport_paned.add(self.side_viewport_frame, weight=1)

        # Recalculate if any viewport is visible
        if any([front_on, top_on, side_on]):
            self.calculate_values()

    def _draw_top_canopy_supports(self, x0t, y0t, y1t, scale_top, x_positions, back_th):
        """Draws canopy supports in the top view, aligned with poles."""
        support_w_scaled = 6 * scale_top
        
        for xp in x_positions:
            pole_center_x = x0t + xp * scale_top
            support_x0 = pole_center_x - support_w_scaled / 2
            support_x1 = pole_center_x + support_w_scaled / 2
            
            # The supports span from the front of the back panel to the front of the canopy
            support_y_start = y0t + back_th
            self.canvas_top.create_rectangle(support_x0, support_y_start, support_x1, y1t, outline="black", stipple="gray50", fill="")

    def _draw_top_fascia_supports(self, x0t, y0t, y1t, scale_top, x_positions, back_th):
        """Draws fascia supports in the top view, aligned with poles."""
        support_w_scaled = 6 * scale_top
        
        for xp in x_positions:
            pole_center_x = x0t + xp * scale_top
            support_x0 = pole_center_x - support_w_scaled / 2
            support_x1 = pole_center_x + support_w_scaled / 2
            
            # The supports span from the front of the back panel to the front of the fascia
            support_y_start = y0t + back_th
            self.canvas_top.create_rectangle(support_x0, support_y_start, support_x1, y1t, outline="black", stipple="gray50", fill="", width=2)

    # ===== PRICING METHODS =====
    
    def create_pricing_panel(self, parent):
        """Create the pricing estimate panel"""
        self.pricing_panel = ttk.LabelFrame(parent, text="Pricing Estimate", relief=tk.RIDGE, borderwidth=2)
        self.pricing_panel.pack(fill=tk.X, padx=5, pady=5)
        
        # Authentication status
        auth_frame = ttk.Frame(self.pricing_panel)
        auth_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.auth_status_var = tk.StringVar(value="Not authenticated")
        self.auth_status_label = ttk.Label(auth_frame, textvariable=self.auth_status_var, font=("Arial", 9))
        self.auth_status_label.pack(side=tk.LEFT)
        
        self.reauth_button = ttk.Button(auth_frame, text="Re-authenticate", command=self.reauthenticate_zoho)
        self.reauth_button.pack(side=tk.RIGHT)
        
        # Material costs
        self.material_cost_var = tk.StringVar(value="Materials: $0.00")
        self.material_cost_label = ttk.Label(self.pricing_panel, textvariable=self.material_cost_var, font=("Arial", 10))
        self.material_cost_label.pack(pady=2)
        
        # Labor costs
        self.labor_cost_var = tk.StringVar(value="Labor: $0.00")
        self.labor_cost_label = ttk.Label(self.pricing_panel, textvariable=self.labor_cost_var, font=("Arial", 10))
        self.labor_cost_label.pack(pady=2)
        
        # Overhead costs
        self.overhead_cost_var = tk.StringVar(value="Overhead: $0.00")
        self.overhead_cost_label = ttk.Label(self.pricing_panel, textvariable=self.overhead_cost_var, font=("Arial", 10))
        self.overhead_cost_label.pack(pady=2)
        
        # Subtotal
        self.subtotal_var = tk.StringVar(value="Subtotal: $0.00")
        self.subtotal_label = ttk.Label(self.pricing_panel, textvariable=self.subtotal_var, font=("Arial", 10, "bold"))
        self.subtotal_label.pack(pady=2)
        
        # Profit margin
        profit_frame = ttk.Frame(self.pricing_panel)
        profit_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(profit_frame, text="Profit %:").pack(side=tk.LEFT)
        self.profit_margin_var = tk.StringVar(value="30")
        self.profit_entry = ttk.Entry(profit_frame, textvariable=self.profit_margin_var, width=8)
        self.profit_entry.pack(side=tk.LEFT, padx=5)
        self.profit_entry.bind("<KeyRelease>", self.update_pricing_display)
        
        self.profit_amount_var = tk.StringVar(value="$0.00")
        self.profit_amount_label = ttk.Label(profit_frame, textvariable=self.profit_amount_var)
        self.profit_amount_label.pack(side=tk.RIGHT)
        
        # Total price
        self.total_price_var = tk.StringVar(value="TOTAL: $0.00")
        self.total_price_label = tk.Label(self.pricing_panel, textvariable=self.total_price_var, 
                                        font=("Arial", 12, "bold"), fg="green")
        self.total_price_label.pack(pady=5)
        
        # Price breakdown button
        self.price_breakdown_button = tk.Button(self.pricing_panel, text="Price Breakdown", 
                                               command=self.show_price_breakdown,
                                               bg="#2196F3", fg="white", 
                                               font=("Arial", 10, "bold"))
        self.price_breakdown_button.pack(pady=5)
        
        # Initially hide the panel
        self.pricing_panel.pack_forget()
    
    def authenticate_zoho(self):
        """Open Zoho Books authentication dialog"""
        dialog = PricingAuthDialog(self.master, self.zoho_auth)
        result = dialog.show()
        
        if result:
            # Authentication successful, fetch pricing data
            self.refresh_pricing_data()
            self.update_pricing_display()
            messagebox.showinfo("Authentication Successful", 
                              "Connected to Zoho Books! Pricing features are now enabled.")
    
    def reauthenticate_zoho(self):
        """Re-authenticate with Zoho Books"""
        self.authenticate_zoho()
    
    def refresh_pricing_data(self):
        """Refresh pricing data from Zoho Books"""
        if not self.zoho_auth.is_authenticated():
            messagebox.showwarning("Not Authenticated", 
                                 "Please authenticate with Zoho Books first.")
            return
        
        try:
            self.pricing_manager.fetch_and_cache_pricing()
            self.pricing_data_loaded = True
            self.update_pricing_display()
            messagebox.showinfo("Pricing Data Updated", 
                              "Pricing data has been refreshed from Zoho Books.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh pricing data: {e}")
    
    def toggle_pricing_panel(self):
        """Toggle visibility of pricing panel"""
        if self.pricing_panel.winfo_viewable():
            self.pricing_panel.pack_forget()
        else:
            if not self.zoho_auth.is_authenticated():
                messagebox.showwarning("Not Authenticated", 
                                     "Please authenticate with Zoho Books first.")
                return
            self.pricing_panel.pack(fill=tk.X, padx=5, pady=5)
            self.update_pricing_display()
    
    def show_price_breakdown(self):
        """Show detailed price breakdown dialog"""
        if not self.zoho_auth.is_authenticated():
            messagebox.showwarning("Not Authenticated", 
                                 "Please authenticate with Zoho Books first.")
            return
        
        # Get current pricing data
        pricing_data = self._get_current_pricing_data()
        
        # Show breakdown dialog
        from price_breakdown_dialog import show_price_breakdown
        show_price_breakdown(self.master, pricing_data)
    
    def _get_current_pricing_data(self):
        """Get current pricing data for breakdown dialog"""
        if not self.part_list:
            return {
                'material_cost': 0,
                'labor_cost': 0,
                'overhead_cost': 0,
                'total_cost': 0,
                'materials_breakdown': [],
                'labor_data': {}
            }
        
        # Calculate material costs
        material_result = self.pricing_manager.calculate_parts_material_cost(self.part_list)
        
        # Calculate labor costs
        unit_type = self.unitTypeVar.get()
        width = self.width_var.get()
        height = self.height_var.get()
        has_wire_shelves = self.shelfMaterialVar.get() == 'Wire'
        
        labor_result = self.labor_calculator.calculate(
            unit_type, width, height, len(self.part_list), has_wire_shelves
        )
        
        return {
            'material_cost': material_result.get('total_cost', 0),
            'labor_cost': labor_result.get('labor_cost', 0),
            'overhead_cost': labor_result.get('overhead_cost', 0),
            'total_cost': material_result.get('total_cost', 0) + 
                         labor_result.get('labor_cost', 0) + 
                         labor_result.get('overhead_cost', 0),
            'materials_breakdown': material_result.get('breakdown', []),
            'labor_data': labor_result
        }
    
    def open_pricing_settings(self):
        """Open pricing settings dialog"""
        dialog = PricingSettingsDialog(self.master, self.labor_calculator, 
                                     self.zoho_client, self.pricing_manager)
        result = dialog.show()
        
        if result:
            # Settings updated, refresh pricing display
            self.update_pricing_display()
    
    def update_pricing_display(self, *args):
        """Update the pricing display with current calculations"""
        if not self.zoho_auth.is_authenticated():
            self.auth_status_var.set("Not authenticated")
            return
        
        self.auth_status_var.set("✓ Connected to Zoho Books")
        
        if not self.pricing_data_loaded:
            try:
                self.pricing_manager.fetch_and_cache_pricing()
                self.pricing_data_loaded = True
            except Exception as e:
                self.auth_status_var.set(f"Error: {e}")
                return
        
        try:
            # Calculate material costs
            material_result = self.pricing_manager.calculate_parts_material_cost(self.part_list)
            material_cost = material_result.get('total_cost', 0.0)
            
            # Calculate labor and overhead
            unit_type = self.unitTypeVar.get()
            width = self.width_var.get()
            height = self.height_var.get()
            depth = self.depth_var.get()
            part_count = len(self.part_list)
            has_canopy = self.top_var.get() == "Canopy"
            has_fascia = self.top_var.get() == "Fascia"
            shelf_count = self.numShelvesVar.get()
            wire_shelves = self.shelfMaterialVar.get() == "Wire"
            side_wall_length = self.sideWallLengthVar.get() if self.sideWallToggleVar.get() else 0
            
            # Calculate column and pole counts
            column_count = 1 if unit_type == "Endcap" else 0
            pole_count = len(self.compute_pole_positions_width(width)) if unit_type == "Endcap" else 0
            
            labor_result = self.labor_calculator.calculate(
                unit_type, width, height, depth, part_count,
                has_canopy, has_fascia, shelf_count, wire_shelves,
                side_wall_length, column_count, pole_count
            )
            
            labor_cost = labor_result.get('labor_cost', 0.0)
            overhead_cost = labor_result.get('overhead_cost', 0.0)
            
            # Calculate profit
            try:
                profit_percent = float(self.profit_margin_var.get())
            except (ValueError, tk.TclError):
                profit_percent = 30.0
            
            profit_result = self.labor_calculator.calculate_profit_margin(
                material_cost, labor_cost, overhead_cost, profit_percent
            )
            
            # Update display
            self.material_cost_var.set(f"Materials: ${material_cost:.2f}")
            self.labor_cost_var.set(f"Labor: ${labor_cost:.2f}")
            self.overhead_cost_var.set(f"Overhead: ${overhead_cost:.2f}")
            self.subtotal_var.set(f"Subtotal: ${profit_result['subtotal']:.2f}")
            self.profit_amount_var.set(f"${profit_result['profit_amount']:.2f}")
            self.total_price_var.set(f"TOTAL: ${profit_result['total_price']:.2f}")
            
        except Exception as e:
            self.auth_status_var.set(f"Error calculating pricing: {e}")
    
    def is_zoho_authenticated(self):
        """Check if Zoho Books is authenticated"""
        return self.zoho_auth.is_authenticated()

if __name__ == "__main__":
    root = tk.Tk()
    app = OmniPOPApp(root)
    root.mainloop()
