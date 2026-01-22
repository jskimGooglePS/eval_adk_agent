import asyncio
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from planner_agent.agent import root_agent

session_service = InMemorySessionService()

# Define constants for identifying the interaction context
APP_NAME = "planner_test_app"
USER_ID = "user_1"
SESSION_ID = "session_000" # Using a fixed ID for simplicity

async def init_session(session_service:InMemorySessionService,app_name:str,user_id:str,session_id:str) -> InMemorySessionService:
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )
    print(f"Session created: App='{app_name}', User='{user_id}', Session='{session_id}'")
    return session

session = asyncio.run(init_session(session_service, APP_NAME,USER_ID,SESSION_ID))

runner = Runner(
    agent=root_agent, # The agent we want to run
    app_name=APP_NAME,   # Associates runs with our app
    session_service=session_service # Uses our session manager
)
print(f"Runner created for agent '{runner.agent.name}'.")