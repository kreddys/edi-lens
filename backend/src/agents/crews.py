# FILE: backend/src/agents/crews.py
import logging
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from .llm import get_llm
from .refinement_engine.rag_tool import RAGTool
from .tools import schema_structure_tool, node_definition_tool

logger = logging.getLogger(__name__)


# --- Existing SchemaRefinementCrews (can be left as-is or removed) ---
@CrewBase
class SchemaRefinementCrews:
    """A class to define all crews related to schema refinement."""
    
    def __init__(self, rag_tool: RAGTool):
        self.rag_tool = rag_tool
        self.llm = get_llm()

    @agent
    def planner(self) -> Agent:
        return Agent(
            role='EDI Requirement Analyst',
            goal='Analyze EDI implementation guide documentation to extract all specified schema modification requirements and formulate them into a structured JSON list of tasks.',
            backstory="""You are an expert EDI analyst. Your sole focus is to read technical documentation and accurately translate every stated requirement into a machine-readable task format.
You never miss a requirement and always follow the specified output format.
You MUST base your analysis ONLY on the information provided to you by the tools.
Do NOT use any external knowledge or make assumptions about EDI standards beyond what is explicitly written in the provided text.""",
            tools=[self.rag_tool],
            llm=self.llm,
            verbose=True
        )

    @agent
    def architect(self) -> Agent:
        return Agent(
            role='EDI Schema Design Architect',
            goal='Analyze a user request against a specific schema definition and generate a precise, structured JSON Patch object (RFC 6902) of proposed changes.',
            backstory="You are a meticulous architect who translates user requirements into detailed, machine-readable modification instructions. You must adhere to the specified JSON Patch output format.",
            tools=[],
            llm=self.llm,
            verbose=True
        )

    @task
    def planning_task(self) -> Task:
        return Task(
            description="""
                Use your tools to read and analyze the provided knowledge source document.
                Your mission is to identify EVERY single stated requirement for modifying the EDI schema.
                To do this, you will first use your tool with a broad query to gather all relevant sections of the document.
                You may need to use the tool multiple times if the first query does not provide all necessary details.
                
                Once you are certain you have gathered all available information from the document, you will synthesize it.
                For EACH requirement you have found, create a corresponding JSON object representing that single task.
                Finally, combine all of these individual task objects into a single JSON array to form your final answer.
            """,
            expected_output="""
                A final, complete JSON array of task objects.
                Each object must have three keys: 'task_type', 'task_description', and 'entity_id'.
                
                The 'entity_id' MUST be structured to provide context.
                - For element-level changes, use the format: 'LOOP_ID:SEGMENT_ID.ELEMENT_ID' (e.g., '2010AA:NM1.NM102').
                - For segment-level changes, use the format: 'LOOP_ID:SEGMENT_ID' (e.g., '2300:CLM').

                Example:
                [
                  {
                    "task_type": "update_segment_definition",
                    "entity_id": "2010AA:NM1.NM102",
                    "task_description": "Make NM102 (Entity Type Qualifier) in Billing Provider NM1 (Loop 2010AA) required."
                  }
                ]
                
                You MUST output your answer as a valid JSON array. Do not add any introductory text,
                conversation, or markdown formatting like ```json. The entire response must be
                the raw JSON array and nothing else.
            """,
            agent=self.planner()
        )
        
    @task
    def propose_patch_task(self) -> Task:
        return Task(
            description="""
                You will be given a specific task and the FULL current schema JSON.
                Your goal is to generate a JSON Patch (RFC 6902) that precisely describes the changes needed to accomplish the task.
                The JSON Patch 'path' MUST be an absolute path starting from the root of the document (e.g., '/segmentDefinitions/CLM/elements/1/usage').
                Do NOT use any tools. Analyze the provided schema and task description to determine the exact changes.

                Current Full Schema:
                {current_schema_json}

                Task to perform:
                {task}
            """,
            expected_output="""
                A final, complete JSON array formatted as a standard JSON Patch (RFC 6902).
                Example:
                [
                    { "op": "replace", "path": "/segmentDefinitions/CLM/elements/1/usage", "value": "R" }
                ]
            """,
            agent=self.architect(),
        )

    @crew
    def planning_crew(self) -> Crew:
        return Crew(
            agents=[self.planner()],
            tasks=[self.planning_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def worker_crew(self) -> Crew:
        return Crew(
            agents=[self.architect()],
            tasks=[self.propose_patch_task()],
            process=Process.sequential,
            verbose=True,
            manager_llm=self.llm
        )


# --- THIS IS THE NEW CREW FOR OUR ENRICHMENT WORKFLOW ---
from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field

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
            description="""
                You are an auditor comparing a JSON definition against a text document.
                The text document provided by the 'Documentation Query Tool' is your ONLY source of truth.
                Do NOT use any of your pre-existing knowledge about EDI standards.
                Your task is to identify discrepancies ONLY for the elements and properties explicitly mentioned in the retrieved text.

                1. You will be given a segment ID (e.g., 'CLM') and its current JSON definition.
                2. Use the 'Documentation Query Tool' ONE TIME with the given segment ID to retrieve its documentation.
                3. Perform a strict comparison between the retrieved text and the provided JSON.
                4. For each discrepancy, create a change object. A discrepancy ONLY exists if the text provides a value that is different from the JSON, or if the text describes an element that is completely missing from the JSON. The `change_type` for a modification MUST be 'MODIFY_ELEMENT' and for an addition MUST be 'ADD_ELEMENT'.
                5. If an element exists in the JSON but is NOT mentioned in the retrieved text, you MUST ignore it. DO NOT propose to remove it.
                6. YOUR FINAL ANSWER MUST BE A JSON OBJECT containing a list of these change objects. If no changes are needed, you MUST return an object with an empty list.

                **CRITICAL RULE**: Every change object you propose MUST include a "citation" field containing the exact quote from the documentation that justifies the change. If you cannot find a quote, you cannot propose the change.

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
            description="""
                You are a JSON Patch specialist. Your task is to convert a single, specific change request into a valid JSON Patch (RFC 6902) array.
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
