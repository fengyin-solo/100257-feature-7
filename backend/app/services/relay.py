"""继电器检修业务规则。

边界口径全部收敛在本模块：
- 结论（检修判定）只由 derive_conclusion 推导，列表与明细共用，保证两处说法一致；
- 没有下次检修日 -> 未排检修；
- 接点电阻为空 / 无法识别 / 超出允许范围 -> 待复检；
- 到期判定同时依赖检修周期与上次检修日；
- 排期、检修记录的日期早于上次检修日一律拒绝保存，并指明对不上的两个日期；
- 同一台继电器重复安排检修以最近一次为准，历次排期留在检修历史里不覆盖。
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

MODULE = "relay"
REQUIRED_FIELDS = ["继电器编号", "继电器型号", "所属设备"]
TECH_STATUSES = ["特性合格", "特性偏移", "接点氧化", "已报废"]

# 接点电阻允许范围（Ω）：必须为正数且不超过上限
RESISTANCE_MIN_OHM = 0.0
RESISTANCE_MAX_OHM = 0.05

# 结论编码 -> 页面文案；顺序即优先级（同一台继电器命中多条时取最靠前的）
CONCLUSIONS: list[tuple[str, str]] = [
    ("scrapped", "已报废"),
    ("reinspect", "待复检"),
    ("unscheduled", "未排检修"),
    ("overdue", "已到期"),
    ("upcoming", "未到期"),
]
CONCLUSION_LABELS = dict(CONCLUSIONS)
ABNORMAL_CODES = {"reinspect", "overdue"}

DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def parse_date(value: Any) -> date | None:
    """认 YYYY-MM-DD；其余写法（含空白、乱码样例）一律返回 None，由调用方决定口径。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = DATE_RE.match(text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def parse_cycle_months(value: Any) -> float | None:
    """把检修周期换算成月数：支持「12个月 / 12月 / 1年 / 90天」这类常见写法。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    number = NUMBER_RE.search(text.replace("，", "."))
    if number is None:
        return None
    amount = float(number.group(0))
    if "年" in text:
        return amount * 12
    if "天" in text or "日" in text:
        return round(amount / 30.0, 2)
    # “个月 / 月 / 纯数字”都按月理解
    return amount


def add_months(base: date, months: float) -> date:
    """在某个日期上加月数，月末自动收敛到当月最后一天，零头月按每月 30 天折算。"""
    whole = int(months)
    extra_days = round((months - whole) * 30)
    shifted_month = base.month - 1 + whole
    year = base.year + shifted_month // 12
    month = shifted_month % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day) + timedelta(days=extra_days)


def parse_resistance_ohm(value: Any) -> tuple[float | None, bool]:
    """解析接点电阻，返回（欧姆值, 是否可识别）。

    支持 0.03 / 0.03Ω / 30mΩ 等写法；空白与无法识别的数值都算不可识别，
    交由结论口径按“待复检”处理，而不是在这里抛错。
    """
    if value is None:
        return None, False
    text = str(value).strip()
    if not text:
        return None, False
    match = NUMBER_RE.search(text.replace("，", "."))
    if match is None:
        return None, False
    ohm = float(match.group(0))
    if "m" in text.lower() or "毫" in text:
        ohm /= 1000.0
    return ohm, True


def derive_conclusion(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """根据台账字段推导检修结论。列表、明细、导出都走这里，避免两处口径漂移。"""
    today = today or date.today()
    reasons: list[str] = []

    last_date = parse_date(entry.get("上次检修日"))
    next_date = parse_date(entry.get("下次检修日"))
    cycle_months = parse_cycle_months(entry.get("检修周期"))
    resistance_raw = entry.get("接点电阻")
    resistance_ohm, resistance_readable = parse_resistance_ohm(resistance_raw)

    # 到期判定：检修周期与上次检修日缺一不可
    due_date: date | None = None
    if last_date is not None and cycle_months is not None and cycle_months > 0:
        due_date = add_months(last_date, cycle_months)

    # 接点电阻：为空 / 无法识别 / 越界 -> 待复检
    resistance_ok = False
    if not resistance_readable:
        if not str(resistance_raw or "").strip():
            reasons.append(
                f"接点电阻未记录，无法核对是否在允许范围（≤{RESISTANCE_MAX_OHM:g}Ω），需现场复测"
            )
        else:
            reasons.append(
                f"接点电阻「{resistance_raw}」无法识别为数值，需现场复测后补录"
            )
    elif not (RESISTANCE_MIN_OHM < resistance_ohm <= RESISTANCE_MAX_OHM):
        reasons.append(
            f"接点电阻 {resistance_ohm:g}Ω 超出允许范围"
            f"（{RESISTANCE_MIN_OHM:g}～{RESISTANCE_MAX_OHM:g}Ω），需现场复测"
        )
    else:
        resistance_ok = True

    # 到期 / 排期口径
    overdue = due_date is not None and today > due_date
    if due_date is not None:
        if overdue:
            reasons.append(
                f"按检修周期 {cycle_months:g} 个月与上次检修日 {last_date:%Y-%m-%d} 推算，"
                f"应在 {due_date:%Y-%m-%d} 前完成检修，现已到期"
            )
        else:
            reasons.append(
                f"按检修周期 {cycle_months:g} 个月与上次检修日 {last_date:%Y-%m-%d} 推算，"
                f"下次到期日为 {due_date:%Y-%m-%d}"
            )

    if next_date is None:
        reasons.append("未填写下次检修日，检修尚未排期，请尽快补录")
    elif due_date is not None and next_date > due_date:
        reasons.append(
            f"已排下次检修日 {next_date:%Y-%m-%d} 晚于按周期推算的到期日 "
            f"{due_date:%Y-%m-%d}，存在超期检修风险，请核对排期"
        )

    scrapped = str(entry.get("继电器状态") or "").strip() == "已报废"

    if scrapped:
        code = "scrapped"
    elif not resistance_ok:
        code = "reinspect"
    elif next_date is None:
        code = "unscheduled"
    elif overdue:
        code = "overdue"
    else:
        code = "upcoming"

    return {
        "code": code,
        "label": CONCLUSION_LABELS[code],
        "reasons": reasons,
        "due_date": due_date.strftime("%Y-%m-%d") if due_date else None,
        "resistance_ohm": resistance_ohm,
        "resistance_ok": resistance_ok,
    }


def decorate(entry: dict[str, Any]) -> dict[str, Any]:
    """给台账记录挂上派生结论，不修改原始字段；历史记录原样带回。"""
    decorated = dict(entry)
    decorated["conclusion"] = derive_conclusion(entry)
    return decorated


def _sync_flags(entry: dict[str, Any]) -> None:
    """把结论同步到 pending/abnormal，供不经过 decorate 的运营概览使用。"""
    conclusion = derive_conclusion(entry)
    entry["status"] = entry.get("继电器状态") or TECH_STATUSES[0]
    entry["pending"] = conclusion["code"] != "scrapped"
    entry["abnormal"] = conclusion["code"] in ABNORMAL_CODES


class RelayService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        tech_status: str | None = None,
        conclusion: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("继电器编号", ""))]
        if tech_status:
            rows = [row for row in rows if str(row.get("继电器状态") or "").strip() == tech_status]
        if conclusion:
            rows = [row for row in rows if derive_conclusion(row)["code"] == conclusion]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [decorate(row) for row in rows[start:start + size]], total

    def summary(self) -> dict[str, int]:
        """按结论统计台账数量，供列表页顶部卡片使用（口径与列表完全一致）。"""
        counts = {code: 0 for code, _ in CONCLUSIONS}
        for row in store.rows(MODULE):
            counts[derive_conclusion(row)["code"]] += 1
        counts["total"] = len(store.rows(MODULE))
        return counts

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return decorate(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ["继电器编号", "继电器型号", "所属设备", "电气特性", "接点电阻", "检修周期"]:
            entry[field] = str(values.get(field) or "").strip()
        last_raw = str(values.get("上次检修日") or "").strip()
        entry["上次检修日"] = last_raw if parse_date(last_raw) else ""
        entry["下次检修日"] = ""
        tech = str(values.get("继电器状态") or "").strip()
        entry["继电器状态"] = tech if tech in TECH_STATUSES else TECH_STATUSES[0]
        entry["history"] = [
            {
                "type": "create",
                "title": "登记台账",
                "detail": "继电器登记入库，下次检修日待补录",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        ]
        _sync_flags(entry)
        rows.append(entry)
        return decorate(entry), []

    def schedule_inspection(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """安排（补录）下次检修日。同一台继电器重复安排时以最近一次为准。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"继电器 {entry_id} 不存在或已归档"
        next_date = parse_date(values.get("下次检修日"))
        if next_date is None:
            return None, "下次检修日为空或日期格式不正确，应为 YYYY-MM-DD，未保存"
        last_date = parse_date(entry.get("上次检修日"))
        if last_date is not None and next_date < last_date:
            return (
                None,
                f"下次检修日 {next_date:%Y-%m-%d} 早于上次检修日 {last_date:%Y-%m-%d}，"
                "排期与检修历史对不上，请核对后重新提交",
            )
        previous = parse_date(entry.get("下次检修日"))
        entry.setdefault("history", []).append(
            {
                "type": "schedule",
                "title": "安排检修",
                "detail": (
                    f"下次检修日排定为 {next_date:%Y-%m-%d}"
                    + (f"（覆盖此前排期 {previous:%Y-%m-%d}，以最近一次安排为准）" if previous else "")
                ),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        entry["下次检修日"] = next_date.strftime("%Y-%m-%d")
        _sync_flags(entry)
        return decorate(entry), f"已排定下次检修日 {next_date:%Y-%m-%d}"

    def save_inspection(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """登记一次检修完成记录。日期倒挂直接拒绝；电阻异常不拦截，结论转待复检。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"继电器 {entry_id} 不存在或已归档"
        inspect_date = parse_date(values.get("检修日期"))
        if inspect_date is None:
            return None, "检修日期为空或格式不正确，应为 YYYY-MM-DD，未保存"
        last_date = parse_date(entry.get("上次检修日"))
        if last_date is not None and inspect_date < last_date:
            return (
                None,
                f"检修日期 {inspect_date:%Y-%m-%d} 早于上次检修日 {last_date:%Y-%m-%d}，"
                "与已有检修历史对不上，请核对后重新提交",
            )

        resistance_raw = str(values.get("接点电阻") if values.get("接点电阻") is not None else "").strip()
        if "电气特性" in values and str(values.get("电气特性") or "").strip():
            entry["电气特性"] = str(values.get("电气特性")).strip()
        tech = str(values.get("继电器状态") or "").strip()
        if tech in TECH_STATUSES:
            entry["继电器状态"] = tech

        resistance_ohm, readable = parse_resistance_ohm(resistance_raw)
        if not readable and resistance_raw:
            resistance_note = f"，填报值「{resistance_raw}」无法识别"
        elif readable and not (RESISTANCE_MIN_OHM < resistance_ohm <= RESISTANCE_MAX_OHM):
            resistance_note = (
                f"，接点电阻 {resistance_ohm:g}Ω 超出允许范围"
                f"（≤{RESISTANCE_MAX_OHM:g}Ω），按待复检处理"
            )
        elif not readable:
            resistance_note = "，接点电阻未填报，按待复检处理"
        else:
            resistance_note = ""

        # 完成一次检修后旧排期已执行，下次检修日回到“待补录”，但历史完整保留
        entry.setdefault("history", []).append(
            {
                "type": "inspect",
                "title": "检修完成",
                "detail": f"{inspect_date:%Y-%m-%d} 完成检修{resistance_note}",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        entry["接点电阻"] = resistance_raw
        entry["上次检修日"] = inspect_date.strftime("%Y-%m-%d")
        entry["下次检修日"] = ""
        _sync_flags(entry)
        return decorate(entry), f"检修记录已保存（{inspect_date:%Y-%m-%d}）"
