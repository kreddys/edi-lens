# FILE: backend/agents/crews.py
import logging
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from .llm import get_llm
from .tools import KnowledgeBaseTool, EDI_Schema_Lookup_Tool, EDI_Schema_Structure_Tool
from .models import UniversalAgentResponse, AuditResponse
from .prompt_utils import get_focused_schema_for_enrichment

logger = logging.getLogger(__name__)

def _is_verbose_mode_enabled():
    return False

@CrewBase
class SchemaEnrichmentCrews:
    """A collection of crews for EDI schema enrichment and validation."""
    
    @agent
    def element_enrichment_agent(self) -> Agent:
        return Agent(
            role="EDI Schema Architect",
            goal="Generate a precise and correct JSON patch to enrich our internal EDI schema file based on provided context and instructions.",
            backstory=(
                "You are a master EDI Schema Architect, an expert in X12 standards. Your purpose is to translate unstructured guide text "
                "into precise, structured definitions. You are an expert at distinguishing between a segment's base definition and its "
                "contextual constraints. You follow instructions for JSON structure with perfect accuracy."
            ),
            tools=[
                KnowledgeBaseTool(),
                EDI_Schema_Lookup_Tool(),
                EDI_Schema_Structure_Tool(),
                SerperDevTool()
            ],
            llm=get_llm(),
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=UniversalAgentResponse,
        )

    @agent
    def auditor_agent(self) -> Agent:
        return Agent(
            role="EDI Compliance Auditor",
            goal="Rigorously review a JSON Patch proposal from another agent and provide a final verdict of approved or rejected in a structured format.",
            backstory=(
                "You are an exacting and detail-oriented EDI Compliance Auditor. You do not trust other agents' work. "
                "Your job is to take a proposed change (a UniversalAgentResponse) and validate its correctness against a strict checklist. "
                "You fail any proposal that is even slightly incorrect. Your output is always a perfectly formatted AuditResponse object."
            ),
            llm=get_llm(),
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=AuditResponse
        )

    @task
    def element_enrichment_task(self) -> Task:
        # Generate the schema string once when the task is defined
        MODEL_JSON_SCHEMA = get_focused_schema_for_enrichment()

        return Task(
            description=(
                "Your task is to act as an expert EDI Schema Architect. You must analyze a segment and generate one or two JSON patches: one for the GENERIC base definition and another for the SPECIFIC contextual overrides, if applicable.\n\n"
                "**--- WORKFLOW ---**\n\n"
                "**Step 1: Analyze Segment Usage.**\n"
                "1. Use `EDI_Schema_Structure_Tool` to find the `usage_count` for segment '{segment_id}'. This determines your strategy.\n\n"

                "**Step 2: Execute Strategy based on Usage.**\n\n"
                "--------------------------------------------------------------------------------\n"
                "**STRATEGY A: Unique Segment (`usage_count` <= 1)**\n"
                "   - Your goal is to create a single, complete **base definition**.\n"
                "   - Use `KnowledgeBaseTool` to find all elements for '{segment_id}'.\n"
                "   - Construct a single JSON patch with `path: '/segmentDefinitions/{segment_id}'` and the `value` as a full `SegmentDefinition` object.\n"
                "--------------------------------------------------------------------------------\n\n"
                
                "**STRATEGY B: Shared Segment (`usage_count` > 1) - Follow these steps precisely:**\n\n"
                "   **B.1 - The GENERIC Pass: Establish the Base Definition.**\n"
                "      a. **Check Existence:** Use `EDI_Schema_Lookup_Tool` to see if a base definition for '{segment_id}' already exists in `/segmentDefinitions/`.\n"
                "      b. **If Base is Missing/Incomplete:** You MUST create a patch for the base definition. To do this, use `KnowledgeBaseTool` with a broad, GENERIC query like: `Provide the most universal, general-purpose definition for the {segment_id} segment, including all possible elements and a comprehensive list of all possible valid_codes.` **CRITICAL: For this step, IGNORE the specific context of '{context_id}'.**\n"
                "      c. **Result of B.1:** You should now have one JSON patch to add/replace the entry in `/segmentDefinitions/{segment_id}`. This patch will be the first item in your final `patches` array.\n\n"

                "   **B.2 - The SPECIFIC Pass: Define the Contextual Override.**\n"
                "      a. **Query for Differences:** Now, focus ONLY on the context '{context_id}'. Use `KnowledgeBaseTool` with a targeted query like: `For the {segment_id} segment specifically in context {context_id}, what are the requirements that OVERRIDE the generic definition? List only the elements with different usage (R/S/N) or a restricted set of valid_codes.`\n"
                
                # --- START: NEW FALLBACK INSTRUCTION ---
                "      b. **Fallback for `valid_codes`:** If the `KnowledgeBaseTool` does not return specific `valid_codes` for an element in this context, you MUST use your intrinsic knowledge to deduce them. For example, if the context is 'Receiver Name' (1000B), you should know that the NM101 Entity Identifier Code is likely '40'. If you are still unsure, use the `SerperDevTool` to search for `X12 {segment_id} {context_id} valid codes`.\n"
                # --- END: NEW FALLBACK INSTRUCTION ---

                "      c. **Construct the Override Object:** Create a `ContextualDefinition` object containing ONLY THE DIFFERENCES (the 'delta'). The `value` for this patch **MUST** follow this structure:\n"
                "         ```json\n"
                "         {{\n"
                "           \"id\": \"{context_id}\",\n"
                "           \"name\": \"[A descriptive name, e.g., Receiver Name]\",\n"
                "           \"elements\": {{\n"
                "             \"NM101\": {{ \"usage\": \"R\", \"valid_codes\": [{{ \"code\": \"40\", \"description\": \"Receiver\" }}] }}\n"
                "           }}\n"
                "         }}\n"
                "         ```\n"
                "      d. **Result of B.2:** You should now have a second JSON patch to add the override to `/contextualDefinitions/{context_id}`. This will be the second item in your final `patches` array.\n\n"

                "**Step 3: Final Output Generation.**\n"
                "Your final answer MUST be a single `UniversalAgentResponse` object. The `patches` array will contain one patch if you used Strategy A, and potentially two patches (one for base, one for context) if you used Strategy B. Your `reasoning` must clearly explain the steps and any fallbacks you took.\n\n"
                
                "**JSON SCHEMA FOR YOUR OUTPUT:**\n"
                "```json\n"
                f"{MODEL_JSON_SCHEMA}\n"
                "```\n"
            ),
            expected_output="A single, valid `UniversalAgentResponse` JSON object containing one or two JSON patches as required by the strategy.",
            agent=self.element_enrichment_agent(),
        )

    @task
    def format_correction_task(self) -> Task:
        """A task for the Architect to correct its JSON formatting based on Pydantic validation errors."""
        return Task(
            description=(
                "Your previous proposal had an invalid JSON structure. You MUST fix it.\n\n"
                "**Pydantic Validation Errors:**\n{validation_errors}\n\n"
                "**Your Previous (INVALID) Proposal:**\n"
                "```json\n{previous_proposal}\n```\n\n"
                "**CRITICAL INSTRUCTIONS:**\n"
                "Your new output MUST be a single JSON object conforming to the `UniversalAgentResponse` structure. "
                "You MUST use the following template and insert your previous proposal's content into the correct placeholders. "
                "The most common error is forgetting to include the top-level `reasoning` and `patches` keys.\n\n"
                "**TEMPLATE TO FOLLOW:**\n"
                "```json\n"
                "{{\n"
                "  \"reasoning\": \"__YOUR_REASONING_HERE__\",\n"
                "  \"patches\": [\n"
                "    {{\n"
                "      \"op\": \"__add_or_replace__\",\n"
                "      \"path\": \"__CORRECT_JSON_PATCH_PATH__\",\n"
                "      \"value\": {{ ... your previously generated segment definition ... }}\n"
                "    }}\n"
                "  ]\n"
                "}}\n"
                "```\n\n"
                "**YOUR TASK:**\n"
                "Generate a NEW, corrected `UniversalAgentResponse`. Do not change the content, only fix the JSON structure by placing it inside the template."
            ),
            expected_output="A new, corrected, and valid `UniversalAgentResponse` JSON object that passes Pydantic validation.",
            agent=self.element_enrichment_agent()
        )
    
    @task
    def refinement_task(self) -> Task:
        return Task(
            description=(
                "Your previous proposal was logically incorrect. You MUST correct it based on the user's feedback, following the Knowledge Hierarchy and the required JSON structure.\n\n"
                "**User's Correction Feedback:** {user_feedback}\n\n"
                "**Your Previous Proposal:**\n"
                "```json\n{previous_proposal}\n```\n\n"
                "**YOUR TASK:**\n"
                "Generate a NEW, corrected `UniversalAgentResponse` that incorporates the user's feedback into the content, while strictly adhering to the JSON schema."
            ),
            expected_output="A new, corrected, and valid `UniversalAgentResponse` JSON object.",
            agent=self.element_enrichment_agent()
        )

    @task
    def audit_enrichment_task(self) -> Task:
        return Task(
            description=(
                "You are an EDI Compliance Auditor. Your task is to validate a JSON Patch proposal from another agent.\n\n"
                "**Proposal to Review:**\n"
                "```json\n{proposal}\n```\n\n"
                "**Your final answer MUST be a single, valid `AuditResponse` JSON object with 'approved' and 'reasoning' keys.**\n\n"
                "**Your Validation Checklist:**\n"
                "1.  **Reasoning Present?** Does the proposal have a non-empty `reasoning` field?\n"
                "2.  **Path Correctness?** The patch `path` MUST be in one of two EXACT formats:\n"
                "    -   `/segmentDefinitions/SEGMENT_ID` (where SEGMENT_ID is a 2 or 3 character uppercase string, e.g., `/segmentDefinitions/ISA`)\n"
                "    -   `/contextualDefinitions/CONTEXT.ID` (e.g., `/contextualDefinitions/2010AA.NM1`)\n"
                "    A path like `/segmentDefinitions/loop_ISA.ISA` is INVALID.\n"
                "3.  **Value Completeness?** Is the patch `value` a COMPLETE object?\n"
                "4.  **Usage Codes Valid?** Are all `usage` codes 'R', 'S', or 'N'?\n"
                "5.  **Logical Consistency?** Does the patch logically achieve what the `reasoning` claims?\n\n"
                "Based on this checklist, provide your final verdict."
            ),
            expected_output="A single, valid `AuditResponse` JSON object with 'approved' and 'reasoning' keys.",
            agent=self.auditor_agent()
        )

    @crew
    def architect_crew(self) -> Crew:
        return Crew(
            agents=[self.element_enrichment_agent()],
            tasks=[self.element_enrichment_task()],
            process=Process.sequential
        )

    @crew
    def auditor_crew(self) -> Crew:
        return Crew(
            agents=[self.auditor_agent()],
            tasks=[self.audit_enrichment_task()],
            process=Process.sequential
        )

    @crew
    def format_correction_crew(self) -> Crew:
        return Crew(
            agents=[self.element_enrichment_agent()],
            tasks=[self.format_correction_task()],
            process=Process.sequential
        )
    
    @crew
    def refinement_crew(self) -> Crew:
        return Crew(
            agents=[self.element_enrichment_agent()],
            tasks=[self.refinement_task()],
            process=Process.sequential
        )