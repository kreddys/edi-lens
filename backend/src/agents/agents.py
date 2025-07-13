import logging
from crewai import Agent
from .tools import SchemaStructureTool, NodeDefinitionTool

# Get a logger for this module
logger = logging.getLogger(__name__)

class SchemaAgents:
    def __init__(self, schema_name: str):
        logger.debug(f"Initializing SchemaAgents for schema: '{schema_name}'")
        self.structure_tool = SchemaStructureTool(schema_name=schema_name)
        self.node_tool = NodeDefinitionTool(schema_name=schema_name)

    def input_triage_agent(self) -> Agent:
        logger.debug("Creating InputTriageAgent")
        return Agent(
            role='Input Triage Analyst',
            goal='Analyze and classify user input regarding EDI schema changes. Extract the core user intent and any specific entities mentioned (like segment or loop IDs).',
            backstory="You are an expert at reading and understanding technical requests. Your job is to pre-process user queries, making them clear and actionable for a team of specialists.",
            verbose=True,
            allow_delegation=False,
        )

    def schema_locator_agent(self) -> Agent:
        logger.debug("Creating SchemaLocatorAgent")
        return Agent(
            role='Schema Navigation Specialist',
            goal='Take a user request analysis and find the exact corresponding node key(s) within the EDI schema structure using the provided tools.',
            backstory="You have a perfect memory of the entire EDI schema structure. Your mission is to pinpoint the exact locations for modifications.",
            tools=[self.structure_tool],
            verbose=True,
            allow_delegation=False,
        )

    def change_proposal_agent(self) -> Agent:
        logger.debug("Creating ChangeProposalAgent")
        return Agent(
            role='EDI Schema Design Architect',
            goal='Analyze a user request against specific schema node definitions and generate a precise, structured JSON object of proposed changes.',
            backstory="You are a meticulous architect who translates user requirements into detailed, machine-readable instructions. You must adhere to the specified JSON output format for the 'Change Plan'.",
            tools=[self.node_tool],
            verbose=True,
            allow_delegation=True, # Can delegate back to locator if context is missing
        )