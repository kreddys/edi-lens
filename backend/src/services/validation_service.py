import logging
import uuid
import time
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
from src.repositories.processing_log_repo import ProcessingLogRepository
from src.models.validation_transaction import ValidationStatus
# ---
from src.core.storage import storage_client
from src.api.schemas import ValidationResponse, ValidationFinding, FindingLocation

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
        self.processing_log_repo = ProcessingLogRepository(self.db)

    async def process_edi_file(
        self,
        edi_data: str,
        file_name: str,
        tenant_id: str,
        user_id: str,
        username: str,
        profile_name: Optional[str] = None
    ) -> ValidationResponse:
        """
        Crystal clear EDI validation with flexible profile selection!
        Supports both manual profile override and auto-detection.
        """
        logger.info(f"ValidationService: Starting processing for file '{file_name}' in tenant '{tenant_id}' "
                   f"with profile_name='{profile_name}'")
        
        start_time = time.time()
        transaction_id = uuid.uuid4()
        matched_profile = None
        detection_method = "manual" if profile_name else "auto"
        
        try:
            # Step 1: Profile Selection (Manual Override or Auto-Detection)
            if profile_name:
                # Manual override - use specified profile
                matched_profile = await self.profile_matcher.get_profile_by_name(tenant_id, profile_name)
                if not matched_profile:
                    available_profiles = await self.profile_matcher.list_tenant_profiles(tenant_id)
                    profile_names = [p.name for p in available_profiles]
                    raise PrevalidationError(f"Profile '{profile_name}' not found. Available profiles: {', '.join(profile_names)}")
                logger.info(f"Using manual profile override: '{matched_profile.name}'")
            else:
                # Auto-detection using existing ProfileMatcher
                matched_profile = await self.profile_matcher.match(edi_data, tenant_id)
                if not matched_profile:
                    # Check if there are any profiles configured at all
                    available_profiles = await self.profile_matcher.list_tenant_profiles(tenant_id)
                    if available_profiles:
                        # Profiles exist but none matched
                        profile_names = [p.name for p in available_profiles]
                        raise PrevalidationError(f"No matching profile found for this EDI document. Available profiles: {', '.join(profile_names)}")
                    else:
                        # No profiles configured - fall back to default behavior for backwards compatibility
                        logger.info("No profiles configured for tenant. Using default validation with SNIP3, TA1 enabled.")
                        # Create a temporary default profile for processing
                        from src.models.partner_profile import PartnerProfile
                        matched_profile = PartnerProfile(
                            id=None,
                            name="default-fallback",
                            tenant_id=tenant_id,
                            partner_id=None,
                            implementation_guide="837P",
                            validation_schema_name=None,  # Will use default schema mapping
                            snip_level="SNIP3",
                            generate_ta1=True,
                            generate_999=False,
                            priority=999
                        )
                        detection_method = "fallback"
                logger.info(f"Auto-detected profile: '{matched_profile.name}'")

            # Step 2: Schema Selection (from matched profile or default)
            guide_version = get_guide_version_from_edi(edi_data)
            if not guide_version:
                raise PrevalidationError("Rejected: Could not determine implementation guide version (GS08)")
            
            schema_name_to_use = (
                matched_profile.validation_schema_name if matched_profile.validation_schema_name
                else get_default_schema_for_guide(guide_version)
            )
            if not schema_name_to_use:
                raise PrevalidationError(f"Rejected: No default schema mapping found for guide version: {guide_version}")

            schema = schema_manager.get_schema(schema_name_to_use, tenant_id)
            if not schema:
                raise PrevalidationError(f"Rejected: Could not load required validation schema: {schema_name_to_use}")

            # Step 3: Store original file
            request_key = f"{tenant_id}/{transaction_id}/request.edi"
            storage_client.upload(edi_data.encode('utf-8'), request_key)
            
            # Step 4: Create validation transaction record (only if profile has ID)
            if matched_profile.id is not None:
                await self.validation_repo.create_transaction(
                    transaction_id=transaction_id, tenant_id=tenant_id, user_id=user_id,
                    username=username, profile_id=matched_profile.id, filename=file_name,
                    request_key=request_key
                )

            # Step 5: Parse EDI
            parser = EdiParser(edi_string=edi_data, schema=schema)
            interchange = parser.parse()

            # Step 6: Validate and Generate Acknowledgments based on profile configuration
            interchange_errors = validate_interchange_envelope(interchange, edi_data)
            
            # Generate TA1 if configured in profile
            ta1_content = None
            ta1_key = None
            if matched_profile.generate_ta1:
                ta1_generator = TA1Generator()
                ta1_content = ta1_generator.generate(interchange.header, interchange_errors)
                if ta1_content:
                    ta1_key = f"{tenant_id}/{transaction_id}/ta1.edi"
                    storage_client.upload(ta1_content.encode('utf-8'), ta1_key)
            
            # Generate 999 if configured in profile (placeholder for now)
            ta1_999_content = None
            ta1_999_key = None
            if matched_profile.generate_999:
                # TODO: Implement 999 generation
                logger.info("999 generation requested but not yet implemented")

            # Step 7: Determine validation result
            is_valid = len(interchange_errors) == 0
            validation_result = "VALID" if is_valid else "INVALID"
            final_status = ValidationStatus.COMPLETE if is_valid else ValidationStatus.FAILED

            # Step 8: Update validation transaction (only if profile has ID)
            if matched_profile.id is not None:
                await self.validation_repo.update_transaction_acks_and_status(
                    transaction_id=transaction_id,
                    status=final_status,
                    ta1_key=ta1_key,
                    ack999_key=ta1_999_key
                )

            # Step 9: Create processing log entry
            processing_time_ms = int((time.time() - start_time) * 1000)
            await self.processing_log_repo.create_log(
                tenant_id=tenant_id,
                source="API",
                file_name=file_name,
                file_size_bytes=len(edi_data.encode('utf-8')),
                validation_result=validation_result,
                processing_time_ms=processing_time_ms,
                error_count=len(interchange_errors),
                schema_name=schema_name_to_use,
                snip_level_used=matched_profile.snip_level,
                profile_id=matched_profile.id,
                ta1_generated=bool(ta1_content),
                ta1_999_generated=bool(ta1_999_content),
                original_content_path=request_key,
                ta1_content_path=ta1_key,
                ta1_999_content_path=ta1_999_key
            )

            # Step 10: Return enhanced response
            findings = [
                ValidationFinding(
                    level="error",
                    code="interchange_error",
                    message=str(error),
                    location=FindingLocation(
                        segment_id="ISA",
                        segment_instance=1,
                        element_position=1,
                        line_number=1
                    )
                ) for error in interchange_errors
            ]

            return ValidationResponse(
                valid=is_valid,
                status="Validation Complete" if is_valid else "Rejected at Interchange Level",
                findings=findings,
                errors=findings,  # Alias for compatibility
                ta1_content=ta1_content,
                ta1_999_content=ta1_999_content,
                processing_time_ms=processing_time_ms,
                matched_profile=matched_profile.name,
                schema_used=schema_name_to_use,
                snip_level_used=matched_profile.snip_level,
                detection_method=detection_method,
                # Legacy fields for backwards compatibility
                ta1_acknowledgement=ta1_content,
                ack999_acknowledgement=ta1_999_content
            )

        except Exception as e:
            # If anything fails, update the DB record to FAILED and create error log
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            try:
                if matched_profile and matched_profile.id is not None:
                    await self.validation_repo.update_transaction_acks_and_status(
                        transaction_id=transaction_id, status=ValidationStatus.FAILED,
                        ta1_key=None, ack999_key=None
                    )
                
                # Create error processing log
                await self.processing_log_repo.create_log(
                    tenant_id=tenant_id,
                    source="API",
                    file_name=file_name,
                    file_size_bytes=len(edi_data.encode('utf-8')),
                    validation_result="ERROR",
                    processing_time_ms=processing_time_ms,
                    error_count=1,
                    schema_name=None,
                    snip_level_used=matched_profile.snip_level if matched_profile else None,
                    profile_id=matched_profile.id if matched_profile else None,
                    ta1_generated=False,
                    ta1_999_generated=False
                )
            except Exception as log_error:
                logger.error(f"Failed to create error log: {log_error}")
            
            # Re-raise the original exception to be handled by the API layer
            raise