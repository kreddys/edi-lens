from crewai import Task, Agent  # Correctly import Agent here
from .agents import SchemaAgents

class SchemaTasks:
    def __init__(self):
        pass

    def triage_task(self, agent: Agent, user_input: str) -> Task:
        return Task(
            description=f"""
                Analyze the following user input and classify its type (e.g., 'documentation', 'edi_sample', 'natural_language_request').
                Summarize the user's core intent and extract all relevant EDI entities mentioned (e.g., segment names like 'NM1', loop IDs like '2300', qualifiers like 'F8').

                USER INPUT:
                ---
                {user_input}
                ---
            """,
            expected_output="A concise JSON object with three keys: 'inputType' (string), 'intent' (string), and 'entities' (list of strings).",
            agent=agent,
        )

    def locate_task(self, agent: Agent, context_task: Task) -> Task:
        return Task(
            description="""
                Based on the analysis from the triage task, use the Schema Structure Reader tool to find the unique key for every schema node relevant to the user's request.
                You must identify all nodes that need to be examined to fulfill the user's intent.
            """,
            expected_output="A JSON list of unique schema node keys. For example: ['loop:2000A.loop:2010AA', 'loop:2000B.loop:2010BA']",
            agent=agent,
            context=[context_task],
        )

    def propose_task(self, agent: Agent, context_tasks: list) -> Task:
        return Task(
            description="""
                For each node key identified by the locator agent, use the Node Definition Reader tool to get its full definition.
                Then, carefully compare the definition against the original user request (provided in the context) to generate a detailed, structured 'Change Plan'.

                The final output MUST be a single JSON object with two keys:
                1. 'summary': A human-readable string summarizing the proposed changes.
                2. 'suggested_changes': A list of change objects.

                Each change object in the list must have the following keys:
                - 'change_id': A unique identifier for the change (e.g., 'change-001').
                - 'type': The type of change, e.g., 'SPECIALIZE_SEGMENT', 'MODIFY_NODE'.
                - 'scope_key': The unique key of the node being changed.
                - 'description': A human-readable description of this specific change.
                - 'actions': A list of specific, machine-readable action objects to be performed.
            """,
            expected_output="A final, complete JSON object formatted as a 'Change Plan'.",
            agent=agent,
            context=context_tasks,
        )