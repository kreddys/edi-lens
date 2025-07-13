import logging
from crewai import Crew, Process, Agent, Task
from .agents import SchemaAgents
from .tasks import SchemaTasks
from .llm import get_llm

logger = logging.getLogger(__name__)

def create_schema_refinement_crew(schema_name: str, user_input: str) -> Crew:
    """Creates and configures the schema refinement crew."""
    
    # Get the single, configured LLM instance from our factory.
    llm = get_llm()

    # Initialize agent and task factories
    agents_factory = SchemaAgents()
    tasks_factory = SchemaTasks()

    # Define agent instances
    triage_agent = agents_factory.input_triage_agent()
    locator_agent = agents_factory.schema_locator_agent()
    proposal_agent = agents_factory.change_proposal_agent()

    # Assign the LLM object to each agent
    triage_agent.llm = llm
    locator_agent.llm = llm
    proposal_agent.llm = llm

    # 1. Define the first task. It has no dependencies.
    triage_task = tasks_factory.triage_task(
        agent=triage_agent, 
        user_input=user_input, 
        schema_name=schema_name
    )

    # 2. Define the second task, telling it that it depends on the output of the first task.
    locate_task = tasks_factory.locate_task(
        agent=locator_agent, 
        schema_name=schema_name
    )
    # Set the context directly on the Task object
    locate_task.context = [triage_task]

    # 3. Define the final task, telling it that it depends on the first two tasks.
    propose_task = tasks_factory.propose_task(
        agent=proposal_agent, 
        schema_name=schema_name
    )
    # Set the context directly on the Task object
    propose_task.context = [triage_task, locate_task]

    # Instantiate the crew with the list of tasks.
    # The sequential process will respect the `context` defined on each task.
    return Crew(
        agents=[triage_agent, locator_agent, proposal_agent],
        tasks=[triage_task, locate_task, propose_task],
        process=Process.sequential,
        # --- THIS IS THE FIX ---
        # Changed verbose from integer `2` to boolean `True`.
        verbose=True,
        manager_llm=llm,
    )