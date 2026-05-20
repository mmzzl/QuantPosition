from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from pydantic import BaseModel
from app.core.auth import AuthenticatedUser, get_current_user
from services.rule_service import RuleService

router = APIRouter(prefix="/rules", tags=["交易规则"])


class RuleCreate(BaseModel):
    name: str
    type: str  # buy / sell / risk
    priority: int = 3
    weight: float = 0.0
    condition: str = ""
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str = None
    type: str = None
    priority: int = None
    weight: float = None
    condition: str = None
    enabled: bool = None


class BatchDelete(BaseModel):
    rule_ids: List[int]


@router.get("")
async def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    return RuleService.list_rules(page, page_size)


@router.post("")
async def create_rule(
    data: RuleCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    return RuleService.create_rule(data.model_dump())


@router.get("/{rule_id}")
async def get_rule(
    rule_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    r = RuleService.get_rule(rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="规则不存在")
    return r


@router.put("/{rule_id}")
async def update_rule(
    rule_id: int,
    data: RuleUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    ok = RuleService.update_rule(rule_id, data.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在或无变化")
    return {"message": "更新成功"}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    ok = RuleService.delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"message": "删除成功"}


@router.post("/batch-delete")
async def batch_delete(
    data: BatchDelete,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    count = RuleService.batch_delete(data.rule_ids)
    return {"message": f"已删除 {count} 条规则"}
