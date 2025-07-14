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
            role='EDI Requirement Analyst',
            goal='Analyze EDI implementation guide documentation to extract all specified schema modification requirements and formulate them into a structured JSON list of tasks.',
            # --- THIS IS THE FIX ---
            # Added a very strong negative constraint to prevent hallucination.
            backstory="""You are an expert EDI analyst. Your sole focus is to read technical documentation and accurately translate every stated requirement into a machine-readable task format.
You never miss a requirement and always follow the specified output format.
You MUST base your analysis ONLY on the information provided to you by the tools.
Do NOT use any external knowledge or make assumptions about EDI standards beyond what is explicitly written in the provided text.""",
            # --- END OF FIX ---
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

    # --- TASK DEFINITIONS ---

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
        return Crew(
            agents=[self.architect()],
            tasks=[self.propose_patch_task()],
            process=Process.sequential,
            verbose=True,
            manager_llm=self.llm
        )