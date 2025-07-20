# FILE: backend/src/agents/crews.py
import logging
import os
import json
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from .llm import get_llm
from .tools.rag import KnowledgeBaseTool
from .models import ElementEnrichmentProposal, ComplexRuleProposal

logger = logging.getLogger(__name__)

# We no longer need the schema here; the few-shot example is more effective.

def _is_verbose_mode_enabled():
    # ... (this function is fine)
    return os.getenv('AGENT_VERBOSE', 'false').lower() == 'true'

@CrewBase
class SchemaEnrichmentCrews:
    # ... (agent definitions and __init__ are fine) ...
    # ...
    def __init__(self):
        self.rag_tool = KnowledgeBaseTool()
        self.llm = get_llm()
        self.element_enrichment_agent_instance = self.element_enrichment_agent()
        self.complex_rule_extraction_agent_instance = self.complex_rule_extraction_agent()

    @agent
    def element_enrichment_agent(self) -> Agent:
        return Agent(
            role="EDI Element Detail Specialist",
            goal="Generate a precise JSON patch to align a given JSON definition with the guide's specifications by first consulting the documentation, then identifying discrepancies, and finally creating the patch.",
            backstory=(
                "You are a meticulous and obedient JSON Patch specialist for EDI schemas. "
                "You work with two pieces of information: the 'current_definition_json' and the 'guide_text' retrieved from a tool. "
                "Your ONLY job is to generate a JSON patch array (`op`, `path`, `value`) to make the `current_definition_json` match the rules described in the `guide_text`. "
                "You ONLY generate patches for what is explicitly different or missing. If the definition is already correct, you return an empty patch array. "
                "You never invent information or modify elements not mentioned in the guide text."
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
                "You are an expert at translating complex business logic from text into perfectly structured JSON. "
                "Your SOLE purpose is to generate a JSON object that strictly conforms to the provided `ComplexRuleProposal` schema. "
                "You pay extremely close attention to the required fields and the allowed values in `Literal` types within the schema. "
                "Your output will be machine-validated, so precision is paramount. Do not add any conversational text or explanations around the final JSON object."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=ComplexRuleProposal
        )

    @task
    def element_enrichment_task(self) -> Task:
        return Task(
            description=(
                # --- THIS IS THE FIX ---
                # We are adding a strong few-shot example to show the agent EXACTLY how to
                # construct the 'value' for an 'add' operation. This is the most effective
                # way to prevent the "lazy" behavior of only adding the 'xid'.
                "Your task is to create a JSON Patch to modify a `current_definition_json` to match the rules in your retrieved `guide_text`. Follow these steps and the example precisely.\n\n"
                "**EXAMPLE:**\n"
                "--------\n"
                "**`current_definition_json`:**\n"
                "`{{\"elements\": [{{\"xid\": \"CLM01\"}}]}}`\n\n"
                "**`guide_text` from tool:**\n"
                "'The CLM segment contains CLM09 Release of Information, which is Situational.'\n\n"
                "**Correct JSON Patch Output:**\n"
                "```json\n"
                '{{\n'
                '  "patches": [\n'
                '    {{\n'
                '      "op": "add",\n'
                '      "path": "/elements/1",\n'
                '      "value": {{\n'
                '        "xid": "CLM09",\n'
                '        "name": "Release of Information",\n'
                '        "usage": "S"\n'
                '      }}\n'
                '    }}\n'
                '  ]\n'
                '}}\n'
                "```\n"
                "**Logic**: The example shows that you must create a complete element object for the `add` operation's `value`. You must infer the `name` from the text and correctly map the word 'Situational' to a `usage` of 'S'.\n"
                "--------\n\n"
                "**YOUR TASK:**\n"
                "Now, apply this exact same logic to the following inputs for the '{segment_id}' segment:\n"
                "**`current_definition_json`**: {current_definition_json}\n\n"
                "**INSTRUCTIONS**:\n"
                "1. Use the 'EDI Guide Knowledge Base Tool' to get the official `guide_text` for the '{segment_id}' segment.\n"
                "2. Assume the retrieved text is the complete source of truth.\n"
                "3. Compare the `current_definition_json` to the `guide_text`.\n"
                "4. Generate the JSON Patch to fix any issues, following the format from the example above. Remember to map 'Required' to `usage: 'R'` and 'Situational' to `usage: 'S'`.\n"
                "5. If no changes are needed, return `{{\"patches\": []}}`."
                # --- END OF FIX ---
            ),
            expected_output=(
                "A single, valid JSON object that perfectly matches the `ElementEnrichmentProposal` model."
            ),
            agent=self.element_enrichment_agent_instance,
            output_json=ElementEnrichmentProposal
        )
    
    @task
    def complex_rule_extraction_task(self) -> Task:
        return Task(
            description=(
                # --- THIS IS THE FIX for the 'rule extraction' failure ---
                # We remove the huge, overwhelming JSON schema and replace it with a concise,
                # powerful few-shot example. This is much easier for the LLM to follow.
                "Analyze the `guide_text_chunk` to identify and extract all complex, conditional, or relational rules. "
                "Your final output MUST be a single JSON object that strictly conforms to the `ComplexRuleProposal` Pydantic model. "
                "Follow the format in this example precisely.\n\n"
                "**EXAMPLE:**\n"
                "--------\n"
                "**Input Text:**\n"
                "'When the REF01 element contains the code 'G2', then the REF02 element is required.'\n\n"
                "**Correct JSON Output:**\n"
                "```json\n"
                '{{\n'
                '  "rules": [\n'
                '    {{\n'
                '      "ruleId": "REF_G2_Requirement",\n'
                '      "description": "If REF01 is \'G2\', then REF02 must be present.",\n'
                '      "citation": "From guide text",\n'
                '      "appliesTo": {{"segment": "REF"}},\n'
                '      "conditions": {{\n'
                '        "logicalOperator": "AND",\n'
                '        "expressions": [\n'
                '          {{\n'
                '            "field": "REF01",\n'
                '            "operator": "equals",\n'
                '            "value": "G2"\n'
                '          }}\n'
                '        ]\n'
                '      }},\n'
                '      "action": {{\n'
                '        "type": "REQUIRE_ELEMENT",\n'
                '        "details": {{"element": "REF02"}}\n'
                '      }}\n'
                '    }}\n'
                '  ]\n'
                '}}\n'
                "```\n"
                "--------\n"
                "Now, apply this exact same logic and structure to the current `guide_text_chunk`."
                # --- END OF FIX ---
            ),
            expected_output="A single, valid JSON object that perfectly matches the example's structure.",
            agent=self.complex_rule_extraction_agent_instance,
            output_json=ComplexRuleProposal
        )
    # ... (crews are fine) ...
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