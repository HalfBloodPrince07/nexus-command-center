from fastapi import APIRouter

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/status")
async def get_all_agent_status():
    return {
        "agents": [
            {"id": "supervisor", "name": "Nexus", "role": "Supervisor Agent", "tier": 1, "status": "active"},
            {"id": "knowledge_lead", "name": "Aria", "role": "Knowledge Domain Lead", "tier": 2, "status": "active"},
            {"id": "file_processor", "name": "Forge", "role": "File Processor", "tier": 3, "status": "idle"},
            {"id": "rag_retriever", "name": "Echo", "role": "RAG Retriever", "tier": 3, "status": "idle"},
            {"id": "vision", "name": "Iris", "role": "Vision Specialist", "tier": 3, "status": "idle"},
        ]
    }


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str):
    return {"lm_studio_connected": True, "agent": agent_id}

