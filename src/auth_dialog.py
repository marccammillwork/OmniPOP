"""
OAuth Authentication Dialog
Modal dialog for Zoho Books OAuth authentication flow
"""

import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from zoho_auth import ZohoAuth, ZohoAuthDialog


class PricingAuthDialog:
    """Enhanced OAuth dialog specifically for pricing integration"""
    
    def __init__(self, parent, auth_handler):
        self.parent = parent
        self.auth_handler = auth_handler
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Zoho Books Authentication - Pricing Integration")
        self.dialog.geometry("600x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (500 // 2)
        self.dialog.geometry(f"600x500+{x}+{y}")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame
        main_frame = tk.Frame(self.dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Zoho Books Pricing Integration", 
                              font=("Arial", 16, "bold"), fg="#2E7D32")
        title_label.pack(pady=(0, 10))
        
        # Subtitle
        subtitle_label = tk.Label(main_frame, text="Connect to Zoho Books for real-time pricing data", 
                                 font=("Arial", 10), fg="#666666")
        subtitle_label.pack(pady=(0, 20))
        
        # Instructions frame
        instructions_frame = tk.Frame(main_frame)
        instructions_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Instructions
        instructions = tk.Text(instructions_frame, height=10, width=70, wrap=tk.WORD,
                             font=("Arial", 9), bg="#F5F5F5", relief=tk.FLAT)
        instructions.pack(fill=tk.BOTH, expand=True)
        
        instructions_text = """To enable pricing features in OmniPOP, you need to authenticate with Zoho Books:

1. Click 'Open Zoho Books' below to open your browser
2. Log in to your Zoho account (or create one if needed)
3. Grant OmniPOP permission to access your Zoho Books data
4. Copy the authorization code from the browser
5. Paste it in the field below and click 'Authenticate'

What this enables:
• Real-time material pricing from your Zoho Books inventory
• Automatic labor and overhead calculations
• Professional pricing estimates for your units
• Historical pricing data and cost analysis

Note: Only internal CAM Millwork employees will have access to pricing features.
External users will see a limited version without pricing data."""
        
        instructions.insert(tk.END, instructions_text)
        instructions.config(state=tk.DISABLED)
        
        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Open browser button
        self.browser_button = tk.Button(button_frame, text="Open Zoho Books", 
                                       command=self._open_browser, 
                                       bg="#4CAF50", fg="white", 
                                       font=("Arial", 11, "bold"),
                                       padx=20, pady=8)
        self.browser_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Refresh button
        self.refresh_button = tk.Button(button_frame, text="Refresh", 
                                       command=self._refresh_auth_url,
                                       bg="#2196F3", fg="white",
                                       font=("Arial", 10),
                                       padx=15, pady=8)
        self.refresh_button.pack(side=tk.LEFT)
        
        # Authorization code input frame
        code_frame = tk.LabelFrame(main_frame, text="Authorization Code", 
                                 font=("Arial", 10, "bold"), padx=10, pady=10)
        code_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Code entry
        self.code_entry = tk.Entry(code_frame, width=60, font=("Arial", 11),
                                  relief=tk.SUNKEN, bd=2)
        self.code_entry.pack(fill=tk.X, pady=(5, 0))
        self.code_entry.bind('<Return>', lambda e: self._authenticate())
        
        # Placeholder text
        placeholder = "Paste the authorization code here..."
        self.code_entry.insert(0, placeholder)
        self.code_entry.config(fg="gray")
        
        def on_focus_in(event):
            if self.code_entry.get() == placeholder:
                self.code_entry.delete(0, tk.END)
                self.code_entry.config(fg="black")
        
        def on_focus_out(event):
            if not self.code_entry.get():
                self.code_entry.insert(0, placeholder)
                self.code_entry.config(fg="gray")
        
        self.code_entry.bind('<FocusIn>', on_focus_in)
        self.code_entry.bind('<FocusOut>', on_focus_out)
        
        # Action buttons frame
        action_frame = tk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Authenticate button
        self.authenticate_button = tk.Button(action_frame, text="Authenticate", 
                                            command=self._authenticate, 
                                            bg="#FF9800", fg="white", 
                                            font=("Arial", 11, "bold"),
                                            padx=25, pady=8)
        self.authenticate_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Cancel button
        self.cancel_button = tk.Button(action_frame, text="Cancel", 
                                     command=self._cancel,
                                     font=("Arial", 10),
                                     padx=20, pady=8)
        self.cancel_button.pack(side=tk.LEFT)
        
        # Status frame
        status_frame = tk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Status label
        self.status_label = tk.Label(status_frame, text="", font=("Arial", 10))
        self.status_label.pack()
        
        # Progress bar (initially hidden)
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        
        # Focus on code entry
        self.code_entry.focus()
        self.code_entry.icursor(0)
    
    def _open_browser(self):
        """Open authorization URL in browser"""
        auth_url = self.auth_handler.generate_auth_url()
        webbrowser.open(auth_url)
        self.status_label.config(text="Browser opened. Please copy the authorization code.", 
                               fg="blue")
    
    def _refresh_auth_url(self):
        """Refresh the authorization URL"""
        self._open_browser()
        self.status_label.config(text="New authorization URL generated.", fg="blue")
    
    def _authenticate(self):
        """Authenticate with provided code"""
        code = self.code_entry.get().strip()
        
        # Check if it's placeholder text
        if code == "Paste the authorization code here...":
            self.status_label.config(text="Please enter the authorization code.", fg="red")
            return
        
        if not code:
            self.status_label.config(text="Please enter the authorization code.", fg="red")
            return
        
        # Show progress
        self.progress.pack(fill=tk.X, pady=(5, 0))
        self.progress.start()
        self.status_label.config(text="Authenticating with Zoho Books...", fg="blue")
        self.dialog.update()
        
        # Disable buttons during authentication
        self.authenticate_button.config(state=tk.DISABLED)
        self.browser_button.config(state=tk.DISABLED)
        self.refresh_button.config(state=tk.DISABLED)
        
        try:
            if self.auth_handler.exchange_code_for_tokens(code):
                self.progress.stop()
                self.progress.pack_forget()
                self.status_label.config(text="✓ Authentication successful! Pricing features enabled.", 
                                        fg="green")
                self.dialog.after(1500, self._close_success)
            else:
                self.progress.stop()
                self.progress.pack_forget()
                self.status_label.config(text="✗ Authentication failed. Please check the code and try again.", 
                                        fg="red")
                self._enable_buttons()
        except Exception as e:
            self.progress.stop()
            self.progress.pack_forget()
            self.status_label.config(text=f"✗ Error during authentication: {str(e)}", fg="red")
            self._enable_buttons()
    
    def _enable_buttons(self):
        """Re-enable buttons after authentication attempt"""
        self.authenticate_button.config(state=tk.NORMAL)
        self.browser_button.config(state=tk.NORMAL)
        self.refresh_button.config(state=tk.NORMAL)
    
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
    from zoho_auth import ZohoAuth
    
    root = tk.Tk()
    root.withdraw()
    
    auth = ZohoAuth()
    dialog = PricingAuthDialog(root, auth)
    result = dialog.show()
    
    if result:
        print("Authentication successful!")
    else:
        print("Authentication cancelled.")
    
    root.destroy()
