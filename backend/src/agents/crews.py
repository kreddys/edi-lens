# FILE: backend/src/agents/crews.py
import logging
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from .llm import get_llm
from .tools import KnowledgeBaseTool, EDI_Schema_Lookup_Tool 
from .models import UniversalAgentResponse, AuditResponse

logger = logging.getLogger(__name__)

def _is_verbose_mode_enabled():
    return os.getenv('AGENT_VERBOSE', 'false').lower() == 'true'

@CrewBase
class SchemaEnrichmentCrews:
    def __init__(self):
        self.rag_tool = KnowledgeBaseTool()
        self.schema_lookup_tool = EDI_Schema_Lookup_Tool()
        self.search_tool = SerperDevTool()
        self.llm = get_llm()
        self.element_enrichment_agent_instance = self.element_enrichment_agent()
        self.complex_rule_extraction_agent_instance = self.complex_rule_extraction_agent()
        self.auditor_agent_instance = self.auditor_agent()

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
            tools=[self.rag_tool, self.schema_lookup_tool, self.search_tool],
            llm=self.llm,
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
            llm=self.llm,
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=AuditResponse
        )

    @agent
    def complex_rule_extraction_agent(self) -> Agent:
        return Agent(
            role="EDI Complex Rule Analyst",
            goal="Extract complex rules from text and place them within a standard response object.",
            backstory=(
                "You are a logic expert. Your sole purpose is to create a `UniversalAgentResponse` object. "
                "You must first provide your step-by-step `reasoning`, then populate the `complex_rules` field with your findings. "
                "The `patches` field MUST be an empty list. You follow the requested output format perfectly."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=UniversalAgentResponse
        )

    @task
    def element_enrichment_task(self) -> Task:
        return Task(
            description=(
                "Your task is to analyze the schema for the '{segment_id}' segment, specifically within the '{context_id}' context, and propose a JSON patch if and only if it is incomplete or incorrect according to your information gathering.\n\n"
                "**CRITICAL INSTRUCTIONS FOR CONSTRUCTING JSON PATCHES:**\n"
                "1.  **GOAL:** Your primary goal is to find **DIFFERENCES** between an implementation guide and our current schema. If they **ALREADY MATCH**, you MUST return an empty `patches` list.\n"
                "2.  **JSON PATCH PATHS:** You MUST use one of these two exact formats for the `path`:\n"
                "    -   For a BASE segment definition: `/segmentDefinitions/SEGMENT_ID` (e.g., `/segmentDefinitions/CLM`)\n"
                "    -   For a CONTEXTUAL segment override: `/contextualDefinitions/CONTEXT_ID` (e.g., `/contextualDefinitions/2300.CLM`)\n\n"
                "3.  **THE READ-MODIFY-WRITE PATTERN (MOST IMPORTANT RULE):** The `value` of your patch operation (`add` or `replace`) MUST ALWAYS be a COMPLETE, VALID, and SELF-CONTAINED object. NEVER provide partial objects.\n"
                "    -   **Step A (READ):** ALWAYS start by using the `EDI_Schema_Lookup_Tool` to get the `baseDefinition` and any existing `contextualDefinition`.\n"
                "    -   **Step B (MODIFY):** Create a *new* complete object in your thought process. \n"
                "        - If a `baseDefinition` exists, start by copying it.\n"
                "        - If a `contextualDefinition` exists, apply its overrides to your copy.\n"
                "        - Finally, apply the NEW rules from the `KnowledgeBaseTool` to your copy.\n"
                "    -   **Step C (WRITE):** Your final patch's `value` MUST be the complete, merged object from Step B. Do not just include the fields you changed.\n\n"
                "4.  **CREATING NEW DEFINITIONS:** If the `EDI_Schema_Lookup_Tool` returns `null` for a definition, you must create it from scratch using your intrinsic knowledge (Tier 3) and information from the RAG tool (Tier 1). The created `value` must still be a COMPLETE `SegmentDefinition` or `ContextualDefinition` object.\n"
                "5.  **USAGE CODES:** `usage` properties MUST be one of: `\"R\"` (Required), `\"S\"` (Situational), or `\"N\"` (Not Used).\n\n"
                "**INFORMATION GATHERING HIERARCHY:**\n"
                "-   **Tier 1 (RAG):** Use `KnowledgeBaseTool` first to get specific guide rules.\n"
                "-   **Tier 2 (Internal Schema):** ALWAYS use `EDI_Schema_Lookup_Tool` to see what already exists.\n"
                "-   **Tier 3 (Intrinsic Knowledge):** Use your internal knowledge of X12 standards to construct complete base definitions when they are missing.\n\n"
                "Your final output is a `UniversalAgentResponse` Pydantic object. Your `reasoning` field must explain the tiers you used and how you constructed the final `value`. The `patches` field will contain your proposed changes."
            ),
            expected_output="A single, valid `UniversalAgentResponse` JSON object.",
            agent=self.element_enrichment_agent_instance,
        )

    @task
    def refinement_task(self) -> Task:
        """A task for the Architect to correct its own work based on feedback."""
        return Task(
            description=(
                "Your previous proposal was rejected by the Auditor. You must correct it.\n\n"
                "**Original Task:** Analyze the schema for the '{segment_id}' segment within the '{context_id}' context.\n"
                "**Your Previous (Rejected) Proposal:**\n"
                "```json\n{previous_proposal}\n```\n\n"
                "**Auditor's Rejection Justification:** {audit_feedback}\n\n"
                "**Your Task:**\n"
                "Carefully read the Auditor's justification. Re-evaluate your previous proposal and generate a NEW, corrected `UniversalAgentResponse`. "
                "Fix the specific errors the Auditor pointed out. Do not repeat your mistakes. "
                "You may use your tools again if necessary to gather more information to fix the issue.\n\n"
                "**Crucially, your new proposal MUST be a complete `UniversalAgentResponse` object, including the `reasoning` field explaining your corrected approach.**"
            ),
            expected_output="A new, corrected, and valid `UniversalAgentResponse` JSON object that addresses the auditor's feedback.",
            agent=self.element_enrichment_agent_instance
        )

    @task
    def audit_enrichment_task(self) -> Task:
        return Task(
            description=(
                "You are an EDI Compliance Auditor. Your task is to validate a JSON Patch proposal from another agent. Your analysis must be rigorous and detail-oriented.\n\n"
                "**Proposal to Review:**\n"
                "```json\n"
                "{proposal}\n"
                "```\n\n"
                "**Your Validation Checklist & Rules:**\n"
                "1.  **Presence of Reasoning:** The `reasoning` field MUST be present and non-empty.\n"
                "2.  **Path Correctness:** The JSON patch `path` MUST be either `/segmentDefinitions/SEGMENT_ID` or `/contextualDefinitions/CONTEXT_ID`.\n"
                "3.  **Value Completeness:** The `value` of the patch (`add` or `replace`) MUST be a COMPLETE and valid object. Partial objects are an immediate failure.\n"
                "4.  **Usage Code Validity:** All `usage` properties inside the `value` MUST be exactly `\"R\"`, `\"S\"`, or `\"N\"`.\n"
                "5.  **Logical Consistency:** The final patch MUST logically achieve what the `reasoning` field claims.\n\n"
                "Your final answer MUST be a single, valid `AuditResponse` JSON object. "
                "Provide your final verdict in the `approved` field (true/false) and your concise analysis in the `reasoning` field."
            ),
            expected_output="A single, valid `AuditResponse` JSON object.",
            agent=self.auditor_agent_instance
        )


    @task
    def complex_rule_extraction_task(self) -> Task:
        return Task(
            description=(
                "Your task is to create a `UniversalAgentResponse` object containing complex rules from the `guide_text_chunk`.\n\n"
                "**Instructions**:\n"
                "1. Use the 'EDI Guide Knowledge Base Tool' ONCE to get the `guide_text_chunk`.\n"
                "2. In your `reasoning`, quote the exact sentence from the text that justifies every rule.\n"
                "3. Your final output MUST be a single JSON object. The `patches` list MUST be empty.\n\n"
            ),
            expected_output="A single, valid JSON object that perfectly matches the `UniversalAgentResponse` Pydantic model.",
            agent=self.complex_rule_extraction_agent_instance,
        )

    @crew
    def element_enrichment_crew(self) -> Crew:
        return Crew(
            agents=[self.element_enrichment_agent_instance],
            tasks=[self.element_enrichment_task()],
            process=Process.sequential,
            verbose=_is_verbose_mode_enabled()
        )

    @crew
    def complex_rule_extraction_crew(self) -> Crew:
        return Crew(
            agents=[self.complex_rule_extraction_agent_instance],
            tasks=[self.complex_rule_extraction_task()],
            process=Process.sequential,
            verbose=_is_verbose_mode_enabled()
        )