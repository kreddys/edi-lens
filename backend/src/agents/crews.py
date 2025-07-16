# FILE: backend/src/agents/crews.py
import logging
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, Field

from .llm import get_llm
from .refinement_engine.rag_tool import RAGTool
from .refinement_engine.models import (
    StructuralChange, StructuralChangeProposal,
    ContextualLink, ContextualLinkProposal,
    ElementEnrichment, ElementEnrichmentProposal,
    ComplexRule, ComplexRuleProposal
)

logger = logging.getLogger(__name__)

@CrewBase
class SchemaEnrichmentCrews:
    """
    A collection of specialized agent crews that form a "Schema Assembly Line"
    to generate and enrich an EDI schema from an implementation guide.
    """
    def __init__(self, rag_tool: RAGTool):
        self.rag_tool = rag_tool
        self.llm = get_llm()
        # --- THIS IS THE FIX ---
        # Instantiate the agents in the constructor so they are objects, not methods.
        self.structural_integrity_agent_instance = self.structural_integrity_agent()
        self.contextualization_agent_instance = self.contextualization_agent()
        self.element_enrichment_agent_instance = self.element_enrichment_agent()
        self.complex_rule_extraction_agent_instance = self.complex_rule_extraction_agent()
        # --- END OF FIX ---

    # --- AGENT DEFINITIONS ---

    @agent
    def structural_integrity_agent(self) -> Agent:
        return Agent(
            role="EDI Structural Architect",
            goal="Ensure the schema's hierarchical structure perfectly matches the implementation guide's table of contents by identifying and adding any missing loops or segments.",
            backstory=(
                "You are a meticulous architect focused solely on the blueprint of an EDI transaction. "
                "You ignore the fine details of elements and rules, concentrating only on the high-level structure. "
                "Your job is to compare the guide's intended hierarchy (its table of contents) with the existing schema's structure and add any missing pieces to create a perfect, complete skeleton."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            output_pydantic=StructuralChangeProposal
        )

    @agent
    def contextualization_agent(self) -> Agent:
        return Agent(
            role="EDI Contextual Linker",
            goal="Identify segments within the schema structure that have a special, context-specific meaning and create the necessary links and placeholders for their unique definitions.",
            backstory=(
                "You are a librarian of EDI semantics. You understand that a segment's meaning changes with its location. "
                "You traverse the schema's structure, and for each segment, you consult the guide to determine its specific role (e.g., 'Billing Provider Name' vs. 'Subscriber Name'). "
                "You don't write the full definitions; you simply create the 'card catalog' entry (`contextId`) and the empty placeholder, preparing the way for the detail-oriented agents."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            output_pydantic=ContextualLinkProposal
        )

    @agent
    def element_enrichment_agent(self) -> Agent:
        return Agent(
            role="EDI Element Detail Specialist",
            goal="Flesh out the definitions of individual segments by adding all element-level details from the guide, such as descriptions, data types, code values, and length constraints.",
            backstory=(
                "You are a detail-oriented technical writer, a master of specifications. You are given a single segment to focus on. "
                "You meticulously read the corresponding section of the implementation guide and transfer every piece of element-specific information—descriptions, usage notes, data types, valid codes, and min/max lengths—into the JSON schema. "
                "You also identify and add any elements that are completely missing from the base definition."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            output_pydantic=ElementEnrichmentProposal
        )

    @agent
    def complex_rule_extraction_agent(self) -> Agent:
        return Agent(
            role="EDI Complex Rule Analyst",
            goal="Extract all complex, conditional, and relational validation rules from the implementation guide and codify them into a structured, machine-readable JSON format.",
            backstory=(
                "You are a logic and syntax expert. You read between the lines of the implementation guide, searching for the complex business rules that govern the entire transaction. "
                "You ignore simple element properties and focus on sentences containing keywords like 'if', 'when', 'then', 'required', 'must not', and 'must balance'. "
                "Your sole purpose is to translate this complex business logic into a clear, data-driven JSON format that a validation engine can execute."
            ),
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            output_pydantic=ComplexRuleProposal
        )

    # --- TASK DEFINITIONS ---

    @task
    def structural_integrity_task(self) -> Task:
        return Task(
            description=(
                "Analyze the provided `guide_toc` (Table of Contents from the implementation guide) and compare it against the `current_schema_structure`. "
                "Identify any loops or segments present in the guide's TOC that are completely missing from the schema structure. "
                "For each missing item, create a `StructuralChange` object specifying its `xid`, `type`, `name`, and the `parentLoopId` where it should be inserted. "
                "Your final output must be a `StructuralChangeProposal` object."
            ),
            expected_output="A single, valid JSON object matching the `StructuralChangeProposal` Pydantic model.",
            # --- THIS IS THE FIX ---
            agent=self.structural_integrity_agent_instance,
            output_json=StructuralChangeProposal
        )

    @task
    def contextualization_task(self) -> Task:
        return Task(
            description=(
                "You will be given the full `schema_structure` and a specific `loop_id` to analyze. "
                "For each segment within that loop, use the 'Documentation Query Tool' to find its specific name or role (e.g., 'Billing Provider Name' for an NM1 in loop 2010AA). "
                "If a segment has a specific role, create a `ContextualLink` object containing the `loopId`, `segmentId`, and a new `contextId` (formatted as 'LOOP_ID.SEGMENT_ID'). "
                "Your final output must be a `ContextualLinkProposal` object."
            ),
            expected_output="A single, valid JSON object matching the `ContextualLinkProposal` Pydantic model.",
            agent=self.contextualization_agent_instance,
            output_json=ContextualLinkProposal
        )

    @task
    def element_enrichment_task(self) -> Task:
        return Task(
            description=(
                "You will be given a `segment_id`, its `context_id` (if any), and its `current_definition_json`. "
                "Your task is to enrich this definition. Use the 'Documentation Query Tool' with a very specific query to get the relevant guide text. "
                "Extract and add all missing details: element descriptions, data types, min/max lengths, and full `valid_codes` lists. "
                "Also, identify any elements mentioned in the guide but missing from the definition. "
                "Your final output must be an `ElementEnrichmentProposal` object containing the JSON patch operations needed to update the definition."
            ),
            expected_output="A single, valid JSON object matching the `ElementEnrichmentProposal` Pydantic model, containing a list of JSON Patch operations.",
            agent=self.element_enrichment_agent_instance,
            output_json=ElementEnrichmentProposal
        )

    @task
    def complex_rule_extraction_task(self) -> Task:
        return Task(
            description=(
                "Analyze the provided `guide_text_chunk`. Your goal is to identify and extract ONLY complex, conditional, or relational rules. "
                "Ignore simple properties like data types or code lists. Focus on rules that span multiple elements or segments (e.g., 'If X, then Y is required'). "
                "For each rule found, create a `ComplexRule` object, filling in all fields, especially the `type`, `conditions`, and `action`. "
                "Your final output must be a `ComplexRuleProposal` object."
            ),
            expected_output="A single, valid JSON object matching the `ComplexRuleProposal` Pydantic model.",
            agent=self.complex_rule_extraction_agent_instance,
            output_json=ComplexRuleProposal
        )

    # --- CREW DEFINITIONS ---

    @crew
    def structural_integrity_crew(self) -> Crew:
        return Crew(agents=[self.structural_integrity_agent_instance], tasks=[self.structural_integrity_task()], process=Process.sequential, verbose=True)

    @crew
    def contextualization_crew(self) -> Crew:
        return Crew(agents=[self.contextualization_agent_instance], tasks=[self.contextualization_task()], process=Process.sequential, verbose=True)

    @crew
    def element_enrichment_crew(self) -> Crew:
        return Crew(agents=[self.element_enrichment_agent_instance], tasks=[self.element_enrichment_task()], process=Process.sequential, verbose=True)

    @crew
    def complex_rule_extraction_crew(self) -> Crew:
        return Crew(agents=[self.complex_rule_extraction_agent_instance], tasks=[self.complex_rule_extraction_task()], process=Process.sequential, verbose=True)