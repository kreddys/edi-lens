# FILE: backend/src/agents/refinement_engine/engine.py
import json
import logging
import re
from typing import Generator, Dict, Any, List
from jsonpatch import JsonPatch

from .models import KnowledgeSource, RefinementStatus, RefinementTask
from .rag_tool import RAGTool
from src.agents.crews import SchemaRefinementCrews

logger = logging.getLogger(__name__)

# --- NEW HELPER FUNCTION ---
def _extract_json_from_llm_output(text: str) -> str:
    """
    Extracts a JSON string from a markdown code block in the LLM's output.
    """
    match = re.search(r'```(json)?\n(.*)\n```', text, re.DOTALL)
    if match:
        return match.group(2).strip()
    # Fallback if no markdown block is found, assume the whole string is JSON
    return text.strip()


class SchemaRefinementEngine:
    def __init__(self, base_schema: Dict[str, Any], knowledge_source: KnowledgeSource):
        self.in_memory_schema = base_schema
        self.rag_tool = RAGTool(knowledge_source=knowledge_source)
        self.crew_factory = SchemaRefinementCrews(rag_tool=self.rag_tool)
        logger.info("SchemaRefinementEngine initialized with new CrewBase factory.")

    def run(self) -> Generator[RefinementStatus, None, None]:
        """
        Runs the full refinement process, yielding status updates.
        """
        try:
            # --- PHASE 1: PLANNING ---
            yield RefinementStatus(phase="Planning", message="Analyzing documentation to create a refinement plan...")
            
            planning_crew = self.crew_factory.planning_crew()
            plan_output = planning_crew.kickoff()
            
            # --- THIS IS THE FIX ---
            # Use the helper to extract the clean JSON before parsing
            clean_plan_json = _extract_json_from_llm_output(plan_output.raw)
            tasks_data = json.loads(clean_plan_json)
            # --- END OF FIX ---
            
            tasks = [RefinementTask.model_validate(t) for t in tasks_data]
            
            total_tasks = len(tasks)
            yield RefinementStatus(
                phase="Planning",
                message=f"Plan generated with {total_tasks} discrete tasks.",
                progress=0.0,
                total_tasks=total_tasks
            )

            # --- PHASE 2: EXECUTION ---
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
                
                # --- THIS IS THE FIX (Applied here as well) ---
                clean_patch_json = _extract_json_from_llm_output(patch_output.raw)
                patch = json.loads(clean_patch_json)
                # --- END OF FIX ---
                
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