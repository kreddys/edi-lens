# FILE: backend/src/agents/refinement_engine/engine.py
import json
import logging
from typing import Generator, Dict, Any, List
from jsonpatch import JsonPatch, JsonPatchException, InvalidJsonPatch

from .models import KnowledgeSource, RefinementStatus
from src.agents.crews import SchemaEnrichmentCrews
from .embedding_models import PineconeEmbeddingModel
from src.core.config import settings
from src.utils.llm_output_parser import extract_json_from_llm_output

logger = logging.getLogger(__name__)

class SchemaRefinementEngine:
    """
    Orchestrates a multi-agent "assembly line" to generate and enrich an EDI schema
    from a textual implementation guide.
    """
    def __init__(self, base_schema: Dict[str, Any], knowledge_source: KnowledgeSource, guide_toc: str):
        self.schema = base_schema
        self.knowledge_source = knowledge_source
        self.guide_toc = guide_toc
        
        logger.info("Initializing embedding model and RAG tool...")
        embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
        from .rag_tool import RAGTool
        rag_tool = RAGTool(knowledge_source=self.knowledge_source, embedding_model=embedding_model)
        
        self.crews = SchemaEnrichmentCrews(rag_tool=rag_tool)
        logger.info("SchemaRefinementEngine initialized with specialized agent crews.")

    def _apply_patch(self, patch: List[Dict[str, Any]], description: str):
        """Applies a JSON patch to the in-memory schema and logs the outcome."""
        if not patch:
            logger.debug(f"Skipping patch for '{description}' as it is empty.")
            return
        try:
            self.schema = JsonPatch(patch).apply(self.schema)
            logger.info(f"Successfully applied patch for: {description}")
        except (JsonPatchException, InvalidJsonPatch) as e:
            logger.error(f"Failed to apply patch for {description}: {e}. Patch was: {patch}", exc_info=True)
            raise

    def run(self) -> Generator[RefinementStatus, None, None]:
        """Executes the full, multi-stage schema enrichment workflow."""
        try:
            # Stage 1: Structural Integrity
            yield RefinementStatus(phase="Structural Integrity", message="Analyzing guide TOC to find and add missing loops/segments...", progress=0.1)
            
            # Stage 2: Contextualization
            yield RefinementStatus(phase="Contextualization", message="Traversing structure to create context links...", progress=0.2)
            
            # Stage 3: Element Enrichment
            yield RefinementStatus(phase="Element Enrichment", message="Beginning detailed enrichment of all segment definitions...", progress=0.4)
            enrichment_crew = self.crews.element_enrichment_crew()
            
            all_definitions = {**self.schema.get("segmentDefinitions", {}), **self.schema.get("contextualDefinitions", {})}
            total_defs = len(all_definitions)

            for i, (def_id, def_json) in enumerate(all_definitions.items()):
                yield RefinementStatus(phase="Element Enrichment", message=f"Enriching definition: {def_id}", progress=0.4 + (0.4 * (i / total_defs if total_defs > 0 else 0)))
                
                is_contextual = def_id in self.schema.get("contextualDefinitions", {})
                segment_id_for_query = def_id.split('.')[1] if is_contextual else def_id
                context_id_for_query = def_id if is_contextual else None
                base_path = f"/contextualDefinitions/{def_id}" if is_contextual else f"/segmentDefinitions/{def_id}"

                inputs = {"segment_id": segment_id_for_query, "context_id": context_id_for_query, "current_definition_json": json.dumps(def_json)}
                result = enrichment_crew.kickoff(inputs=inputs)
                
                patch_json_str = extract_json_from_llm_output(result.raw)
                if not patch_json_str:
                    logger.warning(f"Agent for {def_id} returned no parsable JSON. Raw output: {result.raw}")
                    continue

                try:
                    patch_data = json.loads(patch_json_str)
                    patch = patch_data.get("patches", patch_data)
                    if not isinstance(patch, list):
                        raise InvalidJsonPatch("Agent output 'patches' field is not a list.")
                        
                    full_path_patch = [{**p, "path": f"{base_path}{p['path']}"} for p in patch]
                    self._apply_patch(full_path_patch, f"Definition {def_id}")

                except (json.JSONDecodeError, InvalidJsonPatch, KeyError) as e:
                    logger.error(f"Could not process patch for {def_id}: {e}. Raw JSON from agent: {patch_json_str}", exc_info=True)
                    continue
            
            # Stage 4: Complex Rule Extraction
            yield RefinementStatus(phase="Rule Extraction", message="Scanning guide for complex, conditional rules...", progress=0.8)
            rule_crew = self.crews.complex_rule_extraction_crew()
            inputs = {"guide_text_chunk": self.guide_toc}
            result = rule_crew.kickoff(inputs=inputs)
            
            rules_json_str = extract_json_from_llm_output(result.raw)
            if rules_json_str:
                try:
                    extracted_data = json.loads(rules_json_str)
                    extracted_rules = extracted_data.get("rules", [])
                    if isinstance(extracted_rules, list) and extracted_rules:
                        if "rules" not in self.schema:
                            self.schema["rules"] = []
                        self.schema["rules"].extend(extracted_rules)
                        yield RefinementStatus(phase="Rule Extraction", message=f"Extracted and added {len(extracted_rules)} complex rules.", progress=0.9)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Could not process extracted rules: {e}. Raw JSON from agent: {rules_json_str}", exc_info=True)
            else:
                logger.warning(f"Rule extraction agent returned no parsable JSON. Raw output: {result.raw}")

            yield RefinementStatus(phase="Complete", message="Schema enrichment finished successfully.", progress=1.0)

        except Exception as e:
            logger.error(f"Refinement engine failed: {e}", exc_info=True)
            yield RefinementStatus(phase="Failed", message=f"An unhandled error occurred in the engine: {str(e)}")

    def get_final_schema(self) -> Dict[str, Any]:
        return self.schema