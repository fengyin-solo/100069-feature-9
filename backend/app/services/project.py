"""检测项目业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from typing import Any

from app.store import store

MODULE = "project"
REQUIRED_FIELDS = ["项目编码", "项目名称", "检测方法"]
STATUS_ORDER = ["草稿", "已启用", "待修订", "已停用"]
ACTION_RULES = {"启用项目": "已启用", "提交修订": "待修订", "停用项目": "已停用"}
NEGATIVE_ACTIONS = ["停用项目"]

# 可参与组合检索的文本字段，多个条件之间是「且」的关系
SEARCH_FIELDS = ["项目编码", "方法标准号", "计量单位"]
PRICE_FIELD = "收费单价"
PRICE_SORTS = {"price_asc": "收费单价从低到高", "price_desc": "收费单价从高到低"}
_PRICE_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_price(value: Any) -> float | None:
    """把「120元/项」「￥1,200.50」这类收费单价解析成可比较的数字，解析不出来返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _PRICE_RE.search(str(value).replace(",", ""))
    return float(match.group()) if match else None


class ProjectService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        code: str | None = None,
        standard: str | None = None,
        unit: str | None = None,
        sort: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, str | None]:
        rows = store.rows(MODULE)
        total_all = len(rows)

        # keyword 保留给旧调用方，等价于按项目编码检索
        terms = {
            "项目编码": code or keyword,
            "方法标准号": standard,
            "计量单位": unit,
        }
        active = {field: str(term).strip() for field, term in terms.items() if str(term or "").strip()}
        if status:
            active["项目状态"] = status.strip()

        for field, term in active.items():
            if field == "项目状态":
                # 项目状态以内部 status 字段为准
                rows = [row for row in rows if row.get("status") == term]
            else:
                rows = [row for row in rows if term in str(row.get(field, ""))]

        if sort in PRICE_SORTS:
            descending = sort == "price_desc"

            def price_key(row: dict[str, Any]) -> tuple[int, float]:
                price = parse_price(row.get(PRICE_FIELD))
                if price is None:
                    return (1, 0.0)  # 无法解析单价的记录在升降序下都排末尾
                return (0, -price if descending else price)

            rows.sort(key=price_key)

        total = len(rows)
        hint: str | None = None
        if total == 0:
            if active:
                if total_all == 0:
                    hint = "当前还没有登记任何检测项目数据"
                elif self._is_conflict(active):
                    hint = (
                        f"检索条件之间互相冲突：{self._describe_terms(active)}，"
                        "没有检测项目能同时满足，请放宽或调整条件"
                    )
                else:
                    hint = (
                        f"没有找到符合条件的检测项目（{self._describe_terms(active)}），"
                        "请检查检索词或放宽条件"
                    )
            else:
                hint = "当前还没有登记任何检测项目数据"

        start = max(page - 1, 0) * size
        return rows[start:start + size], total, hint

    def _is_conflict(self, active: dict[str, str]) -> bool:
        """判断空结果是不是条件打架造成的：逐字段放宽后每一项单独都能查到数据，
        但所有条件合在一起查不到，说明条件之间互相矛盾而不是系统里根本没有。"""
        if len(active) < 2:
            return False
        rows = store.rows(MODULE)
        for field, term in active.items():
            if field == "项目状态":
                alone = [row for row in rows if row.get("status") == term]
            else:
                alone = [row for row in rows if term in str(row.get(field, ""))]
            if not alone:
                return False
        return True

    @staticmethod
    def _describe_terms(active: dict[str, str]) -> str:
        labels = {
            "项目编码": "项目编码",
            "方法标准号": "方法标准号",
            "计量单位": "计量单位",
            "项目状态": "项目状态",
        }
        return "、".join(f"{labels.get(field, field)}含「{term}」" for field, term in active.items())

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测项目 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于检测项目可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"检测项目已{action}"
