import os
import sys
import json
import asyncio
from pathlib import Path

# Fix Windows console encoding for Unicode/emoji support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

# Import the LangGraph application
from src.graph import app as graph_app

app = FastAPI(title="IaC Orchestrator API")

@app.get("/")
def get_index():
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        return HTMLResponse("index.html not found", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

async def pipeline_event_generator(user_prompt: str):
    initial_state = {
        "user_prompt": user_prompt,
        "rag_context": "",
        "current_code": "",
        "architect_reflection": "",
        "security_critique": "",
        "finops_critique": "",
        "linter_logs": "",
        "security_score": 0.0,
        "monthly_cost": 0.0,
        "iteration_count": 0,
        "terraform_valid": False,
    }

    try:
        # We use astream to support async iteration
        async for event in graph_app.astream(initial_state, stream_mode="updates"):
            for node_name, state_update in event.items():
                payload = {
                    "node": node_name,
                    "update": state_update
                }
                yield {"data": json.dumps(payload)}
                # Yield control to the event loop
                await asyncio.sleep(0.01)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        yield {"data": json.dumps({"error": str(e)})}
        
    yield {"data": json.dumps({"node": "complete"})}

@app.get("/api/stream")
async def stream_pipeline(prompt: str = Query(..., description="User infrastructure prompt")):
    return EventSourceResponse(pipeline_event_generator(prompt))

if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:8000 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
