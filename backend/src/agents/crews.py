# FILE: backend/agents/crews.py
import logging
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from .llm import get_llm
from .tools import KnowledgeBaseTool, EDI_Schema_Lookup_Tool, EDI_Schema_Structure_Tool
from .models import UniversalAgentResponse, AuditResponse

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
        return Task(
            description=(
                "Your task is to create a complete and accurate segment definition for '{segment_id}' in the context of '{context_id}' for the schema '{schema_name}'.\n\n"
                "**KNOWLEDGE HIERARCHY & DECISION PROCESS:**\n"
                "1.  **Assess Usage:** First, use the `EDI_Schema_Structure_Tool` to determine the `usage_count` for '{segment_id}'.\n"
                "2.  **Determine Update Strategy & JSON Patch Path:**\n"
                "    -   If `usage_count` > 1, create a CONTEXTUAL definition. The JSON patch `path` MUST be exactly `/contextualDefinitions/{context_id}`.\n"
                "    -   If `usage_count` <= 1, create a BASE definition. The JSON patch `path` MUST be exactly `/segmentDefinitions/{segment_id}`.\n"
                "3.  **Gather Content:** Use the `KnowledgeBaseTool` and `EDI_Schema_Lookup_Tool` to get content.\n"
                "4.  **Cite Sources:** In your `reasoning`, you MUST state your strategy (BASE or CONTEXTUAL) and cite your knowledge tiers for the content.\n\n"
                "**FINAL OUTPUT INSTRUCTIONS:**\n"
                "You MUST respond with a single JSON object. Use the following template and fill in the `__PLACEHOLDER__` sections. Do not deviate from this structure.\n\n"
                "```json\n"
                "{{\n"
                "  \"reasoning\": \"__YOUR_REASONING_HERE__\",\n"
                "  \"patches\": [\n"
                "    {{\n"
                "      \"op\": \"__add_or_replace__\",\n"
                "      \"path\": \"__CORRECT_JSON_PATCH_PATH__\",\n"
                "      \"value\": {{\n"
                "        \"id\": \"__SEGMENT_ID__\",\n"
                "        \"name\": \"__SEGMENT_NAME__\",\n"
                "        \"description\": \"__SEGMENT_DESCRIPTION__\",\n"
                "        \"usage\": \"__R_S_OR_N__\",\n"
                "        \"max_use\": __INTEGER__,\n"
                "        \"elements\": [\n"
                "          {{\n"
                "            \"xid\": \"__ELEMENT_XID__\",\n"
                "            \"data_ele\": __INTEGER__,\n"
                "            \"name\": \"__ELEMENT_NAME__\",\n"
                "            \"usage\": \"__R_S_OR_N__\",\n"
                "            \"seq\": \"__SEQUENCE_STRING__\",\n"
                "            \"dataType\": \"__DATATYPE_STRING__\"\n"
                "          }}\n"
                "        ]\n"
                "      }}\n"
                "    }}\n"
                "  ]\n"
                "}}\n"
                "```"
            ),
            expected_output="A single, valid `UniversalAgentResponse` JSON object that strictly follows the provided template.",
            agent=self.element_enrichment_agent(),
        )

    @task
    def format_correction_task(self) -> Task:
        return Task(
            description=(
                "Your previous proposal had an invalid JSON structure. You MUST fix it.\n\n"
                "**Pydantic Validation Errors:**\n{validation_errors}\n\n"
                "**Your Previous (INVALID) Proposal:**\n"
                "```json\n{previous_proposal}\n```\n\n"
                "**CRITICAL INSTRUCTIONS:**\n"
                "1.  Review the validation errors. They tell you exactly which fields are wrong (e.g., you used 'id' instead of 'xid').\n"
                "2.  Your new output MUST be a single JSON object conforming to the `UniversalAgentResponse` structure shown in your original instructions.\n"
                "3.  Do not change the content, only fix the JSON field names and structure."
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