# FILE: backend/tests/core/test_profile_matcher.py

import pytest
from unittest.mock import AsyncMock

from src.core.profile_matcher import ProfileMatcher
from src.models.partner_profile import PartnerProfile

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]

@pytest.mark.asyncio
async def test_match_by_filename_selects_correct_profile():
    """Tests that the matcher finds the correct profile based on a filename pattern."""
    # Arrange
    profile1 = PartnerProfile(id=1, name="Claims Profile", priority=10, file_name_patterns='["claims_*.edi"]')
    profile2 = PartnerProfile(id=2, name="Remits Profile", priority=20, file_name_patterns='["remits_*.x12"]')
    
    matcher = ProfileMatcher(db_session=AsyncMock())
    matcher.list_tenant_profiles = AsyncMock(return_value=[profile1, profile2])

    # Act
    matched_profile = await matcher.match_by_filename("tenant-a", "claims_12345.edi")

    # Assert
    assert matched_profile is not None
    assert matched_profile.id == 1
    assert matched_profile.name == "Claims Profile"

@pytest.mark.asyncio
async def test_match_by_filename_respects_priority():
    """Tests that the highest priority (lowest number) profile is chosen when multiple patterns match."""
    # Arrange
    profile_catch_all = PartnerProfile(id=2, name="Catch All EDI", priority=20, file_name_patterns='["*.edi"]')
    profile_specific = PartnerProfile(id=1, name="Specific Claims", priority=10, file_name_patterns='["claims_*.edi"]')
    
    matcher = ProfileMatcher(db_session=AsyncMock())
    # The list_tenant_profiles method should return them pre-sorted by priority
    matcher.list_tenant_profiles = AsyncMock(return_value=[profile_specific, profile_catch_all])

    # Act
    matched_profile = await matcher.match_by_filename("tenant-a", "claims_54321.edi")

    # Assert
    assert matched_profile is not None
    assert matched_profile.id == 1
    assert matched_profile.name == "Specific Claims"

@pytest.mark.asyncio
async def test_match_by_filename_returns_none_for_no_match():
    """Tests that None is returned when no profile's patterns match the filename."""
    # Arrange
    profile1 = PartnerProfile(id=1, name="Claims", priority=10, file_name_patterns='["claims_*.edi"]')
    
    matcher = ProfileMatcher(db_session=AsyncMock())
    matcher.list_tenant_profiles = AsyncMock(return_value=[profile1])

    # Act
    matched_profile = await matcher.match_by_filename("tenant-a", "unmatched_file.txt")

    # Assert
    assert matched_profile is None

@pytest.mark.asyncio
async def test_match_by_filename_handles_invalid_json_patterns_gracefully():
    """Tests that a malformed file_name_patterns JSON string does not crash the matcher."""
    # Arrange
    profile_good = PartnerProfile(id=2, name="Good Profile", priority=20, file_name_patterns='["good_*.edi"]')
    profile_bad = PartnerProfile(id=1, name="Bad JSON Profile", priority=10, file_name_patterns='["bad_json_patterns') # Invalid JSON
    
    matcher = ProfileMatcher(db_session=AsyncMock())
    matcher.list_tenant_profiles = AsyncMock(return_value=[profile_bad, profile_good])

    # Act
    # The matcher should skip the bad profile and correctly match the good one
    matched_profile = await matcher.match_by_filename("tenant-a", "good_file.edi")

    # Assert
    assert matched_profile is not None
    assert matched_profile.id == 2
    assert matched_profile.name == "Good Profile"

@pytest.mark.asyncio
async def test_match_by_filename_returns_none_if_no_profiles_exist():
    """Tests that None is returned if the tenant has no profiles configured."""
    # Arrange
    matcher = ProfileMatcher(db_session=AsyncMock())
    matcher.list_tenant_profiles = AsyncMock(return_value=[])

    # Act
    matched_profile = await matcher.match_by_filename("tenant-a", "any_file.edi")

    # Assert
    assert matched_profile is None