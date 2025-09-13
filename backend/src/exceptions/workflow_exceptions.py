"""
Workflow-specific exceptions for proper error handling
"""

class WorkflowError(Exception):
    """Base exception for all workflow-related errors"""
    pass

class NiFiConnectionError(WorkflowError):
    """NiFi connection or authentication failed"""
    def __init__(self, message: str, url: str = None, status_code: int = None):
        self.url = url
        self.status_code = status_code
        super().__init__(f"NiFi connection failed: {message}")

class NiFiAPIError(WorkflowError):
    """NiFi API call failed"""
    def __init__(self, message: str, endpoint: str = None, status_code: int = None, response_body: str = None):
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"NiFi API error: {message}")

class RegistryConnectionError(WorkflowError):
    """Registry connection failed"""
    def __init__(self, message: str, url: str = None, status_code: int = None):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Registry connection failed: {message}")

class RegistryImportError(WorkflowError):
    """Registry import failed - workflow cannot be deployed properly"""
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"Registry import failed: {message}")

class ParameterSubstitutionError(WorkflowError):
    """Parameter substitution failed - processors will not work correctly"""
    def __init__(self, message: str, invalid_processors: list = None):
        self.invalid_processors = invalid_processors or []
        super().__init__(f"Parameter substitution failed: {message}")

class ProcessorValidationError(WorkflowError):
    """Processors failed validation - workflow cannot execute properly"""
    def __init__(self, message: str, validation_errors: dict = None):
        self.validation_errors = validation_errors or {}
        super().__init__(f"Processor validation failed: {message}")

class VersionControlError(WorkflowError):
    """Version control setup failed - Registry integration broken"""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(f"Version control setup failed: {message}")

class TemplateValidationError(WorkflowError):
    """Template validation failed - template structure is invalid"""
    def __init__(self, message: str, template_id: str = None):
        self.template_id = template_id
        super().__init__(f"Template validation failed: {message}")

class ProcessorCreationError(WorkflowError):
    """Failed to create processors in NiFi"""
    def __init__(self, message: str, processor_name: str = None, errors: list = None):
        self.processor_name = processor_name
        self.errors = errors or []
        super().__init__(f"Processor creation failed: {message}")

class ConnectionCreationError(WorkflowError):
    """Failed to create connections in NiFi"""
    def __init__(self, message: str, connection_name: str = None, errors: list = None):
        self.connection_name = connection_name
        self.errors = errors or []
        super().__init__(f"Connection creation failed: {message}")