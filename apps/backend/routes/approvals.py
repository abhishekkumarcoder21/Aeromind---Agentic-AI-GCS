"""Approval API routes — human-in-the-loop approval workflow."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    """Request body for approval/rejection."""

    decision: str  # "APPROVED" or "REJECTED"
    reason: str = ""


@router.get("")
async def list_pending_approvals(request: Request):
    """List all pending approval requests."""
    execution_engine = request.app.state.execution_engine
    pending = execution_engine.get_pending_approvals()
    return {"approvals": [a.model_dump(mode="json") for a in pending]}


@router.post("/{action_id}")
async def decide_approval(request: Request, action_id: str, body: ApprovalDecisionRequest):
    """Approve or reject a pending action."""
    execution_engine = request.app.state.execution_engine

    if body.decision.upper() == "APPROVED":
        result = await execution_engine.approve_action(action_id)
    elif body.decision.upper() == "REJECTED":
        result = await execution_engine.reject_action(action_id, body.reason)
    else:
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED")

    if not result:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found in pending approvals")

    return {"action": result.model_dump(mode="json")}
