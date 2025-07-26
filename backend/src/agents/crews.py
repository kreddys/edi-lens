# FILE: backend/agents/crews.py
import logging
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from .llm import get_llm
from .tools import KnowledgeBaseTool, EDI_Schema_Lookup_Tool, EDI_Schema_Structure_Tool
from .models import UniversalAgentResponse, AuditResponse
from .prompt_utils import get_pydantic_model_schemas

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
        MODEL_JSON_SCHEMA = get_pydantic_model_schemas()

        return Task(
            description=(
                "Your task is to create a complete and accurate segment definition for '{segment_id}' in the context of '{context_id}'.\n\n"
                "**Step 1: Initial Research & Strategy.**\n"
                "1.  Use `EDI_Schema_Structure_Tool` to determine the `usage_count` for '{segment_id}'.\n"
                "2.  Based on `usage_count`, decide your strategy (BASE or CONTEXTUAL) and determine the correct JSON patch `path`.\n"
                "    -   **IF `usage_count` is 1 or 0:** You are creating a **BASE definition**. The JSON patch `path` **MUST** be `/segmentDefinitions/{segment_id}`.\n"
                "    -   **ELSE (if `usage_count` > 1):** You are creating a **CONTEXTUAL definition**. The JSON patch `path` **MUST** be `/contextualDefinitions/{context_id}`.\n\n"
                
                "**Step 2: Broad Segment Query.**\n"
                "1.  Perform an initial query using `KnowledgeBaseTool` to get the general definition and a list of all elements for the '{segment_id}' segment.\n\n"

                "**Step 3: Rigorous Element-by-Element Verification.**\n"
                "**This is the most important step.** For EACH element identified in Step 2, you MUST verify you have all required details. If ANY detail is missing, you MUST use the `KnowledgeBaseTool` again with a MORE SPECIFIC query targeting that single element.\n"
                "   - **Checklist per element:** `xid`, `data_ele`, `name`, `usage`, `seq`, `dataType`, `minLength`, `maxLength`.\n"
                
                # --- THIS IS THE FIX ---
                # We have removed the {element_xid} placeholder and replaced it with a static example.
                "   - **`valid_codes` Check:** If an element is of type `ID`, it is CRITICAL that you find its list of valid codes. If the first query did not provide them, perform a new, targeted query. For example, you could ask: "
                "`What are all the valid codes and their descriptions for element NM101 in segment {segment_id}?`\n"
                # --- END OF FIX ---

                "   - **Repeat this process for every single element** until your information is complete.\n\n"

                "**Step 4: Construct the Final JSON Output.**\n"
                "Assemble all the verified information into a single, valid JSON object that strictly conforms to the `UniversalAgentResponse` JSON Schema. Do not add any text or explanation after the final closing brace `}}` of the JSON object.\n\n"
                "-   **For Date (DT) or Time (TM) elements:** You MUST include a `format` field. If the guide specifies multiple valid formats (e.g., 'HHMM, HHMMSS'), you MUST provide them as a JSON array of strings: `\"format\": [\"HHMM\", \"HHMMSS\"]`.\n\n"

                "Examples of data_ele field are I01, I03, I65, 479, 142 etc. If the knowledge base did not return the data_ele details , leave the field as null or use your intrinsic knowledge to populate value for this field \n\n"
                "**JSON SCHEMA FOR YOUR OUTPUT:**\n"
                "```json\n"
                f"{MODEL_JSON_SCHEMA}\n"
                "```\n\n"
                "**RICH EXAMPLE of a CORRECT `SegmentDefinition` (for the 'value' field of the patch):**\n"
                "This example shows a composite element (`HI`) and a time element (`ISA10`).\n"
                "```json\n"
                "{{\n"
                "  \"id\": \"HI\",\n"
                "  \"name\": \"Health Care Information Codes\",\n"
                "  \"description\": \"To specify health care diagnosis and procedure codes.\",\n"
                "  \"usage\": \"R\",\n"
                "  \"max_use\": 1,\n"
                "  \"elements\": [\n"
                "    {{\n"
                "      \"xid\": \"HI01\",\n"
                "      \"data_ele\": \"1270\",\n"
                "      \"name\": \"Health Care Code Information\",\n"
                "      \"usage\": \"R\",\n"
                "      \"seq\": 1,\n"
                "      \"dataType\": \"Composite\",\n"
                "      \"sub_elements\": [\n"
                "        {{\n"
                "          \"xid\": \"HI01-1\",\n"
                "          \"data_ele\": \"1271\",\n"
                "          \"name\": \"Code List Qualifier Code\",\n"
                "          \"usage\": \"R\",\n"
                "          \"seq\": 1,\n"
                "          \"dataType\": \"ID\",\n"
                "          \"valid_codes\": [\n"
                "            {{ \"code\": \"ABK\", \"description\": \"Principal Diagnosis\" }},\n"
                "            {{ \"code\": \"ABF\", \"description\": \"Other Diagnosis\" }}\n"
                "          ]\n"
                "        }},\n"
                "        {{\n"
                "          \"xid\": \"HI01-2\",\n"
                "          \"data_ele\": \"1271\",\n"
                "          \"name\": \"Industry Code\",\n"
                "          \"usage\": \"R\",\n"
                "          \"seq\": 2,\n"
                "          \"dataType\": \"AN\"\n"
                "        }}\n"
                "      ]\n"
                "    }},\n"
                "    {{\n"
                "      \"xid\": \"ISA10\",\n"
                "      \"data_ele\": \"I09\",\n"
                "      \"name\": \"Interchange Time\",\n"
                "      \"usage\": \"R\",\n"
                "      \"seq\": 10,\n"
                "      \"dataType\": \"TM\",\n"
                "      \"format\": \"HHMM\"\n"
                "    }}\n"
                "  ]\n"
                "}}\n"
                "```"
            ),
            expected_output="A single, valid `UniversalAgentResponse` JSON object that strictly conforms to the provided JSON Schema.",
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