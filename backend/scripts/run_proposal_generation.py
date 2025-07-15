# FILE: backend/scripts/run_proposal_generation.py
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# --- Setup Project Path and Environment ---
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
env_path = project_root.parent / ".env.local"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from src.core.config import setup_logging, settings
from src.agents.crews import SchemaEnrichmentCrews
# --- THIS IS THE FIX: Corrected import path ---
from scripts.preprocess_guide import preprocess_guide
from src.agents.refinement_engine.rag_tool import RAGTool
from src.agents.refinement_engine.embedding_models import PineconeEmbeddingModel
from src.agents.refinement_engine.models import KnowledgeSource # Import the model

# --- Configuration ---
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BASE_OUTPUT_DIR = project_root / "enrichment_runs"
CURRENT_RUN_DIR = BASE_OUTPUT_DIR / f"run_{RUN_TIMESTAMP}"
PROPOSED_PATCHES_DIR = CURRENT_RUN_DIR / "proposed_patches"
LOG_DIR = CURRENT_RUN_DIR / "logs"

# Create directories
PROPOSED_PATCHES_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Setup Logging ---
log_file = LOG_DIR / "proposal_generation.log"
setup_logging() # Sets up console logging
# Add file handler for this run
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"))
logging.getLogger().addHandler(file_handler)
logger = logging.getLogger(__name__)

def generate_proposals(base_schema_path: Path, guide_path: Path):
    logger.info(f"Starting proposal generation run. Output will be in: {CURRENT_RUN_DIR}")

    # 1. Load base schema
    with open(base_schema_path, 'r') as f:
        schema = json.load(f)
    (CURRENT_RUN_DIR / "_original_schema_copy.json").write_text(json.dumps(schema, indent=2))
    logger.info(f"Loaded base schema from: {base_schema_path}")

    # 2. Pre-process and index the guide
    chunk_dir, toc_content = preprocess_guide(guide_path)
    embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
    
    # --- THIS IS THE FIX: Use the KnowledgeSource model and a new source_type ---
    # We will update the document loader to handle this new type.
    knowledge = KnowledgeSource(source_type="directory", content=str(chunk_dir))
    rag_tool = RAGTool(knowledge_source=knowledge, embedding_model=embedding_model)
    logger.info("Knowledge base has been chunked and indexed.")

    # 3. Initialize Crews
    crews = SchemaEnrichmentCrews(rag_tool)
    analysis_crew = crews.analysis_crew()
    architect_crew = crews.architect_crew()

    # 4. Main Orchestration Loop
    summary_lines = []
    for segment_id, segment_def in schema["segmentDefinitions"].items():
        logger.info(f"----- Analyzing segment: {segment_id} -----")
        
        try:
            analysis_result = analysis_crew.kickoff(inputs={
                "segment_id": segment_id,
                "current_definition_json": json.dumps(segment_def, indent=2)
            })
            tasks = json.loads(analysis_result.raw)

            if not tasks:
                logger.info(f"No changes proposed for segment {segment_id}.")
                continue
            
            logger.info(f"Analyst proposed {len(tasks)} changes for {segment_id}.")
            summary_lines.append(f"- **{segment_id}**: {len(tasks)} changes proposed.")

            all_patches_for_segment = []
            current_segment_def_for_patching = segment_def
            for task in tasks:
                patch_result = architect_crew.kickoff(inputs={
                    "task_json": json.dumps(task),
                    "current_definition_json": json.dumps(current_segment_def_for_patching, indent=2)
                })
                patch = json.loads(patch_result.raw)
                all_patches_for_segment.extend(patch)
                # Apply patch to keep the definition up-to-date for the next task
                from jsonpatch import JsonPatch
                current_segment_def_for_patching = JsonPatch(patch).apply(current_segment_def_for_patching)
            
            patch_file = PROPOSED_PATCHES_DIR / f"{segment_id}.jsonpatch"
            patch_file.write_text(json.dumps(all_patches_for_segment, indent=2))
            logger.info(f"Saved patch file for {segment_id} with {len(all_patches_for_segment)} operations.")

        except Exception as e:
            logger.error(f"Failed to process segment {segment_id}: {e}", exc_info=True)
            summary_lines.append(f"- **{segment_id}**: FAILED - check logs.")

    # 5. Generate Summary Report
    report_content = f"# Schema Enrichment Proposal: {RUN_TIMESTAMP}\n\n" + "\n".join(summary_lines)
    (CURRENT_RUN_DIR / "_summary_report.md").write_text(report_content)
    logger.info(f"Proposal generation complete. Review files in {CURRENT_RUN_DIR}")

if __name__ == "__main__":
    base_schema = project_root.parent / "docs/schema/sample_schema.json"
    guide = project_root.parent / "x222a1.txt"
    generate_proposals(base_schema, guide)