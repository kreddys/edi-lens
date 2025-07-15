# FILE: backend/src/utils/telemetry.py

import json
from opentelemetry import trace
from crewai import Crew, Agent, Task
from wrapt import wrap_function_wrapper
from openlit.semcov import SemanticConvention
import functools

tracer = trace.get_tracer("edi_lens_crew_tracer")

def _parse_tools(tools):
    """Helper to serialize tool information for span attributes."""
    if not tools:
        return "[]"
    result = []
    for tool in tools:
        res = {}
        if hasattr(tool, "name") and tool.name is not None:
            res["name"] = tool.name
        if hasattr(tool, "description") and tool.description is not None:
            res["description"] = tool.description
        if res:
            result.append(res)
    return json.dumps(result)

def _tool_usage_wrapper(wrapped, instance, args, kwargs):
    """Manual wrapper for ToolsHandler._exec_tool to capture details."""
    tool = args[0]
    tool_name = getattr(tool, 'name', 'Unknown Tool')
    with tracer.start_as_current_span(f"Tool Usage: {tool_name}") as span:
        # The tool input can be in either args[1] or kwargs
        tool_input = args[1] if len(args) > 1 else kwargs
        span.set_attribute(SemanticConvention.GEN_AI_TOOL_NAME, tool_name)
        span.set_attribute(SemanticConvention.GEN_AI_TOOL_ARGS, str(tool_input))
        
        output = wrapped(*args, **kwargs)
        
        span.set_attribute("tool.output", str(output))
        return output

def _agent_execute_task_wrapper(wrapped, instance, args, kwargs):
    """
    This is our main instrumentation point. It wraps the agent's primary
    execution method. From here, we can dynamically patch the internal tool handler.
    """
    with tracer.start_as_current_span(f"Agent Execution: {instance.role}") as span:
        span.set_attribute(SemanticConvention.GEN_AI_SYSTEM, "crewai")
        span.set_attribute("crew.agent.id", str(instance.id))
        span.set_attribute("crew.agent.role", str(instance.role))
        span.set_attribute("crew.agent.goal", str(instance.goal))
        if hasattr(instance, 'llm') and hasattr(instance.llm, 'model'):
            span.set_attribute(SemanticConvention.GEN_AI_REQUEST_MODEL, instance.llm.model)

        # Dynamically patch the tool handler on the agent's instance right before execution
        handler = getattr(instance, 'tools_handler', None)
        original_exec_tool = None
        if handler and hasattr(handler, '_exec_tool'):
            original_exec_tool = handler._exec_tool
            # Create a new function that calls our wrapper, passing the original method
            # This avoids complex binding issues.
            def patched_exec_tool(*a, **k):
                return _tool_usage_wrapper(original_exec_tool, handler, a, k)
            handler._exec_tool = patched_exec_tool

        try:
            return wrapped(*args, **kwargs)
        finally:
            # IMPORTANT: Restore the original method to avoid side effects in other tests
            if handler and original_exec_tool:
                handler._exec_tool = original_exec_tool

def _task_execute_wrapper(wrapped, instance, args, kwargs):
    """Manual wrapper for Task's internal execution to create a detailed child span."""
    task_desc = instance.description
    task_name = task_desc.split(":", 1)[0] if ":" in task_desc else (task_desc[:50] + '...' if len(task_desc) > 50 else task_desc)
    span_name = f"Task: {task_name}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute(SemanticConvention.GEN_AI_SYSTEM, "crewai")
        span.set_attribute("crew.task.id", str(instance.id))
        span.set_attribute("crew.task.description", str(instance.description))
        span.set_attribute("crew.task.expected_output", str(instance.expected_output))
        span.set_attribute("crew.task.tools", _parse_tools(getattr(instance, 'tools', [])))
        if isinstance(instance.context, list):
            context_str = "\n---\n".join([f"Task: {t.description}\nOutput: {t.output.raw if t.output else 'N/A'}" for t in instance.context])
            span.set_attribute("crew.task.input_context", context_str)
        result = wrapped(*args, **kwargs)
        if result:
            span.set_attribute("crew.task.output", str(result))
        return result

def trace_crew(crew: Crew, crew_inputs: dict):
    """
    Creates a root span and applies manual instrumentation before running the crew.
    This ensures a complete, hierarchical trace of the entire crew execution.
    """
    agent_names = ", ".join([agent.role for agent in crew.agents])
    span_name = f"Crew Run: {agent_names or 'Unnamed Crew'}"

    # We only need to patch the top-level methods. The tool handler is patched dynamically inside the agent wrapper.
    wrap_function_wrapper('crewai.agent', 'Agent.execute_task', _agent_execute_task_wrapper)
    wrap_function_wrapper('crewai.task', 'Task._execute_core', _task_execute_wrapper)
    
    try:
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(SemanticConvention.GEN_AI_SYSTEM, "crewai")
            span.set_attribute(SemanticConvention.GEN_AI_OPERATION, "crew_kickoff")
            span.set_attribute("crew.process", str(crew.process))
            span.set_attribute("crew.agent_names", agent_names)
            span.set_attribute("crew.task_count", len(crew.tasks))
            span.set_attribute("crew.inputs", str(crew_inputs))
            
            result = crew.kickoff(inputs=crew_inputs)
            
            if hasattr(result, 'raw') and result.raw:
                span.set_attribute("crew.output", str(result.raw))
            else:
                span.set_attribute("crew.output", str(result))
            return result
    finally:
        # Revert the top-level patches after execution.
        if hasattr(Agent.execute_task, '__wrapped__'):
             Agent.execute_task = Agent.execute_task.__wrapped__
        if hasattr(Task._execute_core, '__wrapped__'):
             Task._execute_core = Task._execute_core.__wrapped__