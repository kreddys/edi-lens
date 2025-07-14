# FILE: backend/src/agents/crews.py
import logging
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from .llm import get_llm
from .refinement_engine.rag_tool import RAGTool
from .tools import schema_structure_tool, node_definition_tool

logger = logging.getLogger(__name__)

@CrewBase
class SchemaRefinementCrews:
    """A class to define all crews related to schema refinement."""
    
    def __init__(self, rag_tool: RAGTool):
        self.rag_tool = rag_tool
        self.llm = get_llm()

    # --- AGENT DEFINITIONS ---
    
    @agent
    def planner(self) -> Agent:
        return Agent(
            role='EDI Documentation Analysis and Planning Agent',
            goal='Analyze a large EDI implementation guide and create a structured, machine-readable plan of all required schema changes.',
            backstory="You are a meticulous technical writer and project manager. You read complex specifications and break them down into granular, actionable tasks for a team of developers. Your plans are flawless and comprehensive.",
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
            # This agent no longer needs tools, as the full context is provided.
            tools=[],
            llm=self.llm,
            verbose=True
        )

    # --- TASK DEFINITIONS ---

    @task
    def planning_task(self) -> Task:
        return Task(
            description="""
                Read the provided knowledge source document using your tools.
                Your goal is to create a comprehensive, step-by-step plan for refining an EDI schema.
                Break down the required changes into a list of specific, actionable tasks.
                For each task, identify the type of change (e.g., 'update_segment_definition'),
                the specific entity to be changed (e.g., 'CLM' segment), and a clear description.
            """,
            expected_output="""
                A final, complete JSON array of task objects.
                Each object must have three keys: 'task_type', 'task_description', and 'entity_id'.
                Example:
                [
                  { "task_type": "update_segment_definition", "entity_id": "CLM", "task_description": "Make CLM02 required." }
                ]
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

    # --- CREW DEFINITIONS ---
    
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
        # The worker crew is now simpler, with only one agent and one task.
        return Crew(
            agents=[self.architect()],
            tasks=[self.propose_patch_task()],
            process=Process.sequential,
            verbose=True,
            manager_llm=self.llm
        )