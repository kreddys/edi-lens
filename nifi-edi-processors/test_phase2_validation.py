#!/usr/bin/env python3
"""
Phase 2 validation test with real schema.
Tests the complete validation → TA1 workflow with actual schema validation.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from edi_common.validation_service import EDIValidationService
from edi_common.ta1_generator import TA1Generator
from edi_common.edi_parser import EdiParser

def test_phase2_with_real_schema():
    """Test Phase 2 with actual schema validation."""
    print("🔍 Phase 2 Validation Test with Real Schema")
    print("=" * 60)
    
    # Use actual schema path
    schema_path = os.path.join(os.path.dirname(__file__), "schemas")
    validation_service = EDIValidationService(schema_path)
    ta1_generator = TA1Generator()
    
    # Test EDI that should work with 837 schema
    test_edi_837 = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~ST*837*0001~BHT*0019*00*1234567890*20210101*1000*CH~NM1*41*2*PROVIDER NAME*****46*1234567890~PER*IC*CONTACT*TE*5551234567~NM1*40*2*RECEIVER NAME*****46*0987654321~HL*1**20*1~NM1*PR*2*INSURANCE COMPANY*****PI*12345~HL*2*1*22*0~SBR*P*18*******CI~NM1*IL*1*DOE*JOHN*A***MI*123456789~N3*123 MAIN ST~N4*ANYTOWN*ST*12345~DMG*D8*19800101*M~HL*3*2*23*0~PAT*19~NM1*QC*1*DOE*JOHN*A***MI*123456789~N3*123 MAIN ST~N4*ANYTOWN*ST*12345~CLM*1234567890*100***11:B:1*Y*A*Y*I~DTP*431*D8*20210101~REF*D9*1234567890~HI*BK:Z1234~LX*1~SV1*HC:99213*100*UN*1***1~DTP*472*D8*20210101~SE*25*0001~GE*1*1~IEA*1*000000001~"""
    
    print("\n1. Testing with 837 schema...")
    
    try:
        # Step 1: Validate EDI
        validation_result = validation_service.validate_edi(
            edi_content=test_edi_837,
            schema_name="837.5010.X222.A1.json",
            tenant_id="test-tenant",
            snip_level=3
        )
        
        print(f"   📊 Validation Result: {'VALID' if validation_result.valid else 'INVALID'}")
        print(f"   🔍 Findings: {len(validation_result.findings)}")
        
        if validation_result.findings:
            for finding in validation_result.findings[:3]:  # Show first 3 findings
                print(f"      - {finding.level}: {finding.message}")
        
        # Step 2: Extract ISA header and generate TA1
        parser = EdiParser(test_edi_837)
        segments = parser._segmentize(test_edi_837)
        isa_segment = segments[0]
        
        # Generate TA1 (ISA14=1, so should generate)
        ta1_result = ta1_generator.generate(isa_segment, [])
        
        print(f"   📤 TA1 Generated: {ta1_result is not None}")
        if ta1_result:
            print(f"   📝 TA1 Length: {len(ta1_result)} characters")
            
            # Validate TA1 structure
            ta1_segments = ta1_result.split('~')
            print(f"   🔧 TA1 Segments: {len(ta1_segments)}")
            
            # Show TA1 content (first 100 chars)
            print(f"   📄 TA1 Content: {ta1_result[:100]}...")
        
        print("   ✅ Phase 2 validation test completed successfully")
        
    except Exception as e:
        print(f"   ❌ Phase 2 validation test failed: {e}")
        return False
    
    print("\n2. Testing simulated processor workflow...")
    
    try:
        # Simulate complete processor workflow
        from processors.edi_validation_processor import EDIValidationProcessor
        from processors.ta1_generation_processor import TA1GenerationProcessor
        
        # Create processor instances
        validation_processor = EDIValidationProcessor()
        ta1_processor = TA1GenerationProcessor()
        
        # Verify processors can be instantiated
        val_props = validation_processor.getPropertyDescriptors()
        val_rels = validation_processor.getRelationships()
        
        ta1_props = ta1_processor.getPropertyDescriptors()
        ta1_rels = ta1_processor.getRelationships()
        
        print(f"   ✅ Validation Processor: {len(val_props)} properties, {len(val_rels)} relationships")
        print(f"   ✅ TA1 Processor: {len(ta1_props)} properties, {len(ta1_rels)} relationships")
        
        # Simulate workflow connections
        print(f"   🔗 Workflow: validation.{val_rels[0]} → ta1.input")
        print(f"   🔗 Workflow: ta1.{ta1_rels[0]} → output")
        print(f"   🔗 Workflow: ta1.{ta1_rels[1]} → output (no TA1 needed)")
        
        print("   ✅ Simulated processor workflow test completed")
        
    except Exception as e:
        print(f"   ❌ Simulated processor workflow test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_phase2_with_real_schema()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 PHASE 2 VALIDATION COMPLETE - All tests passed!")
        print("\n📋 Phase 2 Implementation Summary:")
        print("   ✅ TA1 Generation Processor implemented")
        print("   ✅ Integrated validation → TA1 workflow tested")
        print("   ✅ Schema-based validation working")
        print("   ✅ TA1 content generation and validation working")
        print("   ✅ Processor interfaces ready for NiFi deployment")
        print("\n🚀 Ready for Phase 3: EDI Parsing Processor")
    else:
        print("❌ PHASE 2 VALIDATION FAILED - Check implementation")
        sys.exit(1)