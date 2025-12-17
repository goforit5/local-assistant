"""Reasoning service endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import app_state
from providers.base import Message

router = APIRouter()


class ReasoningRequest(BaseModel):
    problem: str
    max_steps: int = 10
    detail: str = "medium"


class ReasoningResponse(BaseModel):
    solution: str
    steps: int
    cost: float
    model: str


@router.post("/solve", response_model=ReasoningResponse)
async def solve_problem(request: ReasoningRequest):
    """Solve complex problem using o1-mini reasoning."""
    try:
        openai_provider = app_state.get("openai")
        if not openai_provider:
            raise HTTPException(status_code=500, detail="OpenAI provider not initialized")

        # Build reasoning prompt
        prompt = f"""Think through this problem step by step and provide a detailed solution:

{request.problem}

Detail level: {request.detail}
Max reasoning steps: {request.max_steps}

Provide your reasoning and final solution."""

        messages = [Message(role="user", content=prompt)]

        # Use o1-mini for reasoning
        response = await openai_provider.chat(
            messages=messages,
            model="o1-mini",
            max_tokens=4096
        )

        return ReasoningResponse(
            solution=response.content,
            steps=request.max_steps,
            cost=response.cost,
            model=response.model
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
async def verify_solution(code: str, spec: str):
    """Verify code against specification."""
    try:
        openai_provider = app_state.get("openai")
        if not openai_provider:
            raise HTTPException(status_code=500, detail="OpenAI provider not initialized")

        prompt = f"""Verify this code meets the specification:

SPECIFICATION:
{spec}

CODE:
{code}

Provide detailed verification results."""

        messages = [Message(role="user", content=prompt)]

        response = await openai_provider.chat(
            messages=messages,
            model="o1-mini",
            max_tokens=4096
        )

        return {
            "verification": response.content,
            "cost": response.cost,
            "model": response.model
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
