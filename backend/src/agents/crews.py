# FILE: backend/src/agents/crews.py
import logging
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field

from .llm import get_llm
from .refinement_engine.rag_tool import RAGTool

logger = logging.getLogger(__name__)

# --- Pydantic Models for Structured Output ---

class ProposedChange(BaseModel):
    """Pydantic model for a single proposed change to the schema."""
    change_type: Literal["MODIFY_ELEMENT", "ADD_ELEMENT", "UPDATE", "ADD"] = Field(..., description="The type of change to perform.")
    element_id: str = Field(..., description="The ID of the element to change (e.g., 'CLM02').")
    human_readable_reason: str = Field(..., description="A brief, clear explanation of why the change is needed.")
    citation: str = Field(..., description="The EXACT sentence or phrase from the documentation that proves the change is necessary.")
    proposed_changes: Dict[str, Any] = Field(..., description="A JSON object of the new values to apply.")

class ChangeProposal(BaseModel):
    """Pydantic model for the list of proposed changes, which is the final output of the analysis task."""
    proposals: List[ProposedChange] = Field(default=[], description="A list of proposed changes. Must be an empty list if no changes are needed.")

@CrewBase
class SchemaEnrichmentCrews:
    """A crew designed to enrich a base schema with details from documentation."""
    def __init__(self, rag_tool: RAGTool):
        self.rag_tool = rag_tool
        self.llm = get_llm()

    # --- Agent Definitions ---
    @agent
    def analyst(self) -> Agent:
        return Agent(
            role="EDI Schema Analyst",
            goal="Compare a segment's existing JSON definition with its text documentation, identify all discrepancies or missing details, and create a structured list of required changes.",
            backstory='''You are a meticulous JSON auditing agent. You are a machine that follows instructions perfectly.
You compare an existing JSON implementation against a detailed text specification.
Your job is to find every single piece of missing information, every incorrect value, and every incomplete description.''',
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def architect(self) -> Agent:
        return Agent(
            role='EDI Schema Design Architect',
            goal='Given a specific, single task and a segment\'s JSON, generate a precise JSON Patch object (RFC 6902) to perform ONLY that task.',
            backstory="You are a JSON surgeon. You perform micro-operations. You receive a single, clear instruction (e.g., 'add element X', 'change usage of Y') and a JSON document. You generate a minimal, perfect JSON Patch to execute that one instruction. You never combine tasks.",
            tools=[],
            llm=self.llm,
            verbose=True
        )

    # --- Task Definitions ---
    @task
    def analysis_task(self) -> Task:
        return Task(
            description="""Analyze Segment Definition: You are an auditor comparing a JSON definition against a text document.
                The text document provided by the 'Documentation Query Tool' is your ONLY source of truth.
                Do NOT use any of your pre-existing knowledge about EDI standards.
                Your task is to identify discrepancies ONLY for the elements and properties explicitly mentioned in the retrieved text.

                1. You will be given a segment ID (e.g., 'CLM') and its current JSON definition.
                2. Use the 'Documentation Query Tool' ONE TIME with the given segment ID to retrieve its documentation.
                3. Perform a strict comparison between the retrieved text and the provided JSON.
                4. For each discrepancy, create a change object. A discrepancy ONLY exists if the text provides a value that is different from the JSON, or if the text describes an element that is completely missing from the JSON.
                   - If an element's property is incorrect (e.g., usage is 'S' but should be 'R'), the `change_type` MUST be 'MODIFY_ELEMENT'. The `proposed_changes` object MUST contain ONLY the key-value pairs that need to be changed, for example: `{{"usage": "R"}}`.
                   - If an element is completely missing from the definition, the `change_type` MUST be 'ADD_ELEMENT'. The `proposed_changes` object MUST contain the full definition of the new element to be added, including its `xid`, `name`, and `usage` parsed from the documentation. For example: `{{"xid": "SBR01", "name": "Payer Responsibility Sequence Number Code", "usage": "R"}}`.
                5. If an element exists in the JSON but is NOT mentioned in the retrieved text, you MUST ignore it. DO NOT propose to remove it.
                6. YOUR FINAL ANSWER MUST BE A JSON OBJECT containing a list of these change objects. If no changes are needed, you MUST return an object with an empty list.

                **CRITICAL RULE 1: ADHERE STRICTLY TO THE PROVIDED DOCUMENTATION**: You are absolutely forbidden from proposing a change or addition for an element if that element is not explicitly described in the retrieved documentation. Do not use your own knowledge to 'fill in the blanks'.
                **EXAMPLE OF WHAT NOT TO DO**: If the documentation for segment 'ST' only mentions 'ST-01', you MUST NOT propose to add 'ST-02', even if you know 'ST-02' typically exists. Your knowledge comes ONLY from the text provided by the tool. If the text doesn't mention it, it doesn't exist for the purpose of this task.

                **CRITICAL RULE 2: PROVIDE CITATIONS**: Every change object you propose MUST include a "citation" field containing the exact quote from the documentation that justifies the change. If you cannot find a quote, you cannot propose the change.

                **CRITICAL RULE 3: NORMALIZE IDs**: The `element_id` and the `xid` in `proposed_changes` MUST be normalized by removing any hyphens (e.g., 'SBR-01' from the documentation becomes 'SBR01').

                Context:
                - Segment ID: {segment_id}
                - Current JSON Definition: {current_definition_json}
            """,
            expected_output="""A list of proposed changes. Must be an empty list if no changes are needed.""",
            agent=self.analyst(),
            output_pydantic=ChangeProposal,
        )

    @task
    def patch_generation_task(self) -> Task:
        return Task(
            description="""Generate JSON Patch: You are a JSON Patch specialist. Your task is to convert a single, specific change request into a valid JSON Patch (RFC 6902) array.
                The patch's 'path' MUST be a valid JSON Pointer, starting from the root of the provided segment definition.
                For example, to change the usage of the second element, the path would be `/elements/1/usage`.

                Current Segment Definition:
                {current_definition_json}

                Specific Change to Implement:
                {task_json}
            """,
            expected_output="""
                A valid JSON array formatted as a standard JSON Patch (RFC 6902).
                Do not add any explanations or markdown.

                Example for modifying an element:
                [
                    { "op": "replace", "path": "/elements/1/usage", "value": "R" }
                ]

                Example for adding an element:
                [
                    { "op": "add", "path": "/elements/-", "value": {"xid": "CLM09", "name": "Release of Information Code", "usage": "R", "seq": "09"} }
                ]
            """,
            agent=self.architect()
        )

    # --- Crew Definitions ---
    @crew
    def analysis_crew(self) -> Crew:
        return Crew(
            agents=[self.analyst()],
            tasks=[self.analysis_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def architect_crew(self) -> Crew:
        return Crew(
            agents=[self.architect()],
            tasks=[self.patch_generation_task()],
            process=Process.sequential,
            verbose=True
        )