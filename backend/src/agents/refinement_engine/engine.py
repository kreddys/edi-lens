# FILE: backend/src/agents/refinement_engine/engine.py
import json
import logging
import re
from typing import Generator, Dict, Any, List
from jsonpatch import JsonPatch

from .models import KnowledgeSource, RefinementStatus, RefinementTask
from .rag_tool import RAGTool
from src.agents.crews import SchemaRefinementCrews
from .embedding_models import PineconeEmbeddingModel
from src.core.config import settings

logger = logging.getLogger(__name__)

def _extract_json_from_llm_output(text: str) -> str:
    """
    A robust helper to find a JSON array `[...]` or object `{...}` within
    the LLM's potentially conversational output. It handles markdown code fences.
    """
    # Look for a JSON block wrapped in markdown ```json ... ```
    match = re.search(r'```(json)?\s*([\s\S]*?)\s*```', text, re.DOTALL)
    if match:
        # If found, return the content inside the fences
        return match.group(2).strip()

    # If no markdown block, find the first occurrence of `[` or `{`
    # and try to parse from there to the corresponding closing bracket/brace.
    start_bracket = text.find('[')
    start_brace = text.find('{')

    if start_bracket == -1 and start_brace == -1:
        return text # No JSON found, return original text to let json.loads fail cleanly

    start_pos = -1
    if start_bracket != -1 and (start_bracket < start_brace or start_brace == -1):
        start_pos = start_bracket
        opener, closer = '[', ']'
    else:
        start_pos = start_brace
        opener, closer = '{', '}'

    if start_pos != -1:
        balance = 0
        for i, char in enumerate(text[start_pos:]):
            if char == opener:
                balance += 1
            elif char == closer:
                balance -= 1
            if balance == 0:
                # Found the complete JSON block
                return text[start_pos : start_pos + i + 1]
    
    return text # Fallback to original text

class SchemaRefinementEngine:
    def __init__(self, base_schema: Dict[str, Any], knowledge_source: KnowledgeSource):
        self.in_memory_schema = base_schema
        
        logger.info("Initializing embedding model...")
        embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)

        self.rag_tool = RAGTool(
            knowledge_source=knowledge_source,
            embedding_model=embedding_model
        )
        
        self.crew_factory = SchemaRefinementCrews(rag_tool=self.rag_tool)
        logger.info("SchemaRefinementEngine initialized with new CrewBase factory.")

    def run(self) -> Generator[RefinementStatus, None, None]:
        try:
            yield RefinementStatus(phase="Planning", message="Analyzing documentation to create a refinement plan...")
            planning_crew = self.crew_factory.planning_crew()
            plan_output = planning_crew.kickoff()
            clean_plan_json = _extract_json_from_llm_output(plan_output.raw)
            tasks_data = json.loads(clean_plan_json)
            tasks = [RefinementTask.model_validate(t) for t in tasks_data]
            
            total_tasks = len(tasks)
            yield RefinementStatus(
                phase="Planning",
                message=f"Plan generated with {total_tasks} discrete tasks.",
                progress=0.0,
                total_tasks=total_tasks
            )

            worker_crew = self.crew_factory.worker_crew()
            for i, task in enumerate(tasks):
                yield RefinementStatus(
                    phase="Executing",
                    message=f"Processing task: {task.task_description}",
                    progress=(i / total_tasks),
                    current_task_index=i,
                    total_tasks=total_tasks
                )
                
                crew_input = {
                    "current_schema_json": json.dumps(self.in_memory_schema),
                    "task": task.model_dump_json()
                }
                patch_output = worker_crew.kickoff(inputs=crew_input)
                
                clean_patch_json = _extract_json_from_llm_output(patch_output.raw)
                patch = json.loads(clean_patch_json)
                
                self.in_memory_schema = JsonPatch(patch).apply(self.in_memory_schema)
                
                yield RefinementStatus(
                    phase="Executing",
                    message=f"Task {i+1} complete. Applied {len(patch)} changes for '{task.entity_id}'.",
                    progress=((i + 1) / total_tasks),
                    current_task_index=i + 1,
                    total_tasks=total_tasks,
                    details={"applied_patch": patch}
                )

            yield RefinementStatus(phase="Complete", message="Schema refinement finished successfully.", progress=1.0)

        except Exception as e:
            logger.error(f"Refinement engine failed: {e}", exc_info=True)
            yield RefinementStatus(phase="Failed", message=f"An error occurred: {str(e)}")

    def get_final_schema(self) -> Dict[str, Any]:
        return self.in_memory_schema