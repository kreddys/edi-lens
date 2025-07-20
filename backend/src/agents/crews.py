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
                "**Critical Instructions:**\n"
                "- Your primary goal is to find **DIFFERENCES** between an implementation guide and the current schema.\n"
                "- If they **ALREADY MATCH**, you MUST return an empty `patches` list.\n"
                "- **Usage Code Mapping:** When setting a `usage` property, you MUST use one of the following exact single-character codes:\n"
                "  - 'Required' or 'Mandatory' -> `\"R\"`\n"
                "  - 'Situational' or 'Optional' -> `\"S\"`\n"
                "  - 'Not Used' -> `\"N\"`\n"
                "- **JSON Patch Path Rules:**\n"
                "  1. For a new BASE segment: `/segmentDefinitions/SEGMENT_ID`\n"
                "  2. For a new or existing CONTEXTUAL override: `/contextualDefinitions/CONTEXT_ID`\n\n"
                "- **Method for `contextualDefinitions`:** To create or update a contextual definition, you MUST follow a READ-MODIFY-WRITE pattern. First, use the `EDI_Schema_Lookup_Tool` to get the `contextualDefinition` (if it exists) and the `baseDefinition`. Then, construct the new complete `value` for your patch by merging the base, the existing context (if any), and the new rules from the guide. Your final `value` must be a complete, valid `ContextualDefinition` object. DO NOT provide partial values.\n"
                "- **Creating `segmentDefinitions` (Tier 3):** The `value` MUST be a complete `SegmentDefinition` object with an `elements` LIST.\n"
                "- **`valid_codes` Structure:** The `valid_codes` property is ALWAYS an object with a `codes` key, which holds a LIST of code objects (e.g., `{{\"code\": \"QC\", \"description\": \"Patient\"}}`).\n"
                "\nYou MUST follow this Four-Tier Information Hierarchy STRICTLY:\n\n"
                "1.  **Tier 1 (RAG):** Use `KnowledgeBaseTool` first.\n"
                "2.  **Tier 2 (Internal Schema):** Use `EDI_Schema_Lookup_Tool` if RAG is insufficient.\n"
                "3.  **Tier 3 (Intrinsic Knowledge):** Generate from training data if Tiers 1 & 2 fail.\n"
                "4.  **Tier 4 (Internet Search):** Use `SerperDevTool` as a last resort.\n\n"
                "Your final output is a `UniversalAgentResponse` Pydantic object. Your `reasoning` field must explain the tiers you used. The `patches` field will contain your proposed changes."
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
                "You may use your tools again if necessary to gather more information to fix the issue."
            ),
            expected_output="A new, corrected, and valid `UniversalAgentResponse` JSON object that addresses the auditor's feedback.",
            agent=self.element_enrichment_agent_instance
        )

    @task
    def audit_enrichment_task(self) -> Task:
        return Task(
            description=(
                "You are an EDI Compliance Auditor. Validate the following proposal from the Architect Agent.\n\n"
                "**Proposal to Review:**\n"
                "```json\n"
                "{proposal}\n"
                "```\n\n"
                "**Your Validation Checklist:**\n"
                "1.  **Reasoning Review:** Is the `reasoning` logical and does it cite the correct Tiers?\n"
                "2.  **Path Correctness:** Does the JSON patch `path` match the reasoning?\n"
                "3.  **Value Structure:** Does the patch `value` represent a COMPLETE and valid object for its target path? Partial objects are not allowed.\n"
                "4.  **Logical Consistency:** Does the patch achieve what the reasoning claims?\n\n"
                "Your final answer MUST be a single, valid `AuditResponse` JSON object with your verdict (`approved`: true/false) and a clear `justification`."
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