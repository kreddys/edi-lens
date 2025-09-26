"""
Base menu class for all CLI menus.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cli_app import EDILensCLI


class BaseMenu(ABC):
    """Base class for all CLI menus."""
    
    def __init__(self, app: 'EDILensCLI'):
        """Initialize the menu with reference to the main app."""
        self.app = app
        self.display = app.display
        self.api_client = app.api_client
        self.config = app.config
        
    @abstractmethod
    async def show(self):
        """Show the menu and handle user interaction."""
        pass
        
    @abstractmethod
    def get_menu_title(self) -> str:
        """Get the title of the menu."""
        pass
        
    @abstractmethod
    def get_menu_options(self) -> List[str]:
        """Get the list of menu options."""
        pass
        
    async def handle_menu_selection(self, selection: str) -> bool:
        """
        Handle menu selection and return whether to continue showing the menu.
        
        Args:
            selection: User's menu selection
            
        Returns:
            True to continue showing menu, False to exit menu
        """
        try:
            choice = int(selection)
            
            if choice == 0:
                return False  # Exit/back option
                
            options = self.get_menu_options()
            if 1 <= choice <= len(options):
                await self.execute_option(choice)
                return True
            else:
                self.display.error("Invalid selection. Please try again.")
                return True
                
        except ValueError:
            self.display.error("Please enter a valid number.")
            return True
        except KeyboardInterrupt:
            return False
        except Exception as e:
            self.display.error(f"An error occurred: {e}")
            return True
            
    @abstractmethod
    async def execute_option(self, option: int):
        """Execute the selected menu option."""
        pass
        
    def show_menu_and_get_choice(self) -> str:
        """Display the menu and get user choice."""
        return self.display.show_menu(
            title=self.get_menu_title(),
            options=self.get_menu_options(),
            show_back=True
        )
        
    async def show_error_details(self, error: Exception):
        """Show detailed error information to the user."""
        self.display.error(f"Operation failed: {str(error)}")
        
        # For API errors, show more context if available
        if hasattr(error, 'response'):
            try:
                error_data = error.response.json()
                if isinstance(error_data, dict) and 'detail' in error_data:
                    detail = error_data['detail']
                    if isinstance(detail, dict):
                        if 'user_message' in detail:
                            self.display.info(f"Details: {detail['user_message']}")
                        if 'action_required' in detail:
                            self.display.warning(f"Action required: {detail['action_required']}")
            except:
                pass  # Ignore JSON parsing errors
                
        self.display.pause("Press Enter to continue...")
        
    def confirm_action(self, message: str, default: bool = False) -> bool:
        """Get user confirmation for an action."""
        return self.display.get_yes_no(message, default)
        
    async def show_operation_result(self, result: Dict[str, Any], operation_name: str):
        """Show the result of an operation to the user."""
        if result.get("success"):
            self.display.success(f"{operation_name} completed successfully!")
            
            # Show additional details if available
            if "message" in result:
                self.display.info(result["message"])
                
            # Show specific result data
            if "process_group_id" in result:
                self.display.info(f"Process Group ID: {result['process_group_id']}")
                
            if "flow_id" in result:
                self.display.info(f"Flow ID: {result['flow_id']}")
                
            if "version" in result:
                self.display.info(f"Version: {result['version']}")
                
        else:
            self.display.error(f"{operation_name} failed!")
            
            if "message" in result:
                self.display.error(result["message"])
                
            # Show failure details if available
            if "failures" in result:
                self.display.section_header("Failure Details")
                failures = result["failures"]
                if isinstance(failures, list):
                    for i, failure in enumerate(failures, 1):
                        self.display.error(f"{i}. {failure}")
                        
        self.display.pause("Press Enter to continue...")
        
    def get_user_input_with_validation(self, prompt: str, validator=None, default: str = "") -> str:
        """Get user input with optional validation."""
        while True:
            value = self.display.get_user_input(prompt, default)
            
            if not value and not default:
                self.display.warning("This field is required.")
                continue
                
            if validator:
                try:
                    if validator(value):
                        return value
                    else:
                        self.display.warning("Invalid input. Please try again.")
                        continue
                except Exception as e:
                    self.display.warning(f"Validation error: {e}")
                    continue
                    
            return value