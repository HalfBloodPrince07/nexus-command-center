from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import AsyncGenerator

from backend.app.agents._lm_studio import stream_chat_completion
from backend.config import settings


class VisionAgent:
    async def analyze_image(
        self,
        image_path: str | None = None,
        image_b64: str | None = None,
        image_mime: str = "image/jpeg",
        question: str = "Describe this image in detail.",
        session_id: str = "",
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        if image_b64 is None:
            if image_path is None:
                yield "No image provided."
                return
            image_b64, image_mime = self._encode_image(image_path)

        vision_model = model or settings.lm_studio_vision_model or settings.lm_studio_model
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
                    {"type": "text", "text": question},
                ],
            }
        ]

        try:
            async for token in stream_chat_completion(
                messages=messages,
                model=vision_model,
                temperature=0.2,
                max_tokens=2048,
            ):
                yield token
        except Exception as exc:
            yield f"Error: Could not analyze image. {exc}"

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        mime_type, _ = mimetypes.guess_type(image_path)
        resolved_mime = mime_type or "image/jpeg"
        data = Path(image_path).read_bytes()
        return base64.b64encode(data).decode("utf-8"), resolved_mime

    async def ocr_document(self, image_path: str, session_id: str = "") -> AsyncGenerator[str, None]:
        async for token in self.analyze_image(
            image_path=image_path,
            question="Extract all text from this image. Output only the text, no commentary.",
            session_id=session_id,
        ):
            yield token


vision_agent = VisionAgent()
