from pydantic import BaseModel
from agents import function_tool, Agent, Runner, trace
import asyncio
import os
from dotenv import load_dotenv

# Load the .env file at startup
load_dotenv()

# ---------- OUTPUT MODEL ----------

class ToolOutputExample(BaseModel):
    """
    Output model for the example tool.
    Attributes:
        description (str): A description of the output.
        success (bool): Indicates whether the operation was successful.

        This pydantic model will be used to validate the output of the example tool.
    """
    description: str
    success: bool

class AgentOutputExample(BaseModel):
    """
    Output model for the agent.
    Attributes:
        output (ToolOutputExample): The output from the tool.
        
        This pydantic model will cause the agent to return output in this format rather than the raw output of the tool.
        It is useful for ensuring that the output is structured and validated.
    """
    input: str
    output: ToolOutputExample
    comment: str = "This is an example agent output."

# ---------- TOOLS  ----------
@function_tool
def example_tool(input: str) -> ToolOutputExample:
    """
    An example tool that takes a string input and returns a description and success status.
    
    Args:
        input (str): Input string for the tool.
    
    Returns:
        ToolOutputExample: An instance of ToolOutputExample containing a description and success status.
    """
    # Process the input and create an output example
    if not input:
        return ToolOutputExample(description="No input provided", success=False)
    
    # Here you can add any processing logic you need
    # Check if input contains Flash return Thunder and True
    if "Flash" in input:
        return ToolOutputExample(description="Thunder", success=True)

    return ToolOutputExample(description=f"Processed input: {input}", success=True)

# ---------- AGENTS ----------

example_tool_agent = Agent(
    name="example_tool_agent",
    instructions="Process input using the example tool.  Include a fun comment in the output as an example.",
    tools=[example_tool],
    model="gpt-4.1-mini",
    output_type=AgentOutputExample,
)

# ---------- RUNNER ----------
async def run_example_tool_agent(input: str):
    """
    Run the example tool agent with the provided input.
    
    Args:
        input (str): Input string for the agent.
    
    Returns:
        AgentOutputExample: The output from the agent.
    """
    with trace("Running example_tool_agent"):
        # Run the agent with the provided input
        # The runner will handle the execution and return the output in the specified format
        result = await Runner.run(example_tool_agent, input)
        print(f"Agent output: {result}")
        return result
    
if __name__ == "__main__":
    # Example usage
    input_data = "Flash is a superhero."
    asyncio.run(run_example_tool_agent(input_data))