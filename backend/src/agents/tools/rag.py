# FILE: backend/src/agents/tools/rag.py
import httpx
import logging
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from opentelemetry import trace
from openlit.semcov import SemanticConvention

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("edi_lens_rag_tool_tracer")

LIGHTRAG_API_URL = "http://lightrag-server:9621"

class KnowledgeBaseQueryInput(BaseModel):
    query: str = Field(..., description="A clear, natural language question to ask the EDI implementation guide.")

class KnowledgeBaseTool(BaseTool):
    name: str = "EDI Guide Knowledge Base Tool"
    description: str = (
        "Use this to query the EDI implementation guide for specific rules, "
        "segment definitions, or structural information. Provides the most accurate, "
        "context-aware information available for the guide."
    )
    args_schema: type[BaseModel] = KnowledgeBaseQueryInput
    
    LIGHTRAG_API_URL: str = LIGHTRAG_API_URL

    def _run(self, query: str) -> str:
        with tracer.start_as_current_span("RAG Tool Query") as span:
            span.set_attribute(SemanticConvention.GEN_AI_SYSTEM, "LightRAG")
            span.set_attribute(SemanticConvention.GEN_AI_CONTENT_PROMPT, query)
            span.set_attribute("lightrag.api.url", self.LIGHTRAG_API_URL)

            logger.info(f"Querying Knowledge Base with: '{query}'")
            try:
                with httpx.Client() as client:
                    response = client.post(
                        f"{self.LIGHTRAG_API_URL}/query",
                        json={"query": query, "mode": "mix"},
                        timeout=120.0
                    )
                    response.raise_for_status()
                    
                    # --- THIS IS THE FIX: Use the correct key 'response' from the OpenAPI spec ---
                    answer = response.json().get("response", "No answer found in the response.")
                    # --- END OF FIX ---
                    logger.info(f"Received answer of length {len(answer)} from Knowledge Base.")

                    span.set_attribute(SemanticConvention.GEN_AI_CONTENT_COMPLETION, answer)
                    span.set_status(trace.StatusCode.OK)
                    return answer
                    
            except httpx.HTTPStatusError as e:
                error_message = f"Error querying LightRAG: HTTP {e.response.status_code} - {e.response.text}"
                logger.error(error_message)
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, description=error_message))
                return error_message
            except Exception as e:
                error_message = f"An unexpected error occurred while querying LightRAG: {str(e)}"
                logger.error(error_message, exc_info=True)
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, description=error_message))
                return error_message