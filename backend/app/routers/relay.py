"""继电器检修接口。

列表、明细、导出都经 RelayService 的统一结论口径渲染，页面在哪里看结论都一致。
写入类接口在日期倒挂等边界情况下返回 ok=False 并说明对不上的字段，不抛 500。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.relay import (
    CONCLUSION_LABELS,
    MODULE,
    TECH_STATUSES,
    RelayService,
)

router = APIRouter(prefix="/api/relay", tags=["继电器检修"])

service = RelayService()

LIST_FIELDS = [
    "继电器编号", "继电器型号", "所属设备", "电气特性", "接点电阻",
    "检修周期", "上次检修日", "下次检修日", "继电器状态",
]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按继电器编号检索"),
    status: str | None = Query(default=None, description="继电器状态：特性合格/特性偏移/接点氧化/已报废"),
    conclusion: str | None = Query(default=None, description="检修结论：unscheduled/reinspect/overdue/upcoming/scrapped"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按编号、继电器状态、检修结论过滤；没有数据返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status and status not in TECH_STATUSES:
        raise HTTPException(status_code=400, detail=f"继电器状态「{status}」不在允许范围内")
    if conclusion and conclusion not in CONCLUSION_LABELS:
        raise HTTPException(status_code=400, detail=f"检修结论「{conclusion}」不在允许范围内")
    items, total = service.list_entries(
        keyword=keyword, tech_status=status, conclusion=conclusion, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def summary() -> dict[str, Any]:
    """结论统计卡片：数量口径与列表结论完全一致。"""
    return {"labels": CONCLUSION_LABELS, "counts": service.summary()}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出继电器检修清单：全量数据并带统一结论。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": MODULE, "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条继电器明细（含结论与检修历史）；不存在时给出可读说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"继电器 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记继电器台账，缺必填字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="继电器已登记", entry=entry)


@router.post("/{entry_id}/schedule", response_model=ActionResult)
def schedule_inspection(entry_id: int, payload: EntryPayload) -> ActionResult:
    """安排/补录下次检修日；早于上次检修日或日期格式不对一律不保存并说明。"""
    entry, message = service.schedule_inspection(entry_id, payload.values)
    return ActionResult(ok=entry is not None, message=message, entry=entry)


@router.post("/{entry_id}/inspections", response_model=ActionResult)
def save_inspection(entry_id: int, payload: EntryPayload) -> ActionResult:
    """登记一次检修完成记录；日期倒挂不保存，电阻异常按待复检处理但不拦截。"""
    entry, message = service.save_inspection(entry_id, payload.values)
    return ActionResult(ok=entry is not None, message=message, entry=entry)
