from __future__ import annotations

import re
import uuid
from typing import AsyncGenerator

from backend.app.agents.rag_retriever import rag_retriever
from backend.app.agents.vision_agent import vision_agent
from backend.core.event_bus import event_bus


class KnowledgeLead:
    SEARCH_PATTERNS = [
        r"\b(search|find|look for|retrieve|what does|according to|based on|from my files?)\b",
        r"\b(documents?|files?|uploaded)\b.*\b(say|mention|contain|about)\b",
    ]
    IMAGE_PATTERNS = [
        r"\b(image|picture|photo|screenshot|diagram|chart|figure)\b",
        r"\b(describe|analyze|read|transcribe|ocr)\b.*\b(image|photo|picture)\b",
    ]
    RESEARCH_PATTERNS = [
        r"\b(research|investigate|deep.dive.into|look.into|study|analyze)\b",
        r"\bresearch\s+(topic|question|query|about)\b",
        r"\bfind out (everything|all|more) about\b",
        r"\bdo an? research on\b",
    ]

    def classify_intent(self, message: str, has_image: bool = False) -> str:
        if has_image:
            return "image"

        lowered = message.lower()
        if any(re.search(pattern, lowered) for pattern in self.IMAGE_PATTERNS):
            return "image"
        if any(re.search(pattern, lowered) for pattern in self.RESEARCH_PATTERNS):
            return "research"
        if any(re.search(pattern, lowered) for pattern in self.SEARCH_PATTERNS):
            return "search"
        return "general"

    async def route(
        self,
        session_id: str,
        user_message: str,
        model: str | None = None,
        image_path: str | None = None,
        image_b64: str | None = None,
        collection: str = "files",
    ) -> AsyncGenerator[dict, None]:
        from backend.app.agents.research_lead import research_lead

        has_image = image_path is not None or image_b64 is not None
        yield {"type": "thinking", "agent": "Aria", "content": ""}
        intent = self.classify_intent(user_message, has_image=has_image)

        if intent == "general":
            return

        if intent == "research":
            yield {"type": "agent_switch", "from": "Aria", "to": "Atlas", "content": ""}
            job_id = str(uuid.uuid4())
            async for event in research_lead.run_research(
                user_message, job_id, session_id
            ):
                yield event
            return

        target_name = "Echo" if intent == "search" else "Iris"
        await event_bus.publish_agent_message(
            from_agent="Aria",
            to_agent=target_name,
            message_type="task_assignment",
            payload={"session_id": session_id, "intent": intent},
        )
        yield {"type": "agent_switch", "from": "Aria", "to": target_name, "content": ""}

        if intent == "search":
            async for item in rag_retriever.search(
                query=user_message,
                collection=collection,
                n_results=5,
                session_id=session_id,
            ):
                if isinstance(item, dict):
                    yield item
                else:
                    yield {"type": "token", "agent": "Echo", "content": item}
        elif intent == "image":
            async for token in vision_agent.analyze_image(
                image_path=image_path,
                image_b64=image_b64,
                question=user_message or "Describe this image in detail.",
                session_id=session_id,
                model=model,
            ):
                yield {"type": "token", "agent": "Iris", "content": token}

        yield {"type": "done", "agent": "Aria", "content": ""}


knowledge_lead = KnowledgeLead()
