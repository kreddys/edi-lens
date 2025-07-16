# FILE: backend/src/agents/crews.py
import logging
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from typing import List, Dict, Any

from .llm import get_llm
from .refinement_engine.rag_tool import RAGTool
from .refinement_engine.models import (
    ElementEnrichmentProposal,
    ComplexRuleProposal
)

logger = logging.getLogger(__name__)

def _is_verbose_mode_enabled():
    """Helper to control verbosity based on a single environment variable."""
    return os.getenv('AGENT_VERBOSE', 'false').lower() == 'true'

@CrewBase
class SchemaEnrichmentCrews:
    # ... __init__ is unchanged ...
    def __init__(self, rag_tool: RAGTool):
        self.rag_tool = rag_tool
        self.llm = get_llm()
        self.element_enrichment_agent_instance = self.element_enrichment_agent()
        self.complex_rule_extraction_agent_instance = self.complex_rule_extraction_agent()

    # --- AGENT DEFINITIONS (Unchanged) ---
    @agent
    def element_enrichment_agent(self) -> Agent:
        return Agent(
            role="EDI Element Detail Specialist",
            goal="Generate a precise JSON patch to align a given JSON definition with the guide's specifications by first consulting the documentation, then identifying discrepancies, and finally creating the patch.",
            backstory=(
                "You are a meticulous and obedient JSON Patch specialist for EDI schemas. "
                "Your thought process MUST begin with using the 'Documentation Query Tool' to find the specifications for the given segment. This is not optional. "
                "After retrieving the documentation, your primary job is to compare the provided JSON to that documentation and generate a JSON patch array (`op`, `path`, `value`) to fix it. "
                "You ONLY generate patches for what is explicitly different or missing. If the definition is already correct after consulting the guide, you return an empty patch array. "
                "You do not hallucinate or add properties not mentioned in the guide."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=ElementEnrichmentProposal
        )

    @agent
    def complex_rule_extraction_agent(self) -> Agent:
        return Agent(
            role="EDI Complex Rule Analyst",
            goal="Extract all complex, conditional, and relational validation rules from the implementation guide and codify them into a structured, machine-readable JSON format, adhering strictly to the provided Pydantic model.",
            backstory=(
                "You are a logic and syntax expert. You read between the lines of the implementation guide, searching for the complex business rules that govern the entire transaction. "
                "You ignore simple element properties and focus on sentences containing keywords like 'if', 'when', 'then', 'required', 'must not', and 'must balance'. "
                "Your sole purpose is to translate this complex business logic into a clear, data-driven JSON format that a validation engine can execute. You follow the requested output format perfectly."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=ComplexRuleProposal
        )

    # --- TASK DEFINITIONS (This is the key change) ---

    @task
    def element_enrichment_task(self) -> Task:
        # We now use f-strings to dynamically insert the segment ID into the prompt.
        # This makes the instructions extremely specific to the current run.
        return Task(
            description=(
                "You are a JSON Patch specialist for EDI schemas. Your task is to align the JSON definition for the '{segment_id}' segment.\n"
                "The current definition is: {current_definition_json}\n\n"
                "Your process MUST be:\n"
                "1. Use the 'Documentation Query Tool' to get the ground-truth specifications for the '{segment_id}' segment. Your query must be specific to '{segment_id}'.\n"
                "2. Compare the `current_definition_json` against the documentation you retrieved. Pay close attention to keywords.\n"
                "   - The word 'Required' in the guide MUST map to a 'usage' value of 'R'.\n"
                "   - The word 'Situational' or 'Optional' in the guide MUST map to a 'usage' value of 'S'.\n"
                "3. Generate a list of JSON Patch operations to correct any discrepancies for the '{segment_id}' segment.\n"
                "4. CRITICAL: If the definition is already correct, you MUST return an empty list `[]`.\n"
                "5. Your final output MUST be a valid JSON object matching the `ElementEnrichmentProposal` model."
            ),
            expected_output=(
                "A single, valid JSON object matching the `ElementEnrichmentProposal` Pydantic model, "
                "containing a list of JSON Patch operations for the '{segment_id}' segment. For example: "
                '`{"patches": [{"op": "replace", "path": "/elements/0/usage", "value": "R"}]}` or `{"patches": []}` if no changes are needed.'
            ),
            agent=self.element_enrichment_agent_instance,
            output_json=ElementEnrichmentProposal
        )

    # ... (complex_rule_extraction_task is unchanged) ...
    @task
    def complex_rule_extraction_task(self) -> Task:
        return Task(
            description=(
                "Analyze the provided `guide_text_chunk`. Your goal is to identify and extract ONLY complex, conditional, or relational rules. "
                "Ignore simple properties like data types or code lists. Focus on rules that span multiple elements or segments (e.g., 'If X, then Y is required').\n"
                "For each rule found, create a `ComplexRule` object, filling in all fields, especially the `type`, `conditions`, and `action`.\n"
                "For example, for the text \"When the REF01 element contains the code 'G2', then the REF02 element is required.\", your extracted rule should look like:\n"
                "```json\n"
                "{\n"
                "  \"rules\": [\n"
                "    {\n"
                "      \"ruleId\": \"REF_conditional_G2\",\n"
                "      \"description\": \"If REF01 is 'G2', then REF02 is required.\",\n"
                "      \"citation\": \"Guide Section 2.1\",\n"
                "      \"appliesTo\": {\"segment\": \"REF\"},\n"
                "      \"conditions\": {\n"
                "        \"logicalOperator\": \"AND\",\n"
                "        \"expressions\": [{\"field\": \"REF01\", \"operator\": \"equals\", \"value\": \"G2\"}]\n"
                "      },\n"
                "      \"action\": {\"type\": \"REQUIRE_PAIRED_ELEMENTS\", \"elements\": [\"REF02\"]}\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "```\n"
                "Your final output must be a `ComplexRuleProposal` object containing a list of all such extracted rules."
            ),
            expected_output="A single, valid JSON object matching the `ComplexRuleProposal` Pydantic model.",
            agent=self.complex_rule_extraction_agent_instance,
            output_json=ComplexRuleProposal
        )
        
    # --- CREW DEFINITIONS (Unchanged) ---
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