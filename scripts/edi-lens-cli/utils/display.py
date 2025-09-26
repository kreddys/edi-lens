"""
Display utilities for the EDI Lens CLI.
Handles formatting, colors, tables, and user interaction.
"""

import sys
from typing import List, Dict, Any, Optional
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Text colors
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class Display:
    """Utility class for formatted terminal output."""
    
    def __init__(self, width: int = 80):
        """Initialize display utility."""
        self.width = width
        self.colors_enabled = sys.stdout.isatty()  # Enable colors only in interactive terminals
        
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.colors_enabled:
            return f"{color}{text}{Colors.RESET}"
        return text
        
    def show_header(self):
        """Display the CLI application header."""
        header = """
🌊 EDI Lens CLI - Interactive NiFi Flow Manager
═══════════════════════════════════════════════
A powerful tool for managing NiFi flows, Registry operations, and version control.
"""
        print(self._colorize(header, Colors.CYAN + Colors.BOLD))
        
    def info(self, message: str):
        """Display an info message."""
        print(f"ℹ️  {message}")
        
    def success(self, message: str):
        """Display a success message."""
        print(self._colorize(f"✅ {message}", Colors.GREEN))
        
    def warning(self, message: str):
        """Display a warning message."""
        print(self._colorize(f"⚠️  {message}", Colors.YELLOW))
        
    def error(self, message: str):
        """Display an error message."""
        print(self._colorize(f"❌ {message}", Colors.RED))
        
    def debug(self, message: str):
        """Display a debug message."""
        print(self._colorize(f"🐛 {message}", Colors.DIM))
        
    def section_header(self, title: str):
        """Display a section header."""
        print(f"\n{self._colorize(title, Colors.BLUE + Colors.BOLD)}")
        print(self._colorize("─" * len(title), Colors.BLUE))
        
    def show_menu(self, title: str, options: List[str], show_back: bool = True) -> str:
        """Display a menu and get user selection."""
        print(f"\n{self._colorize(title, Colors.CYAN + Colors.BOLD)}")
        
        # Create menu box
        box_width = max(len(title), max(len(f"{i}. {opt}") for i, opt in enumerate(options, 1))) + 4
        box_width = min(box_width, self.width - 4)
        
        print("┌" + "─" * (box_width - 2) + "┐")
        
        for i, option in enumerate(options, 1):
            option_text = f"{i}. {option}"
            padding = " " * (box_width - len(option_text) - 3)
            print(f"│ {option_text}{padding}│")
            
        if show_back:
            back_text = "0. ⬅️  Back / Exit"
            padding = " " * (box_width - len(back_text) - 3)
            print(f"│ {back_text}{padding}│")
            
        print("└" + "─" * (box_width - 2) + "┘")
        
        return self.get_user_input("Select an option")
        
    def show_table(self, headers: List[str], rows: List[List[str]], title: str = ""):
        """Display a formatted table."""
        if title:
            self.section_header(title)
            
        if not rows:
            self.info("No data to display")
            return
            
        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
                    
        # Display table
        self._print_table_separator(col_widths, "top")
        self._print_table_row(headers, col_widths, header=True)
        self._print_table_separator(col_widths, "middle")
        
        for row in rows:
            self._print_table_row(row, col_widths)
            
        self._print_table_separator(col_widths, "bottom")
        
    def _print_table_separator(self, col_widths: List[int], position: str):
        """Print table separator line."""
        if position == "top":
            chars = ("┌", "┬", "┐", "─")
        elif position == "middle":
            chars = ("├", "┼", "┤", "─")
        else:  # bottom
            chars = ("└", "┴", "┘", "─")
            
        line = chars[0]
        for i, width in enumerate(col_widths):
            line += chars[3] * (width + 2)
            if i < len(col_widths) - 1:
                line += chars[1]
        line += chars[2]
        print(line)
        
    def _print_table_row(self, row: List[str], col_widths: List[int], header: bool = False):
        """Print a table row."""
        line = "│"
        for i, cell in enumerate(row):
            if i < len(col_widths):
                cell_str = str(cell).ljust(col_widths[i])
                if header:
                    cell_str = self._colorize(cell_str, Colors.BOLD)
                line += f" {cell_str} │"
        print(line)
        
    def show_flow_status(self, flow_data: Dict[str, Any]):
        """Display formatted flow status information."""
        self.section_header("Flow Status")
        
        status_color = Colors.GREEN if flow_data.get("status") == "RUNNING" else Colors.YELLOW
        status = self._colorize(flow_data.get("status", "UNKNOWN"), status_color)
        
        info_items = [
            ("Process Group ID", flow_data.get("process_group_id", "N/A")),
            ("Status", status),
            ("Total Processors", flow_data.get("processor_count", 0)),
            ("Running", flow_data.get("running_count", 0)),
            ("Stopped", flow_data.get("stopped_count", 0)),
            ("Invalid", flow_data.get("invalid_count", 0)),
        ]
        
        for label, value in info_items:
            print(f"  {label}: {value}")
            
    def show_quick_links(self, nifi_url: str, registry_url: str = None):
        """Display quick access links."""
        self.section_header("Quick Links")
        print(f"  🌊 NiFi UI: {nifi_url}")
        if registry_url:
            print(f"  📋 Registry UI: {registry_url}")
            
    def get_user_input(self, prompt: str, default: str = "") -> str:
        """Get user input with optional default value."""
        if default:
            full_prompt = f"{prompt} [{default}]: "
        else:
            full_prompt = f"{prompt}: "
            
        try:
            response = input(full_prompt).strip()
            return response if response else default
        except (EOFError, KeyboardInterrupt):
            return ""
            
    def get_yes_no(self, prompt: str, default: bool = False) -> bool:
        """Get yes/no input from user."""
        default_text = "Y/n" if default else "y/N"
        response = self.get_user_input(f"{prompt} ({default_text})")
        
        if not response:
            return default
            
        return response.lower() in ("y", "yes", "true", "1")
        
    def pause(self, message: str = "Press Enter to continue..."):
        """Pause execution until user presses Enter."""
        try:
            input(f"\n{message}")
        except (EOFError, KeyboardInterrupt):
            pass
            
    def clear_screen(self):
        """Clear the terminal screen."""
        import os
        os.system('clear' if os.name == 'posix' else 'cls')
        
    def show_progress(self, message: str):
        """Show a simple progress indicator."""
        print(f"🔄 {message}...", end=" ", flush=True)
        
    def complete_progress(self, success: bool = True):
        """Complete progress indication."""
        if success:
            print("✅")
        else:
            print("❌")