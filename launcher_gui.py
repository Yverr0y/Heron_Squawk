#!/usr/bin/env python3
"""
Heron Squawk - GUI Launcher
Cross-platform launcher with graphical interface
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import threading


class HeronSquawkLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("HERON SQUAWK")
        self.root.geometry("480x520")
        self.root.resizable(False, False)

        # Theme colors matching web UI
        self.bg_primary = "#0a0e1a"
        self.bg_secondary = "#111827"
        self.bg_tertiary = "#1a2332"
        self.border_color = "#2d3748"
        self.border_accent = "#3d4a5c"
        self.text_primary = "#e4e8f0"
        self.text_secondary = "#9ca3af"
        self.text_dim = "#6b7280"
        self.accent_primary = "#3b82f6"
        self.accent_secondary = "#60a5fa"
        self.accent_danger = "#ef4444"

        self.root.configure(bg=self.bg_primary)

        self.process = None

        self.setup_ui()

    def setup_ui(self):
        # Main container with border
        main_container = tk.Frame(
            self.root,
            bg=self.bg_secondary,
            highlightbackground=self.border_color,
            highlightthickness=2
        )
        main_container.pack(padx=15, pady=15, fill="both", expand=True)

        # Header section
        header_frame = tk.Frame(main_container, bg=self.bg_secondary)
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        # Diamond icon + title
        title_row = tk.Frame(header_frame, bg=self.bg_secondary)
        title_row.pack()

        diamond_label = tk.Label(
            title_row,
            text="\u25c6",
            font=("DejaVu Sans", 14),
            bg=self.bg_secondary,
            fg=self.accent_primary
        )
        diamond_label.pack(side="left", padx=(0, 8))

        title_label = tk.Label(
            title_row,
            text="HERON SQUAWK",
            font=("DejaVu Sans", 20, "bold"),
            bg=self.bg_secondary,
            fg=self.accent_primary
        )
        title_label.pack(side="left")

        subtitle_label = tk.Label(
            header_frame,
            text="L O R A   M E S H   N E T W O R K",
            font=("DejaVu Sans", 8),
            bg=self.bg_secondary,
            fg=self.text_dim
        )
        subtitle_label.pack(pady=(5, 0))

        # Separator line
        separator = tk.Frame(main_container, bg=self.border_color, height=2)
        separator.pack(fill="x", padx=20, pady=15)

        # Status indicator row
        status_row = tk.Frame(main_container, bg=self.bg_secondary)
        status_row.pack(fill="x", padx=20, pady=(0, 15))

        self.status_dot = tk.Label(
            status_row,
            text="\u25cf",
            font=("DejaVu Sans", 10),
            bg=self.bg_secondary,
            fg=self.text_dim
        )
        self.status_dot.pack(side="left")

        self.status_label = tk.Label(
            status_row,
            text="STANDBY",
            font=("DejaVu Sans", 10, "bold"),
            bg=self.bg_secondary,
            fg=self.text_dim
        )
        self.status_label.pack(side="left", padx=(8, 0))

        # Input section
        input_section = tk.Frame(main_container, bg=self.bg_tertiary)
        input_section.pack(fill="x", padx=20, pady=(0, 15))

        # Section header
        section_header = tk.Label(
            input_section,
            text="CONNECTION PARAMETERS",
            font=("DejaVu Sans", 9, "bold"),
            bg=self.bg_tertiary,
            fg=self.text_dim
        )
        section_header.pack(anchor="w", padx=15, pady=(12, 8))

        # Input fields container
        fields_frame = tk.Frame(input_section, bg=self.bg_tertiary)
        fields_frame.pack(fill="x", padx=15, pady=(0, 15))

        # Create input fields
        self.create_input_field(fields_frame, "COM PORT", "com_port", "8 or /dev/ttyUSB0")
        self.create_input_field(fields_frame, "PASSPHRASE", "passphrase", "Enter mesh passphrase")
        self.create_input_field(fields_frame, "WEB PORT", "web_port", "8000")

        # HTTPS option
        https_frame = tk.Frame(input_section, bg=self.bg_tertiary)
        https_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.https_var = tk.BooleanVar(value=False)
        https_checkbox = tk.Checkbutton(
            https_frame,
            text="ENABLE HTTPS (Self-signed certificate)",
            variable=self.https_var,
            bg=self.bg_tertiary,
            fg=self.text_secondary,
            selectcolor=self.bg_primary,
            activebackground=self.bg_tertiary,
            activeforeground=self.accent_primary,
            font=("DejaVu Sans", 9, "bold")
        )
        https_checkbox.pack(anchor="w")

        # Button section
        button_frame = tk.Frame(main_container, bg=self.bg_secondary)
        button_frame.pack(fill="x", padx=20, pady=(5, 15))

        # Start button
        self.start_button = tk.Button(
            button_frame,
            text="\u25b6  INITIALIZE",
            command=self.start_server,
            bg=self.accent_primary,
            fg="white",
            font=("DejaVu Sans", 11, "bold"),
            relief="flat",
            cursor="hand2",
            activebackground=self.accent_secondary,
            activeforeground="white",
            padx=20,
            pady=12
        )
        self.start_button.pack(side="left", expand=True, fill="x", padx=(0, 5))

        # Stop button
        self.stop_button = tk.Button(
            button_frame,
            text="\u25a0  TERMINATE",
            command=self.stop_server,
            bg=self.bg_tertiary,
            fg=self.text_secondary,
            font=("DejaVu Sans", 11, "bold"),
            relief="flat",
            cursor="hand2",
            activebackground=self.accent_danger,
            activeforeground="white",
            state="disabled",
            padx=20,
            pady=12
        )
        self.stop_button.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # Server URL display (hidden initially)
        self.url_frame = tk.Frame(main_container, bg=self.bg_tertiary)
        self.url_frame.pack(fill="x", padx=20, pady=(0, 15))

        url_label = tk.Label(
            self.url_frame,
            text="SERVER ENDPOINT",
            font=("DejaVu Sans", 8, "bold"),
            bg=self.bg_tertiary,
            fg=self.text_dim
        )
        url_label.pack(anchor="w", padx=12, pady=(10, 3))

        self.url_display = tk.Label(
            self.url_frame,
            text="--",
            font=("Consolas", 11),
            bg=self.bg_primary,
            fg=self.accent_primary,
            padx=12,
            pady=8
        )
        self.url_display.pack(fill="x", padx=12, pady=(0, 10))

        # Footer
        footer_frame = tk.Frame(main_container, bg=self.bg_secondary)
        footer_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 15))

        footer_label = tk.Label(
            footer_frame,
            text="ENCRYPTED MESH COMMUNICATIONS",
            font=("DejaVu Sans", 8),
            bg=self.bg_secondary,
            fg=self.text_dim
        )
        footer_label.pack()

    def create_input_field(self, parent, label_text, var_name, placeholder):
        # Field container
        field_frame = tk.Frame(parent, bg=self.bg_tertiary)
        field_frame.pack(fill="x", pady=4)

        # Label
        label = tk.Label(
            field_frame,
            text=label_text,
            font=("DejaVu Sans", 9, "bold"),
            bg=self.bg_tertiary,
            fg=self.text_secondary,
            width=14,
            anchor="w"
        )
        label.pack(side="left")

        # Entry with border frame
        entry_border = tk.Frame(
            field_frame,
            bg=self.border_accent,
            padx=1,
            pady=1
        )
        entry_border.pack(side="left", fill="x", expand=True)

        entry = tk.Entry(
            entry_border,
            font=("Consolas", 10),
            bg=self.bg_primary,
            fg=self.text_primary,
            insertbackground=self.accent_primary,
            relief="flat",
            highlightthickness=0
        )
        entry.pack(fill="x", ipady=6, ipadx=8)
        entry.insert(0, placeholder)

        # Placeholder behavior
        def on_focus_in(_event):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                entry.config(fg=self.text_primary)
                entry_border.config(bg=self.accent_primary)

        def on_focus_out(_event):
            entry_border.config(bg=self.border_accent)
            if entry.get() == "":
                entry.insert(0, placeholder)
                entry.config(fg=self.text_dim)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        entry.config(fg=self.text_dim)

        setattr(self, f"{var_name}_entry", entry)

    def get_com_port(self):
        """Get COM port, auto-prepending 'COM' on Windows if just a number is entered."""
        com_port = self.com_port_entry.get()
        if com_port and com_port.isdigit() and sys.platform == "win32":
            return f"COM{com_port}"
        return com_port

    def validate_inputs(self):
        com_port = self.com_port_entry.get()
        passphrase = self.passphrase_entry.get()
        web_port = self.web_port_entry.get()

        if not com_port or com_port == "8 or /dev/ttyUSB0":
            messagebox.showerror("Input Error", "Please enter a COM port")
            return False

        if not passphrase or passphrase == "Enter mesh passphrase":
            messagebox.showerror("Input Error", "Please enter a passphrase")
            return False

        if not web_port or web_port == "8000":
            web_port = "8000"
            self.web_port_entry.delete(0, tk.END)
            self.web_port_entry.insert(0, "8000")

        try:
            int(web_port)
        except ValueError:
            messagebox.showerror("Input Error", "Web port must be a number")
            return False

        return True

    def start_server(self):
        if not self.validate_inputs():
            return

        com_port = self.get_com_port()
        passphrase = self.passphrase_entry.get()
        web_port = self.web_port_entry.get()
        use_https = self.https_var.get()

        # Update UI to running state
        self.start_button.config(state="disabled", bg=self.bg_tertiary)
        self.stop_button.config(state="normal", bg=self.accent_danger)
        self.status_dot.config(fg=self.accent_primary)
        self.status_label.config(text="ONLINE", fg=self.accent_primary)
        protocol = "https" if use_https else "http"
        self.url_display.config(text=f"{protocol}://localhost:{web_port}")

        # Start server in thread
        def run_server():
            try:
                python_cmd = "python" if sys.platform == "win32" else "python3"
                # Argument order: COM_PORT PASSPHRASE [WEB_PORT] [--https]
                cmd = [python_cmd, "app.py", com_port, passphrase, web_port]
                if use_https:
                    cmd.append("--https")
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                self.process.wait()
                self.root.after(0, self.on_server_stopped)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to start server: {e}"))
                self.root.after(0, self.on_server_stopped)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def stop_server(self):
        if self.process:
            try:
                self.process.terminate()
                self.process = None
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop server: {e}")
        self.on_server_stopped()

    def on_server_stopped(self):
        self.start_button.config(state="normal", bg=self.accent_primary)
        self.stop_button.config(state="disabled", bg=self.bg_tertiary)
        self.status_dot.config(fg=self.text_dim)
        self.status_label.config(text="OFFLINE", fg=self.text_dim)
        self.url_display.config(text="--")

    def on_closing(self):
        if self.process:
            if messagebox.askokcancel("Confirm Exit", "Server is running. Terminate and exit?"):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = HeronSquawkLauncher(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
