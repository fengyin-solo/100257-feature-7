"""继电器检修接口：台账维护、检修登记、排期与状态流转。

列表与明细共用 services.relay 中的结论推导，保证两处口径一致。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.relay import CONCLUSION_LABELS, RelayService

router = APIRouter(prefix="/api/relay", tags=["继电器检修"])

service = RelayService()

LIST_FIELDS = ["继电器编号", "继电器型号", "所属设备", "电气特性", "接点电阻",
               "检修周期", "检修日期", "下次检修日", "继电器状态"]
STATUSES = ["特性合格", "特性偏移", "接点氧化", "已报废"]
# 结论口径与 services.relay.CONCLUSION_LABELS 保持一致
CONCLUSIONS = list(CONCLUSION_LABELS)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按继电器编号检索"),
    status: str | None = Query(default=None, description="特性合格、特性偏移、接点氧化、已报废"),
    conclusion: str | None = Query(default=None, description="正常、即将到期、已到期、未排检修、待复检、已报废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按继电器编号、设备状态与检修结论过滤；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if conclusion and conclusion not in CONCLUSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"检修结论「{conclusion}」不支持，可选：{'、'.join(CONCLUSIONS)}",
        )
    items, total, summary = service.list_entries(
        keyword=keyword, status=status, conclusion=conclusion, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size, summary=summary)


@router.get("/export/all")
def export_entries() -> dict[str, Any]:
    """导出继电器检修清单：返回全量数据及其结论口径。"""
    items, total, summary = service.list_entries(page=1, size=10000)
    return {"module": "relay", "total": total, "summary": summary, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条继电器明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"继电器 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条继电器，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="继电器已登记，当前按未排检修处理", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """补录下次检修日等台账字段；日期对不上时拒绝保存并说明原因。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/maintenance", response_model=ActionResult)
def record_maintenance(entry_id: int, payload: EntryPayload) -> ActionResult:
    """登记一次实际检修：校验日期先后，追加检修历史并刷新下次检修日。"""
    entry, message = service.record_maintenance(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/schedule", response_model=ActionResult)
def schedule_maintenance(entry_id: int, payload: EntryPayload) -> ActionResult:
    """安排下次检修；同一台继电器重复安排时以最近一次为准。"""
    entry, message = service.schedule_maintenance(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条继电器执行记录偏移、申请报废；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
