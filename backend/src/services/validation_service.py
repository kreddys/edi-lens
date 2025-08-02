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
# --- UNCOMMENT AND ADD ---
from src.repositories.validation_transaction_repo import ValidationTransactionRepository
from src.models.validation_transaction import ValidationStatus
# ---
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
        # --- UNCOMMENT ---
        self.validation_repo = ValidationTransactionRepository(self.db)

    async def process_edi_file(
        self,
        edi_data: str,
        file_name: str,
        tenant_id: str,
        user_id: str,
        username: str
    ) -> ValidationResponse:
        logger.info(f"ValidationService: Starting processing for file '{file_name}' in tenant '{tenant_id}'.")
        
        transaction_id = uuid.uuid4()
        ta1_ack_string: Optional[str] = None
        ack999_acknowledgement: Optional[str] = None
        all_findings: list[ValidationFinding] = []
        final_status: ValidationStatus = ValidationStatus.PENDING
        
        try:
            # Steps 1 & 2: Profile Matching and Schema Selection
            matched_profile = await self.profile_matcher.match(edi_data, tenant_id)
            profile_id = matched_profile.id if matched_profile else None
            
            guide_version = get_guide_version_from_edi(edi_data)
            if not guide_version:
                raise PrevalidationError("Rejected: Could not determine implementation guide version (GS08)")
            
            schema_name_to_use = (
                matched_profile.validation_schema_name if matched_profile and matched_profile.validation_schema_name
                else get_default_schema_for_guide(guide_version)
            )
            if not schema_name_to_use:
                raise PrevalidationError(f"Rejected: No default schema mapping found for guide version: {guide_version}")

            schema = schema_manager.get_schema(schema_name_to_use, tenant_id)
            if not schema:
                raise PrevalidationError(f"Rejected: Could not load required validation schema: {schema_name_to_use}")

            # Step 3 & 4: Create DB record and store original file
            request_key = f"{tenant_id}/{transaction_id}/request.edi"
            storage_client.upload(edi_data.encode('utf-8'), request_key)
            
            await self.validation_repo.create_transaction(
                transaction_id=transaction_id, tenant_id=tenant_id, user_id=user_id,
                username=username, profile_id=profile_id, filename=file_name,
                request_key=request_key
            )

            # Step 5: Parse
            parser = EdiParser(edi_string=edi_data, schema=schema)
            interchange = parser.parse()

            # Step 6: TA1 Validation and Generation
            interchange_errors = validate_interchange_envelope(interchange, edi_data)
            ta1_generator = TA1Generator()
            ta1_ack_string = ta1_generator.generate(interchange.header, interchange_errors)

            # Step 7: 999 Validation and Generation (placeholder)
            if not interchange_errors:
                # validation_engine = ValidationEngine() ...
                final_status = ValidationStatus.COMPLETE
            else:
                final_status = ValidationStatus.FAILED

            # Step 8: Store acknowledgements and update DB record
            ta1_key = None
            if ta1_ack_string:
                ta1_key = f"{tenant_id}/{transaction_id}/ta1.edi"
                storage_client.upload(ta1_ack_string.encode('utf-8'), ta1_key)

            await self.validation_repo.update_transaction_acks_and_status(
                transaction_id=transaction_id,
                status=final_status,
                ta1_key=ta1_key,
                ack999_key=None # Placeholder
            )

        except Exception as e:
            # If anything fails, update the DB record to FAILED
            await self.validation_repo.update_transaction_acks_and_status(
                transaction_id=transaction_id, status=ValidationStatus.FAILED,
                ta1_key=None, ack999_key=None
            )
            # Re-raise the exception to be handled by the API layer
            raise

        # Step 9: Return the final response object
        response_status_message = "Rejected at Interchange Level" if interchange_errors else "Validation Complete"
        return ValidationResponse(
            status=response_status_message,
            findings=all_findings,
            ta1_acknowledgement=ta1_ack_string,
            ack999_acknowledgement=ack999_acknowledgement,
        )