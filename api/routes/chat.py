"""Chat endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.state import app_state
from providers.base import Message

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "auto"
    max_tokens: Optional[int] = 4096
    temperature: float = 1.0
    stream: bool = False


class ChatResponse(BaseModel):
    role: str
    content: str
    model: str
    usage: dict
    cost: float


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send chat message and get response."""
    try:
        chat_router = app_state.get("chat_router")
        if not chat_router:
            raise HTTPException(status_code=500, detail="Chat router not initialized")

        # Convert to Message objects
        messages = [
            Message(role=msg.role, content=msg.content)
            for msg in request.messages
        ]

        # Get response
        response = await chat_router.chat(
            messages=messages,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        return ChatResponse(
            role="assistant",
            content=response.content,
            model=response.model,
            usage=response.usage,
            cost=response.cost
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response."""
    try:
        chat_router = app_state.get("chat_router")
        if not chat_router:
            raise HTTPException(status_code=500, detail="Chat router not initialized")

        # Convert to Message objects
        messages = [
            Message(role=msg.role, content=msg.content)
            for msg in request.messages
        ]

        async def generate():
            """Generate streaming response."""
            # Use primary provider's streaming if available
            provider = chat_router.primary

            # For now, non-streaming fallback
            response = await chat_router.chat(
                messages=messages,
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )

            # Simulate streaming by chunking
            chunk_size = 50
            for i in range(0, len(response.content), chunk_size):
                chunk = response.content[i:i + chunk_size]
                yield f"data: {chunk}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
