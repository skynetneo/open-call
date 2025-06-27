from langchain.chat_models import init_chat_model
from langgraph.func import entrypoint
from langgraph.store.memory import InMemoryStore
from langmem import create_memory_store_manager

# 1. In-memory vector store, using Gemini embedding model
store = InMemoryStore(
    index={
        "dims": 1536,
        "embedding_model": "gemini-embedding-exp-03-07",
    }
)

# 2. Use Gemini 2.5 Pro as your chat model
llm = init_chat_model("google:gemini-2.5-pro")

# 3. Memory manager: extracts/stores memories from every incoming message
memory_manager = create_memory_store_manager(
    "google:gemini-2.5-pro",
    namespace=("memories",),
)

@entrypoint(store=store)
async def chat(message: str):
    # save the user’s message
    await memory_manager.invoke(message)
    # get a response from Gemini
    result = await llm.ainvoke(message)
    return result.content

__all__ = ["memory_manager", "chat"]
