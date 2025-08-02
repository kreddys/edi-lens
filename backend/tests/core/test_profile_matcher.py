import pytest
from unittest.mock import MagicMock, AsyncMock

from src.core.profile_matcher import ProfileMatcher
from src.models import partner_profile
from src.models.profile_criterion import FieldSource, Operator, ProfileCriterion

pytestmark = [pytest.mark.unit]

# --- THIS IS THE FIX ---
# A realistic, 106-character ISA segment with standard delimiters.
# The element separator is '*' (at index 3) and the segment terminator is '~' (at index 105).
TEST_EDI = (
    "ISA*00*          *00*          *ZZ*SENDER_ID      *ZZ*RECEIVER_ID    *240718*1200*^*00501*000000001*0*P*:~"
    "GS*HC*SENDER_CODE*RECEIVER_CODE*20240718*1200*1*X*005010X222A1~"
)
# --- END OF FIX ---

@pytest.mark.asyncio
async def test_matcher_selects_highest_priority_profile():
    # Arrange
    profile_low_priority = partner_profile.PartnerProfile(
        id=2, name="Low Prio", priority=20, criteria=[] # Catch-all
    )
    profile_high_priority = partner_profile.PartnerProfile(
        id=1, name="High Prio", priority=10,
        criteria=[
            ProfileCriterion(field_source=FieldSource.GS, field_identifier="02", operator=Operator.EQUALS, value="SENDER_CODE")
        ]
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [profile_high_priority, profile_low_priority]
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    matcher = ProfileMatcher(mock_db)
    
    # Act
    matched_profile = await matcher.match(TEST_EDI, "tenant-a")

    # Assert
    assert matched_profile is not None
    assert matched_profile.id == 1
    assert matched_profile.name == "High Prio"

@pytest.mark.asyncio
async def test_matcher_falls_back_to_lower_priority_if_first_fails():
    # Arrange
    profile_low_priority_match = partner_profile.PartnerProfile(
        id=2, name="Low Prio Match", priority=20,
        criteria=[
             # NOTE: ISA08 in the test EDI is 'RECEIVER_ID    ' with padding. We match exactly.
             ProfileCriterion(field_source=FieldSource.ISA, field_identifier="08", operator=Operator.EQUALS, value="RECEIVER_ID    ")
        ]
    )
    profile_high_priority_no_match = partner_profile.PartnerProfile(
        id=1, name="High Prio No Match", priority=10,
        criteria=[
            ProfileCriterion(field_source=FieldSource.GS, field_identifier="02", operator=Operator.EQUALS, value="WRONG_SENDER_CODE")
        ]
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [profile_high_priority_no_match, profile_low_priority_match]
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    matcher = ProfileMatcher(mock_db)
    
    # Act
    matched_profile = await matcher.match(TEST_EDI, "tenant-a")

    # Assert
    assert matched_profile is not None
    assert matched_profile.id == 2
    assert matched_profile.name == "Low Prio Match"

@pytest.mark.asyncio
async def test_matcher_returns_none_if_no_profiles_match():
    # Arrange
    profile_no_match = partner_profile.PartnerProfile(
        id=1, name="No Match", priority=10,
        criteria=[
            ProfileCriterion(field_source=FieldSource.GS, field_identifier="02", operator=Operator.EQUALS, value="WRONG_SENDER_CODE")
        ]
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [profile_no_match]
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    matcher = ProfileMatcher(mock_db)
    
    # Act
    matched_profile = await matcher.match(TEST_EDI, "tenant-a")

    # Assert
    assert matched_profile is None