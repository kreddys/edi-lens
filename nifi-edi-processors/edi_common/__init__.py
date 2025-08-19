"""
EDI Common Modules

Shared functionality ported from the backend for use in NiFi processors.
These modules provide EDI validation, parsing, TA1 generation, and schema management.
"""

from .cdm import (
    CdmElement,
    CdmSegment, 
    CdmLoop,
    CdmTransaction,
    CdmFunctionalGroup,
    CdmInterchange,
    CdmValidationError
)

from .ta1_defs import (
    TA1AcknowledgementCode,
    TA1NoteCode,
    InterchangeError
)

from .validation_service import (
    ValidationResult,
    EDIValidationService
)

from .ta1_generator import TA1Generator
from .schema_manager import SchemaManager
from .edi_parser import EdiParser

__all__ = [
    "CdmElement",
    "CdmSegment", 
    "CdmLoop",
    "CdmTransaction",
    "CdmFunctionalGroup",
    "CdmInterchange",
    "CdmValidationError",
    "TA1AcknowledgementCode",
    "TA1NoteCode", 
    "InterchangeError",
    "ValidationResult",
    "EDIValidationService",
    "TA1Generator",
    "SchemaManager",
    "EdiParser"
]