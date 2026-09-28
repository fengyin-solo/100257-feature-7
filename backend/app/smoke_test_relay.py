"""继电器检修边界规则冒烟测试。

运行：python3 -m app.smoke_test_relay
不依赖 pytest，直接对内存仓库走一遍业务规则，任一口径不符即非零退出。
"""
from __future__ import annotations

from app.services.relay import (
    LBL_DUE_SOON,
    LBL_NORMAL,
    LBL_OVERDUE,
    LBL_RECHECK,
    LBL_SCRAPPED,
    LBL_UNSCHEDULED,
    RelayService,
)

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        FAILURES.append(message)


def main() -> int:
    svc = RelayService()
    items, total, summary = svc.list_entries(page=1, size=100)
    labels = {row["继电器编号"]: row["conclusion"]["label"] for row in items}
    by_id = {row["继电器编号"]: row for row in items}

    check(total == 8, f"种子台账共 8 条（实际 {total}）")
    check(labels.get("RELA-0001") == LBL_NORMAL, "周期与日期都未到：正常")
    check(labels.get("RELA-0002") == LBL_OVERDUE, "周期推算已到期但排期靠后：已到期")
    check(labels.get("RELA-0003") == LBL_RECHECK, "接点电阻为空：待复检优先于已到期")
    check(labels.get("RELA-0004") == LBL_RECHECK, "接点电阻越界：待复检")
    check(labels.get("RELA-0005") == LBL_UNSCHEDULED, "无下次检修日：未排检修单独呈现")
    check(labels.get("RELA-0006") == LBL_DUE_SOON, "7 天内到期：即将到期")
    check(labels.get("RELA-0007") == LBL_SCRAPPED, "报废设备不再参与到期判定")

    # 列表与明细口径一致
    for row in items:
        detail = svc.get_entry(row["id"])
        check(
            detail is not None
            and detail["conclusion"]["label"] == row["conclusion"]["label"]
            and detail["conclusion"]["reasons"] == row["conclusion"]["reasons"],
            f"id={row['id']} 列表与明细结论一致",
        )

    # 日期倒挂拒绝并说明对不上的位置
    _, msg = svc.update_entry(5, {"下次检修日": "2026-06-01"})
    check("早于上次检修日" in msg and "2026-07-02" in msg and "2026-06-01" in msg,
          "补录日期早于上次检修日：拒绝并指出两个日期")
    _, msg = svc.record_maintenance(1, {"检修日期": "2026-01-01", "下次检修日": "2026-07-01"})
    check("早于上次检修日" in msg, "检修登记日期早于历史最近一次：拒绝")
    _, msg = svc.schedule_maintenance(1, {"下次检修日": "2020-01-01"})
    check("不能把检修安排在最近一次检修之前" in msg, "排期早于上次检修日：拒绝")

    # 补录下次检修日后历史保留
    entry, msg = svc.update_entry(5, {"下次检修日": "2027-01-02"})
    check(entry is not None and len(entry["检修历史"]) == 1, "补录下次检修日后检修历史保留")

    # 登记检修追加历史、刷新排期
    entry, msg = svc.record_maintenance(
        4, {"检修日期": "2026-09-28", "接点电阻": "0.03", "下次检修日": "2026-12-28"}
    )
    check(entry is not None and len(entry["检修历史"]) == 2
          and entry["conclusion"]["label"] == LBL_NORMAL, "复检合格后待复检解除，历史追加")

    # 重复安排以最近一次为准
    svc.schedule_maintenance(8, {"下次检修日": "2027-05-01"})
    entry, _ = svc.schedule_maintenance(8, {"下次检修日": "2027-06-01"})
    check(entry is not None and entry["下次检修日"] == "2027-06-01",
          "同一台继电器重复安排：以最近一次为准")

    check(summary.get(LBL_RECHECK) == 2, f"统计口径含待复检 2 台（实际 {summary}）")

    if FAILURES:
        print(f"\n{len(FAILURES)} 项规则未通过")
        return 1
    print("\n全部继电器检修边界规则通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
