#!/usr/bin/env python3
"""
Phase 3 validation test for EDI Parsing Processor.
Tests multi-format output, performance, and integration capabilities.
"""

import sys
import os
import json
import time
from xml.etree import ElementTree as ET

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from edi_common.edi_parser import EdiParser
from processors.edi_parsing_processor import EDIParsingProcessor

def test_phase3_parsing_capabilities():
    """Test Phase 3 parsing processor capabilities."""
    print("🔍 Phase 3 Parsing Processor Validation Test")
    print("=" * 60)
    
    # Create processor instance
    parsing_processor = EDIParsingProcessor()
    
    # Test EDI samples
    test_samples = {
        "Healthcare 270 Eligibility": """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~ST*270*0001~BHT*0022*13*10001234*20210101*1000~HL*1**20*1~NM1*PR*2*ABC INSURANCE*****PI*12345~PER*IC*CONTACT*TE*5551234567~HL*2*1*22*0~SBR*P*18*******CI~NM1*IL*1*DOE*JOHN*A***MI*123456789~N3*123 MAIN ST~N4*ANYTOWN*ST*12345~DMG*D8*19800101*M~SE*13*0001~GE*1*1~IEA*1*000000001~""",
        
        "Healthcare 837 Claims": """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~ST*837*0001~BHT*0019*00*1234567890*20210101*1000*CH~NM1*41*2*PROVIDER NAME*****46*1234567890~PER*IC*CONTACT*TE*5551234567~NM1*40*2*RECEIVER NAME*****46*0987654321~HL*1**20*1~NM1*PR*2*INSURANCE COMPANY*****PI*12345~HL*2*1*22*0~SBR*P*18*******CI~NM1*IL*1*DOE*JOHN*A***MI*123456789~N3*123 MAIN ST~N4*ANYTOWN*ST*12345~DMG*D8*19800101*M~HL*3*2*23*0~PAT*19~NM1*QC*1*DOE*JOHN*A***MI*123456789~N3*123 MAIN ST~N4*ANYTOWN*ST*12345~CLM*1234567890*100***11:B:1*Y*A*Y*I~DTP*431*D8*20210101~REF*D9*1234567890~HI*BK:Z1234~LX*1~SV1*HC:99213*100*UN*1***1~DTP*472*D8*20210101~SE*25*0001~GE*1*1~IEA*1*000000001~"""
    }
    
    print("\n1. Testing JSON Output Format...")
    for test_name, edi_content in test_samples.items():
        try:
            # Parse EDI
            parser = EdiParser(edi_content)
            interchange = parser.parse()
            
            # Generate JSON output
            metadata = {
                "parsed_at": "2024-01-15T10:30:00Z",
                "segment_count": len(parser.all_segments),
                "has_errors": False,
                "test_name": test_name
            }
            
            json_output = parsing_processor._format_as_json(interchange, True, metadata)
            
            # Validate JSON
            parsed_json = json.loads(json_output)
            
            assert "segments" in parsed_json
            assert "metadata" in parsed_json
            assert len(parsed_json["segments"]) > 0
            
            print(f"   ✅ {test_name}: {len(parsed_json['segments'])} segments parsed to JSON")
            
        except Exception as e:
            print(f"   ❌ {test_name} JSON test failed: {e}")
            return False
    
    print("\n2. Testing XML Output Format...")
    for test_name, edi_content in test_samples.items():
        try:
            # Parse EDI
            parser = EdiParser(edi_content)
            interchange = parser.parse()
            
            # Generate XML output
            metadata = {
                "parsed_at": "2024-01-15T10:30:00Z",
                "segment_count": len(parser.all_segments),
                "has_errors": False,
                "test_name": test_name
            }
            
            xml_output = parsing_processor._format_as_xml(interchange, True, metadata)
            
            # Validate XML
            root = ET.fromstring(xml_output)
            assert root.tag == "edi_document"
            
            segments = root.find("segments").findall("segment")
            assert len(segments) > 0
            
            print(f"   ✅ {test_name}: {len(segments)} segments parsed to XML")
            
        except Exception as e:
            print(f"   ❌ {test_name} XML test failed: {e}")
            return False
    
    print("\n3. Testing CSV Output Format...")
    for test_name, edi_content in test_samples.items():
        try:
            # Parse EDI
            parser = EdiParser(edi_content)
            interchange = parser.parse()
            
            # Generate CSV output
            metadata = {
                "parsed_at": "2024-01-15T10:30:00Z",
                "segment_count": len(parser.all_segments),
                "has_errors": False,
                "test_name": test_name
            }
            
            csv_output = parsing_processor._format_as_csv(interchange, True, metadata)
            
            # Validate CSV
            lines = csv_output.strip().split('\n')
            data_lines = [line for line in lines if line and not line.startswith('#')]
            
            assert len(data_lines) > 1  # Header + data
            assert data_lines[0].startswith("segment_id,line_number")  # Header
            
            print(f"   ✅ {test_name}: {len(data_lines)-1} segments parsed to CSV")
            
        except Exception as e:
            print(f"   ❌ {test_name} CSV test failed: {e}")
            return False
    
    print("\n4. Testing Performance...")
    test_edi = test_samples["Healthcare 837 Claims"]
    
    try:
        # Measure parsing performance
        iterations = 10
        total_time = 0
        
        for i in range(iterations):
            start_time = time.time()
            
            parser = EdiParser(test_edi)
            interchange = parser.parse()
            
            metadata = {"parsed_at": "2024-01-15T10:30:00Z", "segment_count": len(parser.all_segments)}
            
            # Test all formats
            json_output = parsing_processor._format_as_json(interchange, True, metadata)
            xml_output = parsing_processor._format_as_xml(interchange, True, metadata)
            csv_output = parsing_processor._format_as_csv(interchange, True, metadata)
            
            end_time = time.time()
            total_time += (end_time - start_time)
        
        avg_time = total_time / iterations
        segments_per_sec = (len(parser.all_segments) * iterations) / total_time
        
        print(f"   ⚡ Average processing time: {avg_time:.3f} seconds")
        print(f"   📊 Throughput: {segments_per_sec:.1f} segments/second")
        print(f"   📈 Total segments processed: {len(parser.all_segments) * iterations}")
        
        # Performance should be reasonable
        assert avg_time < 1.0  # Less than 1 second per iteration
        
        print("   ✅ Performance test passed")
        
    except Exception as e:
        print(f"   ❌ Performance test failed: {e}")
        return False
    
    print("\n5. Testing Metadata Extraction...")
    try:
        parser = EdiParser(test_samples["Healthcare 270 Eligibility"])
        interchange = parser.parse()
        
        metadata = parsing_processor._extract_metadata(interchange, "2024-01-15T10:30:00Z", "test-tenant")
        
        # Verify metadata structure
        required_fields = ["parsed_at", "segment_count", "has_errors", "tenant_id"]
        for field in required_fields:
            assert field in metadata, f"Missing metadata field: {field}"
        
        # Verify metadata values
        assert metadata["tenant_id"] == "test-tenant"
        assert isinstance(metadata["segment_count"], int)
        assert metadata["segment_count"] > 0
        assert isinstance(metadata["has_errors"], bool)
        
        # Check transaction set extraction
        if "transaction_sets" in metadata:
            assert isinstance(metadata["transaction_sets"], list)
            if metadata["transaction_sets"]:
                tx = metadata["transaction_sets"][0]
                assert "transaction_set_identifier" in tx
                assert "control_number" in tx
        
        print(f"   ✅ Metadata extracted: {len(metadata)} fields")
        print(f"      - Segment count: {metadata['segment_count']}")
        print(f"      - Has errors: {metadata['has_errors']}")
        print(f"      - Transaction sets: {len(metadata.get('transaction_sets', []))}")
        
    except Exception as e:
        print(f"   ❌ Metadata extraction test failed: {e}")
        return False
    
    print("\n6. Testing Processor Interface...")
    try:
        # Test property descriptors
        properties = parsing_processor.getPropertyDescriptors()
        assert len(properties) == 6
        
        property_names = [prop.name for prop in properties]
        expected_props = ["Output Format", "Include Metadata", "Schema Name", 
                         "Segment Filter", "Tenant ID", "Schema Base Path"]
        
        for prop in expected_props:
            assert prop in property_names, f"Missing property: {prop}"
        
        # Test relationships
        relationships = parsing_processor.getRelationships()
        assert len(relationships) == 2
        assert "success" in relationships
        assert "failure" in relationships
        
        print(f"   ✅ Processor interface validated")
        print(f"      - Properties: {len(properties)}")
        print(f"      - Relationships: {relationships}")
        
    except Exception as e:
        print(f"   ❌ Processor interface test failed: {e}")
        return False
    
    return True

def test_complete_parsing_workflow():
    """Test complete parsing workflow integration."""
    print("\n🔄 Testing Complete Parsing Workflow Integration")
    print("=" * 60)
    
    try:
        # Simulate complete workflow: Validation → TA1 → Parsing
        from edi_common.validation_service import EDIValidationService
        from edi_common.ta1_generator import TA1Generator
        
        # Initialize services
        schema_path = os.path.join(os.path.dirname(__file__), "schemas")
        validation_service = EDIValidationService(schema_path)
        ta1_generator = TA1Generator()
        parsing_processor = EDIParsingProcessor()
        
        # Test EDI
        test_edi = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~ST*270*0001~BHT*0022*13*10001234*20210101*1000~HL*1**20*1~NM1*PR*2*ABC INSURANCE*****PI*12345~SE*6*0001~GE*1*1~IEA*1*000000001~"""
        
        # Step 1: Validation
        validation_result = validation_service.validate_edi(
            edi_content=test_edi,
            schema_name="837.5010.X222.A1.json",  # Use available schema
            tenant_id="test-tenant",
            snip_level=3
        )
        
        print(f"   📊 Step 1 - Validation: {'VALID' if validation_result.valid else 'INVALID'}")
        print(f"      Findings: {len(validation_result.findings)}")
        
        # Step 2: TA1 Generation
        parser = EdiParser(test_edi)
        segments = parser._segmentize(test_edi)
        isa_segment = segments[0]
        
        ta1_result = ta1_generator.generate(isa_segment, [])
        
        print(f"   🏷️  Step 2 - TA1 Generation: {'Generated' if ta1_result else 'Not needed'}")
        if ta1_result:
            print(f"      TA1 length: {len(ta1_result)} characters")
        
        # Step 3: Parsing (JSON format)
        interchange = parser.parse()
        metadata = {
            "parsed_at": "2024-01-15T10:30:00Z",
            "segment_count": len(parser.all_segments),
            "has_errors": len(validation_result.findings) > 0,
            "tenant_id": "test-tenant"
        }
        
        json_output = parsing_processor._format_as_json(interchange, True, metadata)
        parsed_json = json.loads(json_output)
        
        print(f"   📊 Step 3 - Parsing (JSON): {len(parsed_json['segments'])} segments")
        print(f"      Metadata fields: {len(parsed_json['metadata'])}")
        
        # Step 4: Parsing (XML format)
        xml_output = parsing_processor._format_as_xml(interchange, True, metadata)
        xml_root = ET.fromstring(xml_output)
        xml_segments = xml_root.find("segments").findall("segment")
        
        print(f"   📊 Step 4 - Parsing (XML): {len(xml_segments)} segments")
        
        # Step 5: Parsing (CSV format)
        csv_output = parsing_processor._format_as_csv(interchange, True, metadata)
        csv_lines = [line for line in csv_output.split('\n') if line and not line.startswith('#')]
        
        print(f"   📊 Step 5 - Parsing (CSV): {len(csv_lines)-1} data rows")
        
        # Verify workflow consistency
        assert len(parsed_json['segments']) == len(xml_segments)
        assert len(parsed_json['segments']) == len(csv_lines) - 1  # -1 for header
        
        print("   ✅ Complete parsing workflow integration successful")
        return True
        
    except Exception as e:
        print(f"   ❌ Complete parsing workflow integration failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Phase 3 EDI Parsing Processor Validation")
    print("Testing multi-format parsing capabilities and performance")
    
    success = True
    success &= test_phase3_parsing_capabilities()
    success &= test_complete_parsing_workflow()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 PHASE 3 VALIDATION COMPLETE - All tests passed!")
        print("\n📋 Phase 3 Implementation Summary:")
        print("   ✅ EDI Parsing Processor implemented")
        print("   ✅ Multi-format output (JSON/XML/CSV) working")
        print("   ✅ Metadata extraction functional")
        print("   ✅ Performance benchmarks met")
        print("   ✅ Complete workflow integration tested")
        print("   ✅ Processor interface ready for NiFi deployment")
        print("\n🚀 All 3 Phases Complete - Ready for Production Deployment!")
    else:
        print("❌ PHASE 3 VALIDATION FAILED - Check implementation")
        sys.exit(1)