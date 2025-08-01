import json
import argparse
from pathlib import Path
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def add_missing_contextual_definitions(input_path: Path, output_path: Path):
    """
    Reads a schema file, adds missing contextual definitions based on the 
    error report from review_schema.py, and writes the result to a new file.
    """
    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Reading schema from: {input_path}")
    with open(input_path, 'r') as f:
        schema_data = json.load(f)

    if "contextualDefinitions" not in schema_data:
        logging.error("No 'contextualDefinitions' key found in the schema.")
        return

    context_defs = schema_data["contextualDefinitions"]
    
    # Define the missing contextual definitions based on the error report
    missing_definitions = {
        "2400.DTP_ServiceDate": {
            "id": "2400.DTP_ServiceDate",
            "name": "Date - Service Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "472",
                            "description": "Service"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_PrescriptionDate": {
            "id": "2400.DTP_PrescriptionDate",
            "name": "Date - Prescription Date", 
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "471",
                            "description": "Prescription"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_CertificationRevisionDate": {
            "id": "2400.DTP_CertificationRevisionDate",
            "name": "Date - Certification Revision/Recertification Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "607",
                            "description": "Revision/Recertification"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_BeginTherapyDate": {
            "id": "2400.DTP_BeginTherapyDate",
            "name": "Date - Begin Therapy Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "463",
                            "description": "Begin Therapy"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_LastCertificationDate": {
            "id": "2400.DTP_LastCertificationDate",
            "name": "Date - Last Certification Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "461",
                            "description": "Last Certification"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_LastSeenDate": {
            "id": "2400.DTP_LastSeenDate",
            "name": "Date - Last Seen Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "304",
                            "description": "Latest Visit or Consultation"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_TestDate": {
            "id": "2400.DTP_TestDate",
            "name": "Date - Test Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "738",
                            "description": "Test"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_ShippedDate": {
            "id": "2400.DTP_ShippedDate",
            "name": "Date - Shipped Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "011",
                            "description": "Shipped"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_LastXRayDate": {
            "id": "2400.DTP_LastXRayDate",
            "name": "Date - Last X-ray Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "455",
                            "description": "Last X-Ray"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.DTP_InitialTreatmentDate": {
            "id": "2400.DTP_InitialTreatmentDate",
            "name": "Date - Initial Treatment Date",
            "elements": {
                "DTP01": {
                    "valid_codes": [
                        {
                            "code": "454",
                            "description": "Initial Treatment"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_RepricedLineItem": {
            "id": "2400.REF_RepricedLineItem",
            "name": "Repriced Line Item Reference Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "9B",
                            "description": "Repriced Line Item Reference Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_AdjustedRepricedLineItem": {
            "id": "2400.REF_AdjustedRepricedLineItem",
            "name": "Adjusted Repriced Line Item Reference Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "9D",
                            "description": "Adjusted Repriced Line Item Reference Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_PriorAuth": {
            "id": "2400.REF_PriorAuth",
            "name": "Prior Authorization",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "G1",
                            "description": "Prior Authorization Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_LineItemControl": {
            "id": "2400.REF_LineItemControl",
            "name": "Line Item Control Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "6R",
                            "description": "Line Item Control Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_MammographyCert": {
            "id": "2400.REF_MammographyCert",
            "name": "Mammography Certification Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "ZZ",
                            "description": "Mammography Certification Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_CLIA": {
            "id": "2400.REF_CLIA",
            "name": "Clinical Laboratory Improvement Amendment (CLIA) Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "X4",
                            "description": "Clinical Laboratory Improvement Amendment Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_ReferringCLIA": {
            "id": "2400.REF_ReferringCLIA",
            "name": "Referring Clinical Laboratory Improvement Amendment (CLIA) Facility Identification",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "F4",
                            "description": "Referring CLIA Facility Identification"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_ImmunizationBatch": {
            "id": "2400.REF_ImmunizationBatch",
            "name": "Immunization Batch Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "BT",
                            "description": "Batch Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        },
        "2400.REF_Referral": {
            "id": "2400.REF_Referral",
            "name": "Referral Number",
            "elements": {
                "REF01": {
                    "valid_codes": [
                        {
                            "code": "9F",
                            "description": "Referral Number"
                        }
                    ],
                    "is_identifier": True
                }
            }
        }
    }

    added_count = 0
    
    logging.info(f"Adding {len(missing_definitions)} missing contextual definitions...")
    
    for def_id, definition in missing_definitions.items():
        if def_id not in context_defs:
            context_defs[def_id] = definition
            logging.info(f"  -> Added contextual definition: {def_id}")
            added_count += 1
        else:
            logging.info(f"  -> Skipping {def_id} (already exists)")

    logging.info(f"Total definitions added: {added_count}")

    logging.info(f"Writing updated schema to: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(schema_data, f, indent=2)
    
    logging.info("Script finished successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add missing contextual definitions to an EDI schema.")
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Path to the input schema JSON file."
    )
    parser.add_argument(
        "--output-file", 
        type=Path,
        required=True,
        help="Path to write the modified schema JSON file."
    )
    args = parser.parse_args()
    
    add_missing_contextual_definitions(args.input_file, args.output_file)