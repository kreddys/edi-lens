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
        # The RAG tool is now initialized inside the engine, as it's a core dependency
        from .rag_tool import RAGTool
        rag_tool = RAGTool(knowledge_source=self.knowledge_source, embedding_model=embedding_model)
        
        self.crews = SchemaEnrichmentCrews(rag_tool=rag_tool)
        logger.info("SchemaRefinementEngine initialized with specialized agent crews.")

    def _apply_patch(self, patch: List[Dict[str, Any]], description: str):
        """Applies a JSON patch to the in-memory schema and logs the outcome."""
        try:
            # The `apply` method returns the new, patched document.
            self.schema = JsonPatch(patch).apply(self.schema)
            logger.info(f"Successfully applied patch for: {description}")
        except JsonPatchException as e:
            logger.error(f"Failed to apply patch for {description}: {e}")
            # In a real-world scenario, you might want to halt or handle this error more gracefully
            raise

    def run(self) -> Generator[RefinementStatus, None, None]:
        """Executes the full, multi-stage schema enrichment workflow."""
        try:
            # Stage 1: Structural Integrity
            yield RefinementStatus(phase="Structural Integrity", message="Analyzing guide TOC to find and add missing loops/segments...", progress=0.1)
            # This stage is a future enhancement. For now, we assume the provided structure is complete.
            # integrity_crew = self.crews.structural_integrity_crew()
            # ... run crew and apply patches ...
            
            # Stage 2: Contextualization
            yield RefinementStatus(phase="Contextualization", message="Traversing structure to create context links...", progress=0.2)
            # This stage is also a future enhancement. We will rely on the pre-defined contextIds for now.

            # Stage 3: Element Enrichment
            yield RefinementStatus(phase="Element Enrichment", message="Beginning detailed enrichment of all segment definitions...", progress=0.4)
            enrichment_crew = self.crews.element_enrichment_crew()
            
            # Enrich base definitions
            all_definitions = self.schema.get("segmentDefinitions", {})
            for i, (def_id, def_json) in enumerate(all_definitions.items()):
                yield RefinementStatus(phase="Element Enrichment", message=f"Enriching base definition: {def_id}", progress=0.4 + (0.2 * (i / len(all_definitions))))
                inputs = {"segment_id": def_id, "context_id": None, "current_definition_json": json.dumps(def_json)}
                result = enrichment_crew.kickoff(inputs=inputs)
                patch_json = extract_json_from_llm_output(result.raw)
                if patch_json:
                    patch_data = json.loads(patch_json)
                    if isinstance(patch_data, dict) and "patches" in patch_data:
                        patch = patch_data["patches"]
                    else:
                        patch = patch_data

                    if not isinstance(patch, list):
                        raise InvalidJsonPatch("Patch is not a list of operations.")
                    # The agent returns a patch relative to the definition, so we prepend the path.
                    full_path_patch = [
                        {**p, "path": f"/segmentDefinitions/{def_id}{p['path']}"}
                        for p in patch
                    ]
                    self._apply_patch(full_path_patch, f"Base definition {def_id}")

            # Enrich contextual definitions
            all_contexts = self.schema.get("contextualDefinitions", {})
            for i, (ctx_id, ctx_json) in enumerate(all_contexts.items()):
                yield RefinementStatus(phase="Element Enrichment", message=f"Enriching contextual definition: {ctx_id}", progress=0.6 + (0.2 * (i / len(all_contexts))))
                base_def_id = ctx_id.split('.')[1]
                inputs = {"segment_id": base_def_id, "context_id": ctx_id, "current_definition_json": json.dumps(ctx_json)}
                result = enrichment_crew.kickoff(inputs=inputs)
                patch_json = extract_json_from_llm_output(result.raw)
                if patch_json:
                    patch_data = json.loads(patch_json)
                    if isinstance(patch_data, dict) and "patches" in patch_data:
                        patch = patch_data["patches"]
                    else:
                        patch = patch_data

                    if not isinstance(patch, list):
                        raise InvalidJsonPatch("Patch is not a list of operations.")
                    # The agent returns a patch relative to the definition, so we prepend the path.
                    full_path_patch = [
                        {**p, "path": f"/contextualDefinitions/{ctx_id}{p['path']}"}
                        for p in patch
                    ]
                    self._apply_patch(full_path_patch, f"Contextual definition {ctx_id}")

            # Stage 4: Complex Rule Extraction
            yield RefinementStatus(phase="Rule Extraction", message="Scanning guide for complex, conditional rules...", progress=0.8)
            try:
                rule_crew = self.crews.complex_rule_extraction_crew()
                # In a real implementation, you would chunk the guide and loop through it.
                # For this example, we'll do one pass.
                inputs = {"guide_text_chunk": self.guide_toc} # Using TOC as a proxy for rule-heavy text
                result = rule_crew.kickoff(inputs=inputs)
                rules_json = extract_json_from_llm_output(result.raw)
                if rules_json:
                    extracted_data = json.loads(rules_json)
                    if isinstance(extracted_data, dict):
                        extracted_rules = extracted_data.get("rules", [])
                        if isinstance(extracted_rules, list):
                            if extracted_rules:
                                if "rules" not in self.schema:
                                    self.schema["rules"] = []
                                self.schema["rules"].extend(extracted_rules)
                                yield RefinementStatus(phase="Rule Extraction", message=f"Extracted and added {len(extracted_rules)} complex rules.", progress=0.9)
                        else:
                            raise TypeError("'rules' key in agent output is not a list.")
            except (TypeError, KeyError) as e:
                logger.error(f"Failed to process and apply rules: {e}")
                yield RefinementStatus(phase="Failed", message=f"An error occurred during rule extraction: {str(e)}")
                return

            yield RefinementStatus(phase="Complete", message="Schema enrichment finished successfully.", progress=1.0)

        except Exception as e:
            logger.error(f"Refinement engine failed: {e}", exc_info=True)
            yield RefinementStatus(phase="Failed", message=f"An error occurred: {str(e)}")

    def get_final_schema(self) -> Dict[str, Any]:
        return self.schema