# FILE: backend/src/agents/crews.py
import logging
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from .llm import get_llm
from .tools.rag import KnowledgeBaseTool
from .models import UniversalAgentResponse

logger = logging.getLogger(__name__)

def _is_verbose_mode_enabled():
    return os.getenv('AGENT_VERBOSE', 'false').lower() == 'true'

@CrewBase
class SchemaEnrichmentCrews:
    # ... __init__ and agent definitions are correct ...
    def __init__(self):
        self.rag_tool = KnowledgeBaseTool()
        self.llm = get_llm()
        self.element_enrichment_agent_instance = self.element_enrichment_agent()
        self.complex_rule_extraction_agent_instance = self.complex_rule_extraction_agent()

    @agent
    def element_enrichment_agent(self) -> Agent:
        return Agent(
            role="EDI Element Detail Specialist",
            goal="Generate a precise JSON patch proposal within a standard response object.",
            backstory=(
                "You are a meticulous JSON Patch specialist. Your sole purpose is to create a `UniversalAgentResponse` object. "
                "You must first provide your step-by-step `reasoning`, then populate the `element_enrichment` field with your findings. "
                "The `complex_rules` field MUST be null. You follow the requested output format perfectly."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=_is_verbose_mode_enabled(),
            allow_delegation=False,
            output_pydantic=UniversalAgentResponse
        )

    @agent
    def complex_rule_extraction_agent(self) -> Agent:
        return Agent(
            role="EDI Complex Rule Analyst",
            goal="Extract complex rules from text and place them within a standard response object.",
            backstory=(
                "You are a logic expert. Your sole purpose is to create a `UniversalAgentResponse` object. "
                "You must first provide your step-by-step `reasoning`, then populate the `complex_rules` field with your findings. "
                "The `element_enrichment` field MUST be null. You follow the requested output format perfectly."
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
                # --- THIS IS THE FINAL FIX ---
                # Be hyper-specific about the keyword-to-code mapping to prevent the LLM
                # from using its own abbreviations like 'O' for optional.
                "Your task is to create a `UniversalAgentResponse` object for the '{segment_id}' segment.\n"
                "**Current Definition**: {current_definition_json}\n\n"
                "**Instructions**:\n"
                "1. Use the 'EDI Guide Knowledge Base Tool' ONCE to get the `guide_text`. This is your ONLY source of truth.\n"
                "2. Your `reasoning` MUST quote the `guide_text` to justify every patch.\n"
                "3. **Usage Mapping Rules**: When creating a patch, you MUST use the following exact mappings:\n"
                "   - Text: 'Required', 'Mandatory', 'Must Use'  ->  JSON: `\"usage\": \"R\"`\n"
                "   - Text: 'Situational', 'Optional'            ->  JSON: `\"usage\": \"S\"`\n"
                "4. Your final output MUST be a single JSON object. Copy and paste the following structure and fill it in:\n\n"
                "```json\n"
                '{{\n'
                '  "reasoning": "YOUR_REASONING_HERE_INCLUDING_QUOTES",\n'
                '  "element_enrichment": {{\n'
                '    "patches": [\n'
                '      // EXAMPLE: {{"op": "add", "path": "/elements/0", "value": {{"xid": "CLM09", "name": "Element Name", "usage": "S"}}}}\n'
                '    ]\n'
                '  }},\n'
                '  "complex_rules": null\n'
                '}}\n'
                "```"
                # --- END OF FIX ---
            ),
            expected_output="A single, valid JSON object that perfectly matches the `UniversalAgentResponse` Pydantic model.",
            agent=self.element_enrichment_agent_instance,
        )
    
    @task
    def complex_rule_extraction_task(self) -> Task:
        # This task is working correctly, no changes needed.
        return Task(
            description=(
                "Your task is to create a `UniversalAgentResponse` object containing complex rules from the `guide_text_chunk`.\n\n"
                "**Instructions**:\n"
                "1. Use the 'EDI Guide Knowledge Base Tool' ONCE to get the `guide_text_chunk`.\n"
                "2. In your `reasoning`, quote the exact sentence from the text that justifies every rule.\n"
                "3. Your final output MUST be a single JSON object. Copy and paste this structure and fill it in:\n\n"
                "```json\n"
                '{{\n'
                '  "reasoning": "YOUR_REASONING_HERE_INCLUDING_QUOTES",\n'
                '  "element_enrichment": null,\n'
                '  "complex_rules": {{\n'
                '    "rules": [\n'
                '      {{\n'
                '        "ruleId": "UNIQUE_RULE_ID",\n'
                '        "description": "HUMAN_READABLE_DESCRIPTION",\n'
                '        "citation": "From guide text",\n'
                '        "appliesTo": {{ "segment": "SEGMENT_ID" }},\n'
                '        "conditions": {{\n'
                '          "logicalOperator": "AND",\n'
                '          "expressions": [\n'
                '            {{ "field": "ELEMENT_ID", "operator": "equals", "value": "SOME_VALUE" }}\n'
                '          ]\n'
                '        }},\n'
                '        "action": {{\n'
                '          "type": "REQUIRE_ELEMENT",\n'
                '          "details": {{ "element": "TARGET_ELEMENT_ID" }}\n'
                '        }}\n'
                '      }}\n'
                '    ]\n'
                '  }}\n'
                '}}\n'
                "```"
            ),
            expected_output="A single, valid JSON object that perfectly matches the `UniversalAgentResponse` Pydantic model.",
            agent=self.complex_rule_extraction_agent_instance,
        )

    # ... crews are unchanged ...
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