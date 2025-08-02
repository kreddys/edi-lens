import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.core.cdm import CdmInterchange
from src.core.schema_manager import schema_manager
from src.core.edi_parser import EdiParser, get_guide_version_from_edi
from src.core.profile_matcher import ProfileMatcher
from src.core.acknowledgements.ta1_validator import validate_interchange_envelope
from src.core.acknowledgements.ta1_generator import TA1Generator
# from src.repositories.validation_transaction_repo import ValidationTransactionRepository # Uncomment when created
from src.core.storage import storage_client
from src.api.schemas import ValidationResponse, ValidationFinding

logger = logging.getLogger(__name__)

# Custom exception for critical failures that should halt processing
class PrevalidationError(Exception):
    pass

def get_default_schema_for_guide(guide_version: str) -> Optional[str]:
    """Maps a guide version (like GS08) to a default base schema filename."""
    if guide_version == "005010X222A1":
        return "837.5010.X222.A1.json"
    return None

class ValidationService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.profile_matcher = ProfileMatcher(self.db)
        # self.validation_repo = ValidationTransactionRepository(self.db) # Uncomment when created

    async def process_edi_file(
        self,
        edi_data: str,
        file_name: str,
        tenant_id: str,
        user_id: str,
        username: str
    ) -> ValidationResponse:
        """
        The main entry point for the generic validation workflow.
        This orchestrates matching, parsing, validation, and acknowledgement generation.
        """
        logger.info(f"ValidationService: Starting processing for file '{file_name}' in tenant '{tenant_id}'.")

        # Step 1: Pre-validation checks that can cause an immediate hard failure.
        guide_version = get_guide_version_from_edi(edi_data)
        if not guide_version:
            logger.error(f"Could not determine guide version for file '{file_name}'.")
            raise PrevalidationError("Rejected: Could not determine implementation guide version (GS08)")

        # Step 2: Match Profile to determine validation rules
        matched_profile = await self.profile_matcher.match(edi_data, tenant_id)
        if matched_profile:
            logger.info(f"Matched EDI to profile: '{matched_profile.name}' (ID: {matched_profile.id})")
        else:
            logger.info("No specific partner profile matched. Using default validation rules.")
        
        # Step 3: Determine and load the schema
        schema_name_to_use = (
            matched_profile.validation_schema_name if matched_profile and matched_profile.validation_schema_name
            else get_default_schema_for_guide(guide_version)
        )
        
        if not schema_name_to_use:
             raise PrevalidationError(f"Rejected: No default schema mapping found for guide version: {guide_version}")

        logger.info(f"Selected schema for validation: '{schema_name_to_use}'")
        schema = schema_manager.get_schema(schema_name_to_use, tenant_id)
        if not schema:
             raise PrevalidationError(f"Rejected: Could not load required validation schema: {schema_name_to_use}")

        # Step 4: Create and store transaction records and original file (future implementation)
        transaction_id = uuid.uuid4()
        logger.info(f"Generated transaction ID: {transaction_id}")
        # await self.validation_repo.create_transaction(...)
        # storage_client.upload(edi_data.encode('utf-8'), f"{tenant_id}/{transaction_id}/request.edi")

        # Step 5: Parse the file
        parser = EdiParser(edi_string=edi_data, schema=schema)
        interchange = parser.parse()

        # Step 6: TA1 Validation and Generation
        interchange_errors = validate_interchange_envelope(interchange, edi_data)
        ta1_generator = TA1Generator()
        ta1_ack_string = ta1_generator.generate(interchange.header, interchange_errors)

        if ta1_ack_string:
             logger.info(f"Generated TA1 Acknowledgement for transaction {transaction_id}.")
             # storage_client.upload(ta1_ack_string.encode('utf-8'), f"{tenant_id}/{transaction_id}/ta1.edi")

        # Step 7: TODO: Implement 999 Validation and Generation
        all_findings: list[ValidationFinding] = []
        ack999_acknowledgement: Optional[str] = None
        
        # Step 8: TODO: Update transaction record to COMPLETE
        # await self.validation_repo.update_transaction(status="COMPLETE", ...)

        # Step 9: Return the final response object
        status_message = "Rejected at Interchange Level" if interchange_errors else "Validation Complete"
        return ValidationResponse(
            status=status_message,
            findings=all_findings,
            ta1_acknowledgement=ta1_ack_string,
            ack999_acknowledgement=ack999_acknowledgement,
        )