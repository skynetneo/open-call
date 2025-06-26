"""LangGraph based agents for call handling."""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langmem import create_memory_manager

# Simple memory manager using langmem for persistence
memory_manager = create_memory_manager(model="gpt-3.5-turbo")

# React agent that will call tools in a loop. We keep it simple here
react_agent = create_react_agent(ChatOpenAI(model="gpt-3.5-turbo"), tools=[])

__all__ = ["memory_manager", "react_agent"]
