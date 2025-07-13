from crewai import Task, Agent

class SchemaTasks:
    def __init__(self):
        pass

    def triage_task(self, agent: Agent, user_input: str, schema_name: str) -> Task:
        return Task(
            description=f"""
                Analyze the following user input regarding the '{schema_name}' EDI schema.
                Classify the input type (e.g., 'documentation', 'edi_sample', 'natural_language_request').
                Summarize the user's core intent and extract all relevant EDI entities mentioned.

                USER INPUT:
                ---
                {user_input}
                ---
            """,
            expected_output="A concise JSON object with three keys: 'inputType' (string), 'intent' (string), and 'entities' (list of strings). Also include the original 'schema_name' in the output.",
            agent=agent,
        )

    def locate_task(self, agent: Agent, schema_name: str) -> Task:
        return Task(
            description=f"""
                Based on the analysis from the previous task, use the Schema Structure Reader tool to find the unique key for every schema node relevant to the user's request.
                You MUST call the tool with the schema_name: '{schema_name}'.
            """,
            expected_output="A JSON list of unique schema node keys.",
            agent=agent,
        )

    def propose_task(self, agent: Agent, schema_name: str) -> Task:
        return Task(
            description=f"""
                For each node key identified by the locator agent, use the Node Definition Reader tool to get its full JSON definition.
                The tool must be called with the schema_name: '{schema_name}' and the specific node_key.
                Then, compare the definition against the original user request to generate a detailed, structured 'Change Plan'.

                The final output MUST be a single JSON object with a 'summary' and a list of 'suggested_changes'.
            """,
            expected_output="A final, complete JSON object formatted as a 'Change Plan'.",
            agent=agent,
        )