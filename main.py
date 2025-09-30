#!/usr/bin/env python3
"""
EDI Parser Command Line Tool

Pars        # Parse the EDI content
        print("\nParsing EDI content...")
        parser = EdiParser(edi_string=edi_content, schema=schema)
        result = parser.parse()
        print("EDI parsed successfully!") files to JSON format with validation.

Usage:
    python main.py                                          # Use sample file
    python main.py input.edi                               # Parse input.edi to JSON
    python main.py input.edi output.json                   # Parse to specific output file
    python main.py input.edi output.json schema.json       # Use specific schema
"""

import argparse
import json
import sys
from pathlib import Path

# Try importing from installed package first, fallback to src path
try:
    from edi_parser import EdiParser
    from edi_schema_models import ImplementationGuideSchema
    from validation_service import EDIValidationService
except ImportError:
    # Add src to path for imports when not installed
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from edi_parser import EdiParser
    from edi_schema_models import ImplementationGuideSchema
    from validation_service import EDIValidationService


def load_schema(schema_name: str = "837.5010.X222.A1.json") -> ImplementationGuideSchema:
    """Load an EDI schema from the schemas directory."""
    schema_path = Path("src/schemas") / schema_name
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r') as f:
        schema_data = json.load(f)
        return ImplementationGuideSchema.model_validate(schema_data)


def parse_edi_file(input_file: str, output_file: str, schema_name: str = "837.5010.X222.A1.json") -> int:
    """Parse an EDI file and save results to JSON."""
    
    print(f"EDI Parser - Processing {input_file}")
    print("=" * 50)
    
    try:
        # Load input EDI file
        print(f"Loading EDI file: {input_file}")
        with open(input_file, 'r') as f:
            edi_content = f.read().strip()
        print(f"Loaded {len(edi_content)} characters")
        
        # Load schema
        print(f"Loading schema: {schema_name}")
        schema = load_schema(schema_name)
        print("Schema loaded successfully!")
        
        # Parse the EDI content
        print("\n� Parsing EDI content...")
        parser = EdiParser(edi_string=edi_content, schema=schema)
        result = parser.parse()
        print("EDI parsed successfully!")
        
        # Display parsing results
        print(f"\nParsing Results:")
        print(f"  Interchange Control Number: {result.header.get_element(13)}")
        print(f"  Sender ID: {result.header.get_element(6)}")  
        print(f"  Receiver ID: {result.header.get_element(8)}")
        print(f"  Functional Groups: {len(result.functional_groups)}")
        
        if result.functional_groups:
            fg = result.functional_groups[0]
            print(f"  Transaction Sets: {len(fg.transactions)}")
            if fg.transactions:
                txn = fg.transactions[0]
                print(f"  Total Segments: {len(txn.body.segments)}")
                print(f"  Total Loops: {sum(len(loops) for loops in txn.body.loops.values())}")
            
        # Run validation
        print("\nRunning EDI validation...")
        validator = EDIValidationService(schema_base_path="src/schemas")
        validation_result = validator.validate_edi(edi_content, schema_name)
        
        if validation_result.valid:
            print("EDI is valid according to schema!")
        else:
            print(f"EDI validation found {len(validation_result.findings)} issues:")
            for i, finding in enumerate(validation_result.findings[:5]):  # Show first 5 findings
                print(f"  {i+1}. {finding.message}")
            if len(validation_result.findings) > 5:
                print(f"  ... and {len(validation_result.findings) - 5} more issues")
        
        # Convert to JSON
        print(f"\nGenerating JSON output...")
        json_output = result.model_dump_json(indent=2)
        
        # Write output file
        with open(output_file, 'w') as f:
            f.write(json_output)
        
        print(f"JSON output saved to: {output_file}")
        print(f"Output size: {len(json_output):,} characters")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}")
        return 1
    except Exception as e:
        print(f"Error during EDI processing: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point with command line argument parsing."""
    
    parser = argparse.ArgumentParser(
        description="Parse EDI files to JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Use sample_837p.edi
  python main.py claims.edi                        # Parse claims.edi -> claims.json  
  python main.py claims.edi output.json            # Parse to specific output
  python main.py claims.edi output.json custom.json   # Use custom schema
        """
    )
    
    parser.add_argument('input_file', nargs='?', default='sample_837p.edi',
                       help='Input EDI file (default: sample_837p.edi)')
    parser.add_argument('output_file', nargs='?', 
                       help='Output JSON file (default: input_file.json)')
    parser.add_argument('schema_file', nargs='?', default='837.5010.X222.A1.json',
                       help='Schema file (default: 837.5010.X222.A1.json)')
    
    args = parser.parse_args()
    
    # Set default output file if not provided
    if not args.output_file:
        input_path = Path(args.input_file)
        args.output_file = str(input_path.with_suffix('.json'))
    
    # Check if input file exists
    if not Path(args.input_file).exists():
        print(f"Error: Input file not found: {args.input_file}")
        if args.input_file == 'sample_837p.edi':
            print("No sample file found. Create one or specify an existing EDI file.")
            print("Example: python main.py your_edi_file.edi")
        return 1
    
    return parse_edi_file(args.input_file, args.output_file, args.schema_file)


if __name__ == "__main__":
    exit(main())