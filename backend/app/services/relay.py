"""继电器检修业务规则：到期判定、边界校验与结论推导都收在这里。

同一份 ``derive_conclusion`` 同时供列表与明细使用，保证两处口径完全一致。
"""
from __future__ import annotations

import re
import calendar
from datetime import date
from typing import Any

from app.store import store

MODULE = "relay"
REQUIRED_FIELDS = ["继电器编号", "继电器型号", "所属设备"]
EDITABLE_FIELDS = REQUIRED_FIELDS + ["电气特性", "接点电阻", "检修周期"]
STATUS_ORDER = ["特性合格", "特性偏移", "接点氧化", "已报废"]
ACTION_RULES = {"记录偏移": "特性偏移", "申请报废": "已报废"}

# 接点电阻允许范围（Ω）：空值与越界都按待复检处理，负值/非数值同理
RESISTANCE_MIN = 0.0
RESISTANCE_MAX = 0.1
# 距到期日不足该天数时提示即将到期
DUE_SOON_DAYS = 7
# 结论标签
LBL_NORMAL = "正常"
LBL_DUE_SOON = "即将到期"
LBL_OVERDUE = "已到期"
LBL_UNSCHEDULED = "未排检修"
LBL_RECHECK = "待复检"
LBL_SCRAPPED = "已报废"
CONCLUSION_LABELS = [
    LBL_NORMAL,
    LBL_DUE_SOON,
    LBL_OVERDUE,
    LBL_UNSCHEDULED,
    LBL_RECHECK,
    LBL_SCRAPPED,
]


# ---------- 字段解析 ----------

def _parse_iso_date(value: Any) -> date | None:
    """宽容解析 YYYY-MM-DD；无法识别时返回 None，由调用方决定口径。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        year, month, day = (int(part) for part in text.split("-"))
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def _parse_iso_date_strict(value: Any, field: str) -> tuple[date | None, str]:
    """保存入口的严格校验：空值放行（返回 None），格式错误给出字段名。"""
    if value is None or not str(value).strip():
        return None, ""
    parsed = _parse_iso_date(value)
    if parsed is None:
        return None, f"{field}格式无法识别，请使用 YYYY-MM-DD（收到：{value}）"
    return parsed, ""


def parse_cycle_months(value: Any) -> int | None:
    """把检修周期解析成月数。

    支持纯数字（按月）与「12个月」「3 月」这类带单位写法；无法识别返回 None。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        months = int(text)
        return months if months > 0 else None
    match = re.match(r"^(\d+)\s*个?\s*月$", text)
    if match:
        months = int(match.group(1))
        return months if months > 0 else None
    return None


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def parse_resistance(value: Any) -> tuple[float | None, str]:
    """解析接点电阻，返回 (数值, 异常说明)。空、非数值、越界都会给说明。"""
    if value is None or not str(value).strip():
        return None, "接点电阻为空，需要复检确认"
    text = str(value).strip().replace("Ω", "").strip()
    try:
        number = float(text)
    except ValueError:
        return None, f"接点电阻「{value}」不是有效数值，需要复检确认"
    if number < RESISTANCE_MIN or number > RESISTANCE_MAX:
        return number, (
            f"接点电阻 {number:g}Ω 超出允许范围"
            f"（{RESISTANCE_MIN:g}~{RESISTANCE_MAX:g}Ω），需要复检确认"
        )
    return number, ""


# ---------- 结论推导（列表/明细共用，禁止分叉） ----------

def _last_history_date(entry: dict[str, Any]) -> date | None:
    """从检修历史取最近一次实际检修日期；历史缺失时回落到台账检修日期。"""
    latest: date | None = None
    for item in entry.get("检修历史") or []:
        day = _parse_iso_date(item.get("检修日期"))
        if day and (latest is None or day > latest):
            latest = day
    if latest is not None:
        return latest
    return _parse_iso_date(entry.get("检修日期"))


def derive_conclusion(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """根据台账字段推导单台继电器的检修结论。

    判定优先级：已报废 > 待复检（接点电阻空/越界）> 未排检修 >
    已到期 > 即将到期 > 正常。reasons 会把命中的全部原因列全，
    页面无论列表还是明细都直接展示这里返回的内容。
    """
    today = today or date.today()
    reasons: list[str] = []

    if entry.get("status") == STATUS_ORDER[-1]:
        return {
            "label": LBL_SCRAPPED,
            "reasons": ["该继电器已报废，不再安排检修"],
            "due_date": None,
            "cycle_due_date": None,
            "next_date": _text_date(entry.get("下次检修日")),
            "days_left": None,
            "flags": {"scrapped": True, "recheck": False, "unscheduled": False,
                      "overdue": False, "due_soon": False},
        }

    # 1) 接点电阻：空值或超出允许范围 → 待复检
    _, resistance_issue = parse_resistance(entry.get("接点电阻"))
    if resistance_issue:
        reasons.append(resistance_issue)

    # 2) 到期判定：检修周期与上次检修日缺一不可
    last_day = _last_history_date(entry)
    if last_day is None:
        reasons.append("缺少上次检修日，无法按周期推算到期时间")
    cycle_months = parse_cycle_months(entry.get("检修周期"))
    if cycle_months is None:
        reasons.append("缺少有效的检修周期，无法按周期推算到期时间")

    cycle_due: date | None = None
    if last_day is not None and cycle_months is not None:
        cycle_due = _add_months(last_day, cycle_months)

    # 3) 未排检修：没有下次检修日单独呈现，而不是留空白
    next_day = _parse_iso_date(entry.get("下次检修日"))
    if next_day is None:
        reasons.append("尚未录入下次检修日，按未排检修处理，请尽快补录")

    # 4) 综合到期：周期推算日与排定日取较早者作为实际到期日
    due_candidates = [day for day in (cycle_due, next_day) if day is not None]
    effective_due = min(due_candidates) if due_candidates else None
    overdue = effective_due is not None and effective_due < today
    days_left = (effective_due - today).days if effective_due is not None else None
    if overdue:
        if cycle_due is not None and cycle_due < today and (next_day is None or next_day >= today):
            reasons.append(
                f"按检修周期（{cycle_months}个月）与上次检修日（{last_day}）推算，"
                f"应于 {cycle_due} 前检修，已到期但下次检修日未提前"
            )
        else:
            reasons.append(f"已超过到期日 {effective_due}，请尽快安排检修")

    if resistance_issue:
        label = LBL_RECHECK
    elif next_day is None:
        label = LBL_UNSCHEDULED
    elif overdue:
        label = LBL_OVERDUE
    elif days_left is not None and days_left <= DUE_SOON_DAYS:
        label = LBL_DUE_SOON
        reasons.append(f"距到期日 {effective_due} 不足 {DUE_SOON_DAYS} 天，请提前安排")
    else:
        label = LBL_NORMAL
        if effective_due is not None:
            reasons.append(f"检修状态正常，下次到期日 {effective_due}")

    return {
        "label": label,
        "reasons": reasons,
        "due_date": effective_due.isoformat() if effective_due else None,
        "cycle_due_date": cycle_due.isoformat() if cycle_due else None,
        "next_date": next_day.isoformat() if next_day else None,
        "days_left": days_left,
        "flags": {
            "scrapped": False,
            "recheck": label == LBL_RECHECK,
            "unscheduled": next_day is None,
            "overdue": bool(overdue),
            "due_soon": label == LBL_DUE_SOON,
        },
    }


def _text_date(value: Any) -> str | None:
    day = _parse_iso_date(value)
    return day.isoformat() if day else None


def _sync_flags(entry: dict[str, Any]) -> None:
    """把派生结论同步回顶层标记，供概览卡片统计。"""
    conclusion = derive_conclusion(entry)
    flags = conclusion["flags"]
    entry["conclusion"] = conclusion
    entry["abnormal"] = bool(flags["recheck"] or flags["overdue"] or flags["unscheduled"])
    entry["pending"] = not flags["scrapped"]


class RelayService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        conclusion: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        rows = store.rows(MODULE)
        matched: list[dict[str, Any]] = []
        summary = {label: 0 for label in CONCLUSION_LABELS}
        for row in rows:
            result = derive_conclusion(row)
            row["conclusion"] = result
            summary[result["label"]] += 1
            if keyword and keyword not in str(row.get("继电器编号", "")):
                continue
            if status and row.get("status") != status:
                continue
            if conclusion and result["label"] != conclusion:
                continue
            matched.append(row)
        total = len(matched)
        start = max(page - 1, 0) * size
        return matched[start:start + size], total, summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        entry["conclusion"] = derive_conclusion(entry)
        return entry

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in EDITABLE_FIELDS:
            entry[field] = (values.get(field) or "").strip() if isinstance(values.get(field), str) else values.get(field)
        entry["检修日期"] = None
        entry["下次检修日"] = None
        entry["检修历史"] = []
        entry["检修安排记录"] = []
        entry["status"] = STATUS_ORDER[0]
        _sync_flags(entry)
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """补录/修改台账字段。下次检修日早于上次检修日时拒绝保存并指明对不上的位置。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"继电器 {entry_id} 不存在或已归档"

        for field in EDITABLE_FIELDS:
            if field in values:
                raw = values.get(field)
                entry[field] = raw.strip() if isinstance(raw, str) else raw

        next_day, err = _parse_iso_date_strict(values.get("下次检修日"), "下次检修日")
        if err:
            return None, err
        if "下次检修日" in values:
            if next_day is None and str(values.get("下次检修日") or "").strip() == "":
                entry["下次检修日"] = None
            elif next_day is not None:
                entry["下次检修日"] = next_day.isoformat()

        last_day = _last_history_date(entry)
        if next_day is not None and last_day is not None and next_day < last_day:
            return None, (
                f"下次检修日 {next_day} 早于上次检修日 {last_day}，"
                "两个日期对不上：下次检修日不能排在上次检修日之前，请核对后重新提交"
            )

        # 补录下次检修日只动排定字段，检修历史原样保留
        _sync_flags(entry)
        return entry, "继电器台账已更新，检修历史已保留"

    def record_maintenance(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """登记一次实际检修：校验日期先后，追加历史，刷新排定的下次检修日。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"继电器 {entry_id} 不存在或已归档"

        maintenance_day, err = _parse_iso_date_strict(values.get("检修日期"), "检修日期")
        if err:
            return None, err
        if maintenance_day is None:
            return None, "检修日期不能为空，请填写本次实际检修日期（YYYY-MM-DD）"

        previous_day = _last_history_date(entry)
        if previous_day is not None and maintenance_day < previous_day:
            return None, (
                f"本次检修日期 {maintenance_day} 早于上次检修日 {previous_day}，"
                "两个日期对不上：检修记录必须晚于或等于最近一次检修，请核对后重新提交"
            )

        next_day, err = _parse_iso_date_strict(values.get("下次检修日"), "下次检修日")
        if err:
            return None, err
        if next_day is not None and next_day < maintenance_day:
            return None, (
                f"下次检修日 {next_day} 早于本次检修日期 {maintenance_day}，"
                "两个日期对不上：下次检修日不能排在本次检修之前，请核对后重新提交"
            )

        resistance = values.get("接点电阻")
        if resistance is not None and str(resistance).strip():
            entry["接点电阻"] = str(resistance).strip()

        history = entry.setdefault("检修历史", [])
        history.append({
            "检修日期": maintenance_day.isoformat(),
            "接点电阻": entry.get("接点电阻"),
            "电气特性": values.get("电气特性") or entry.get("电气特性"),
            "备注": values.get("备注") or "",
        })
        entry["检修日期"] = maintenance_day.isoformat()

        if next_day is not None:
            entry["下次检修日"] = next_day.isoformat()
        elif values.get("按周期顺延") and parse_cycle_months(entry.get("检修周期")) is not None:
            entry["下次检修日"] = _add_months(
                maintenance_day, parse_cycle_months(entry["检修周期"])
            ).isoformat()

        _sync_flags(entry)
        return entry, f"检修记录已登记（{maintenance_day}），下次检修日：{entry['下次检修日'] or '未排'}"

    def schedule_maintenance(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """安排下次检修；同一台继电器重复安排时以最近一次提交为准。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"继电器 {entry_id} 不存在或已归档"

        next_day, err = _parse_iso_date_strict(values.get("下次检修日"), "下次检修日")
        if err:
            return None, err
        if next_day is None:
            return None, "下次检修日不能为空，未排检修的设备请先在台账补录日期"

        last_day = _last_history_date(entry)
        if last_day is not None and next_day < last_day:
            return None, (
                f"下次检修日 {next_day} 早于上次检修日 {last_day}，"
                "两个日期对不上：不能把检修安排在最近一次检修之前，请核对后重新提交"
            )

        schedules = entry.setdefault("检修安排记录", [])
        previous = entry.get("下次检修日")
        schedules.append({
            "下次检修日": next_day.isoformat(),
            "原排定日期": previous,
            "安排时间": date.today().isoformat(),
            "备注": values.get("备注") or "",
        })
        entry["下次检修日"] = next_day.isoformat()
        _sync_flags(entry)
        note = f"（覆盖原排定 {previous}，以最近一次安排为准）" if previous else ""
        return entry, f"下次检修已安排在 {next_day}{note}"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"继电器 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于继电器检修可执行范围"
        target = ACTION_RULES[action]
        entry["status"] = target
        _sync_flags(entry)
        return entry, f"继电器已{action}"
