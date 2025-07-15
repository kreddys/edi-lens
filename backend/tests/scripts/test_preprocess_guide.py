# FILE: backend/tests/scripts/test_preprocess_guide.py
import pytest
from pathlib import Path
from scripts.preprocess_guide import preprocess_guide, sanitize_filename

pytestmark = pytest.mark.unit

# --- Test Data Fixtures ---

# A controlled, miniature version of the guide text to test the basic chunking logic
SIMPLE_GUIDE_TEXT = """
This is the preamble and some introductory text.
It should all be captured in the first chunk.

ISA Interchange Control Header
This is the content for the ISA segment.
It has multiple lines.

CLM Claim Information
This is the content for the CLM segment.

REF Billing Provider Tax Identification
This is the first variant of the REF segment.

REF Payer Secondary Identification
This is the second, distinct variant of the REF segment.

2010AA Billing Provider Name Loop
This is the content for the 2010AA loop.

Overview
This is the table of contents.
2000A Billing Provider Hierarchical Level Loop
This should be part of the ToC.
"""

# A more complex slice focusing on repeated segment definitions (DTP)
REPEATING_SEGMENT_GUIDE_TEXT = """
DTP Date - Accident
Content for Accident Date.

DTP Date - Acute Manifestation
Content for Acute Manifestation Date.

DTP Date - Admission
Content for Admission Date.

PWK Claim Supplemental Information
Content for PWK segment.

Overview
This is the end.
"""

# A highly complex slice focusing on a nested loop structure
NESTED_LOOP_GUIDE_TEXT = """
2320 Other Subscriber Information Loop
Top-level content for Loop 2320.

SBR Other Subscriber Information
Content for the SBR segment within Loop 2320.

CAS Claim Level Adjustments
Content for the CAS segment.

2330A Other Subscriber Name Loop
Content for the nested 2330A Loop.

NM1 Other Subscriber Name
Content for the NM1 segment within Loop 2330A.

2330B Other Payer Name Loop
Content for the nested 2330B Loop.

NM1 Other Payer Name
Content for the NM1 segment within Loop 2330B.

REF Other Payer Secondary Identifier
Content for the REF segment within Loop 2330B.

Overview
End of guide.
"""

# --- Test Cases ---

def test_preprocess_guide_creates_correct_chunks_simple(tmp_path: Path):
    """
    Tests that the preprocess_guide function correctly splits the guide
    into distinct files and handles variants of the same segment code.
    """
    # Arrange
    input_guide_path = tmp_path / "sample_guide.txt"
    input_guide_path.write_text(SIMPLE_GUIDE_TEXT)

    # Act
    output_dir, toc_content = preprocess_guide(input_guide_path)

    # Assert
    assert output_dir.is_dir()
    
    # Verify the Table of Contents was correctly extracted
    assert "Overview" in toc_content
    assert "2000A Billing Provider Hierarchical Level Loop" in toc_content
    assert "ISA Interchange Control Header" not in toc_content

    # Verify the created chunk files
    chunk_filenames = {f.name for f in output_dir.glob("*.txt")}
    
    assert len(chunk_filenames) == 6, f"Expected 6 chunk files, but found {len(chunk_filenames)}"
    assert "Preamble.txt" in chunk_filenames
    assert "CLM_Claim_Information.txt" in chunk_filenames
    assert "REF_Billing_Provider_Tax_Identification.txt" in chunk_filenames
    assert "REF_Payer_Secondary_Identification.txt" in chunk_filenames
    assert "2010AA_Billing_Provider_Name.txt" in chunk_filenames

    # Spot-check content to ensure no bleed-over
    clm_content = (output_dir / "CLM_Claim_Information.txt").read_text()
    assert "CLM Claim Information" in clm_content
    assert "REF Billing Provider" not in clm_content

# --- NEW MEDIUM COMPLEXITY TEST ---
def test_preprocess_guide_handles_repeating_segment_variants(tmp_path: Path):
    """
    Tests that multiple definitions for the same segment code (DTP) are
    correctly chunked into separate files based on their full descriptions.
    """
    # Arrange
    input_guide_path = tmp_path / "dtp_guide.txt"
    input_guide_path.write_text(REPEATING_SEGMENT_GUIDE_TEXT)

    # Act
    output_dir, _ = preprocess_guide(input_guide_path)

    # Assert
    chunk_filenames = {f.name for f in output_dir.glob("*.txt")}
    
    # Preamble is empty in this text, so it's skipped. Expect 4 chunks.
    assert len(chunk_filenames) == 4
    
    # Check that each DTP variant was created as a unique file
    assert "DTP_Date_-_Accident.txt" in chunk_filenames
    assert "DTP_Date_-_Acute_Manifestation.txt" in chunk_filenames
    assert "DTP_Date_-_Admission.txt" in chunk_filenames
    assert "PWK_Claim_Supplemental_Information.txt" in chunk_filenames

    # Check content of one of the variant files
    admission_content = (output_dir / "DTP_Date_-_Admission.txt").read_text()
    assert "Content for Admission Date." in admission_content
    assert "Content for Accident Date." not in admission_content


# --- NEW HIGH COMPLEXITY TEST ---
def test_preprocess_guide_handles_nested_loop_definitions(tmp_path: Path):
    """
    Tests that the pre-processor correctly identifies and chunks definitions
    that appear sequentially but represent a nested hierarchy (e.g., Loop -> Segment -> Loop -> Segment).
    """
    # Arrange
    input_guide_path = tmp_path / "nested_guide.txt"
    input_guide_path.write_text(NESTED_LOOP_GUIDE_TEXT)

    # Act
    output_dir, _ = preprocess_guide(input_guide_path)

    # Assert
    chunk_filenames = {f.name for f in output_dir.glob("*.txt")}

    # Preamble is empty, so it's skipped. Expect 8 chunks.
    expected_files = {
        "2320_Other_Subscriber_Information.txt",
        "SBR_Other_Subscriber_Information.txt",
        "CAS_Claim_Level_Adjustments.txt",
        "2330A_Other_Subscriber_Name.txt",
        "NM1_Other_Subscriber_Name.txt",
        "2330B_Other_Payer_Name.txt",
        "NM1_Other_Payer_Name.txt",
        "REF_Other_Payer_Secondary_Identifier.txt"
    }
    
    assert len(chunk_filenames) == 8
    assert chunk_filenames == expected_files

    # Check content of a deeply nested definition
    ref_content = (output_dir / "REF_Other_Payer_Secondary_Identifier.txt").read_text()
    assert "Content for the REF segment within Loop 2330B" in ref_content

    # Check content of a mid-level definition
    sbr_content = (output_dir / "SBR_Other_Subscriber_Information.txt").read_text()
    assert "Content for the SBR segment within Loop 2320" in sbr_content
    assert "Content for the nested 2330A Loop" not in sbr_content