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
        return Task(
            description=(
                "Your task is to create a complete and accurate segment definition for '{segment_id}' in the context of '{context_id}'.\n\n"
                "**DECISION PROCESS & PATH CONSTRUCTION (Follow these steps exactly):**\n"
                "1.  Use `EDI_Schema_Structure_Tool` to find the `usage_count` for '{segment_id}'.\n"
                "2.  If `usage_count` is 1 or less, you are creating a **BASE definition**. Your JSON patch `path` MUST be `/segmentDefinitions/{segment_id}`. (e.g., `/segmentDefinitions/ISA`).\n"
                "3.  If `usage_count` is greater than 1, you are creating a **CONTEXTUAL definition**. Your JSON patch `path` MUST be `/contextualDefinitions/{context_id}`. (e.g., `/contextualDefinitions/2010AA.NM1`).\n"
                "4.  Use `KnowledgeBaseTool` to gather all content. You MUST query for `valid codes WITH DESCRIPTIONS` for any element that has them.\n\n"
                "**FINAL OUTPUT REQUIREMENTS:**\n"
                "Your final answer MUST be a single `UniversalAgentResponse` JSON object. The `value` of the patch MUST strictly conform to the models described below.\n\n"
                "--- `SegmentDefinition` Model ---\n"
                "`id`: string\n"
                "`name`: string\n"
                "`description`: string\n"
                "`usage`: string (Must be \"R\", \"S\", or \"N\")\n"
                "`max_use`: integer\n"
                "`elements`: A list of `BaseElement` objects.\n\n"
                "--- `BaseElement` Model ---\n"
                "`xid`: string\n"
                "`data_ele`: **integer** (The official X12 Data Element Number)\n"
                "`name`: string\n"
                "`usage`: string (Must be \"R\", \"S\", \"N\")\n"
                "`seq`: **integer** (The sequence number, e.g., 1, 2, 3)\n"
                "`dataType`: string (e.g., \"ID\", \"AN\", \"DT\")\n"
                "`valid_codes`: (optional) A list of `CodeDefinition` objects.\n\n"
                "--- `CodeDefinition` Model (VERY IMPORTANT) ---\n"
                "Each object in the `valid_codes` list MUST have two keys:\n"
                "1. `code`: string\n"
                "2. `description`: string\n\n"
                "**A list of strings like `[\"00\"]` is INVALID for `valid_codes`.**\n\n"
                "**EXAMPLE of a CORRECT `BaseElement` with `valid_codes`:**\n"
                "```json\n"
                "          {{\n"
                "            \"xid\": \"BHT02\",\n"
                "            \"data_ele\": 353,\n"
                "            \"name\": \"Transaction Set Purpose Code\",\n"
                "            \"usage\": \"R\",\n"
                "            \"seq\": 2,\n"
                "            \"dataType\": \"ID\",\n"
                "            \"valid_codes\": [\n"
                "              {{ \"code\": \"00\", \"description\": \"Original\" }},\n"
                "              {{ \"code\": \"18\", \"description\": \"Reissue\" }}\n"
                "            ]\n"
                "          }}\n"
                "```"
            ),
            expected_output="A single, valid `UniversalAgentResponse` JSON object that strictly adheres to the specified Pydantic models.",
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