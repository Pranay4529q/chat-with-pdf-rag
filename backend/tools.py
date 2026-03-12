from langchain.agents import Tool
from langchain_community.utilities import GoogleSerperAPIWrapper

def calc(expression:str)->str:
    try:
        result=eval(expression)
        return str(result)
    except Exception as e:
        return f"Error evaluating the given expression: {str(e)}"
    
def get_tools():
    tools=[
        Tool(
            name="Calculator",
            func=calc,
            description="Useful for mathematic calculations. Input should be a math expression like '2 + 2' or '10 * 5'"
        )
    ]
    return tools
