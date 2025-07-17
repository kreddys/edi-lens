# FILE: backend/src/agents/tools/rag.py
import httpx
import logging
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

# The internal Docker network URL for our LightRAG sidecar service
LIGHTRAG_API_URL = "http://lightrag-server:9621"

class KnowledgeBaseQueryInput(BaseModel):
    """Input for the KnowledgeBaseTool."""
    query: str = Field(..., description="A clear, natural language question to ask the EDI implementation guide.")

class KnowledgeBaseTool(BaseTool):
    name: str = "EDI Guide Knowledge Base Tool"
    description: str = (
        "Use this to query the EDI implementation guide for specific rules, "
        "segment definitions, or structural information. Provides the most accurate, "
        "context-aware information available for the guide."
    )
    args_schema: type[BaseModel] = KnowledgeBaseQueryInput
    
    def _run(self, query: str) -> str:
        """Queries the LightRAG server and returns the synthesized context."""
        logger.info(f"Querying Knowledge Base with: '{query}'")
        try:
            with httpx.Client() as client:
                # We use the 'mix' mode for a powerful combination of graph and vector search
                response = client.post(
                    f"{LIGHTRAG_API_URL}/query",
                    json={"query": query, "mode": "mix"},
                    timeout=120.0
                )
                response.raise_for_status()
                
                # The answer is in the 'answer' key of the JSON response
                answer = response.json().get("answer", "No answer found in the response.")
                logger.info(f"Received answer of length {len(answer)} from Knowledge Base.")
                return answer
                
        except httpx.HTTPStatusError as e:
            error_message = f"Error querying LightRAG: HTTP {e.response.status_code} - {e.response.text}"
            logger.error(error_message)
            return error_message
        except Exception as e:
            error_message = f"An unexpected error occurred while querying LightRAG: {str(e)}"
            logger.error(error_message, exc_info=True)
            return error_message