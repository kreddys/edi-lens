import os
import logging
from crewai import Crew, Process, Agent
from .agents import SchemaAgents
from .tasks import SchemaTasks

# Get a logger for this module
logger = logging.getLogger(__name__)

def create_schema_refinement_crew(schema_name: str, user_input: str) -> Crew:
    """Creates and configures the schema refinement crew."""
    
    # 1. Get the model name from the environment. Default to a known good model.
    llm_model_name = os.getenv("LLM_MODEL", "openrouter/deepseek/deepseek-chat")
    logger.info(f"Using LLM model for all agents: '{llm_model_name}'")

    # 2. Initialize agents and tasks
    agents_factory = SchemaAgents(schema_name=schema_name)
    tasks_factory = SchemaTasks()

    # 3. Define agent instances, passing the model name directly to them.
    #    CrewAI will handle the instantiation of the correct LLM backend via LiteLLM.
    triage_agent = agents_factory.input_triage_agent()
    triage_agent.llm_model = llm_model_name

    locator_agent = agents_factory.schema_locator_agent()
    locator_agent.llm_model = llm_model_name
    
    proposal_agent = agents_factory.change_proposal_agent()
    proposal_agent.llm_model = llm_model_name

    # 4. Define task instances
    triage = tasks_factory.triage_task(triage_agent, user_input)
    locate = tasks_factory.locate_task(locator_agent, triage)
    propose = tasks_factory.propose_task(proposal_agent, [triage, locate])

    # 5. Instantiate the crew with the model assigned to the manager as well.
    return Crew(
        agents=[triage_agent, locator_agent, proposal_agent],
        tasks=[triage, locate, propose],
        process=Process.sequential,
        verbose=2,
        manager_llm={"model_name": llm_model_name}
    )