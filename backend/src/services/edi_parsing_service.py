# FILE: backend/src/services/edi_parsing_service.py

import logging
from typing import List

from src.core.edi_parser import EdiParser
from src.core.schema_manager import SchemaManager
from src.api.schemas import EdiSegment, EdiElement

logger = logging.getLogger(__name__)

class EdiParsingService:
    """Service for parsing EDI documents."""

    def __init__(self):
        self.schema_manager = SchemaManager()

    async def parse_edi(self, edi_content: str, schema_name: str, tenant_id: str) -> List[EdiSegment]:
        """
        Parse an EDI document and return its structure.

        Args:
            edi_content: The EDI document content.
            schema_name: The name of the schema to use for parsing.
            tenant_id: The tenant identifier.

        Returns:
            A list of EdiSegment objects representing the parsed document.
        """
        try:
            logger.info(f"Starting EDI parsing with schema: {schema_name}")

            schema = self.schema_manager.get_schema(schema_name, tenant_id)
            if not schema:
                raise ValueError(f"Schema not found: {schema_name}")

            parser = EdiParser(edi_content, schema)
            interchange = parser.parse()

            if parser.errors:
                raise ValueError(f"EDI parsing completed with errors: {[e.message for e in parser.errors]}")

            # Convert the parsed interchange into a list of EdiSegment objects
            edi_segments = []

            # Add ISA header
            edi_segments.append(
                EdiSegment(
                    id=interchange.header.segment_id,
                    elements=[EdiElement(value=element.value) for element in interchange.header.elements],
                    line_number=interchange.header.line_number,
                )
            )

            def _extract_segments_from_loop(loop):
                for segment in loop.segments:
                    edi_segments.append(
                        EdiSegment(
                            id=segment.segment_id,
                            elements=[EdiElement(value=element.value) for element in segment.elements],
                            line_number=segment.line_number,
                        )
                    )
                for sub_loop_list in loop.loops.values():
                    for sub_loop in sub_loop_list:
                        _extract_segments_from_loop(sub_loop)

            for functional_group in interchange.functional_groups:
                for transaction in functional_group.transactions:
                    _extract_segments_from_loop(transaction.body)

            # Add IEA trailer
            edi_segments.append(
                EdiSegment(
                    id=interchange.trailer.segment_id,
                    elements=[EdiElement(value=element.value) for element in interchange.trailer.elements],
                    line_number=interchange.trailer.line_number,
                )
            )

            logger.info(f"EDI parsing completed successfully.")
            return edi_segments

        except Exception as e:
            logger.error(f"EDI parsing failed: {e}", exc_info=True)
            raise