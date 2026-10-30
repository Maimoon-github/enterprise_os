from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer_instance: AsyncPostgresSaver | None = None

async def init_checkpointer():
    global checkpointer_instance
    # Initialized on FastAPI startup lifecycle
    return None

def get_checkpointer() -> AsyncPostgresSaver | None:
    return checkpointer_instance
