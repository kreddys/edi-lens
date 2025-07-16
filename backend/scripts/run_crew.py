# FILE: backend/scripts/run_crew.py
import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Step 1: Set up project path and LOAD THE ENVIRONMENT ---
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

env_path = project_root.parent / ".env.local" 
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# --- Step 2: Now, import application modules ---
from src.core.config import settings, setup_logging
import openlit

# Import the new engine and its models
from src.agents.rag_pipeline.engine import SchemaRefinementEngine
from src.agents.rag_pipeline.models import KnowledgeSource
from scripts.preprocess_guide import preprocess_guide

# --- Step 3: Configure Logging & OpenLIT ---
setup_logging()
logger = logging.getLogger(__name__)

if os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true":
    logger.info("Observability is enabled. Initializing OpenLIT...")
    openlit.init(application_name="edi-lens-crew")
else:
    logger.info("Observability is disabled.")

def run_full_schema_refinement():
    """
    A command-line interface for the SchemaRefinementEngine.
    This function orchestrates the entire "Schema Assembly Line" workflow.
    """
    logger.info("--- EDI Lens Schema Generation & Enrichment Utility ---")
    
    if not (os.getenv("PINECONE_API_KEY") and (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))):
        logger.error("Required API keys (PINECONE_API_KEY and an LLM provider key) are not set in .env.local")
        return

    # --- Define Inputs ---
    base_schema_path = project_root / "data" / "edi_schemas" / "837.5010.X222.A1.json"
    guide_path = project_root / "data" / "knowledge" / "x222a1.txt"
    output_schema_path = project_root / "data" / "schemas_refined" / "837.5010.X222.A1.enriched.json"
    output_schema_path.parent.mkdir(exist_ok=True, parents=True)

    with open(base_schema_path, 'r') as f:
        base_schema = json.load(f)

    # Preprocess the guide to get the chunks and the table of contents
    chunk_dir, toc_content = preprocess_guide(guide_path)
    knowledge = KnowledgeSource(source_type="directory", content=str(chunk_dir))
    
    # --- Initialize and Run the Engine ---
    engine = SchemaRefinementEngine(
        base_schema=base_schema, 
        knowledge_source=knowledge,
        guide_toc=toc_content
    )
    
    for status in engine.run():
        progress_bar = f"{int(status.progress * 100)}%"
        logger.info(f"[{status.phase.upper():<22}] {progress_bar:>4} | {status.message}")
        
        if status.details:
            logger.debug(json.dumps(status.details, indent=2))
        
        if status.phase == "Failed":
            logger.error("Refinement stopped due to an unrecoverable error.")
            return

    # --- Finalization ---
    if status.phase == "Complete":
        logger.info("Refinement complete. Saving final schema...")
        final_schema = engine.get_final_schema()
        with open(output_schema_path, 'w') as f:
            json.dump(final_schema, f, indent=2)
            
        logger.info(f"✅ Final schema saved to {output_schema_path}")

if __name__ == "__main__":
    run_full_schema_refinement()