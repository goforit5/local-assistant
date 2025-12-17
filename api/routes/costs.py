"""Cost tracking endpoints."""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# from observability.costs import CostTracker, CostEntry

router = APIRouter()


class CostSummary(BaseModel):
    total_cost: float
    requests: int
    avg_cost: float
    breakdown: dict


class ServiceCost(BaseModel):
    service: str
    requests: int
    cost: float
    model: str


@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    period: str = Query("today", enum=["today", "week", "month", "all"])
):
    """Get cost summary for specified period."""
    try:
        # In production, query from database
        # For now, return mock data that matches UI
        mock_data = {
            "today": {
                "total_cost": 4.67,
                "requests": 190,
                "avg_cost": 0.025,
                "breakdown": {
                    "chat": 2.34,
                    "vision": 1.89,
                    "reasoning": 0.54,
                    "computer_use": 0.23
                }
            },
            "week": {
                "total_cost": 23.14,
                "requests": 834,
                "avg_cost": 0.028,
                "breakdown": {
                    "chat": 12.50,
                    "vision": 7.20,
                    "reasoning": 2.44,
                    "computer_use": 1.00
                }
            }
        }

        data = mock_data.get(period, mock_data["today"])

        return CostSummary(
            total_cost=data["total_cost"],
            requests=data["requests"],
            avg_cost=data["avg_cost"],
            breakdown=data["breakdown"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/breakdown", response_model=List[ServiceCost])
async def get_cost_breakdown():
    """Get detailed cost breakdown by service."""
    try:
        # Mock data matching UI
        breakdown = [
            ServiceCost(service="Chat", requests=127, cost=2.34, model="Claude Sonnet 4.5"),
            ServiceCost(service="Vision", requests=43, cost=1.89, model="GPT-4o"),
            ServiceCost(service="Reasoning", requests=8, cost=0.54, model="o1-mini"),
            ServiceCost(service="Computer Use", requests=12, cost=0.23, model="GPT-4o"),
        ]

        return breakdown

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits")
async def get_cost_limits():
    """Get configured cost limits."""
    return {
        "per_request": {"warn": 0.50, "max": 1.00},
        "per_hour": {"warn": 5.00, "max": 10.00},
        "per_day": {"warn": 20.00, "max": 50.00}
    }


@router.post("/limits")
async def set_cost_limits(
    per_request: Optional[float] = None,
    per_hour: Optional[float] = None,
    per_day: Optional[float] = None
):
    """Update cost limits."""
    limits = {}
    if per_request:
        limits["per_request"] = per_request
    if per_hour:
        limits["per_hour"] = per_hour
    if per_day:
        limits["per_day"] = per_day

    return {"success": True, "limits": limits}


@router.get("/alerts")
async def get_cost_alerts():
    """Get active cost alerts."""
    return {
        "active_alerts": [],
        "warnings": []
    }
