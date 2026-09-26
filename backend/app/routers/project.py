"""检测项目接口：维护检测项目，覆盖启用项目、提交修订、停用项目等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.project import SORTABLE_FIELDS, SORT_ORDERS, ProjectService

router = APIRouter(prefix="/api/project", tags=["检测项目"])

service = ProjectService()

LIST_FIELDS = ["项目编码", "项目名称", "检测方法", "方法标准号", "检出限", "计量单位", "收费单价", "项目状态"]
STATUSES = ["草稿", "已启用", "待修订", "已停用"]

FILTER_LABELS = {"code": "项目编码", "standard": "方法标准号", "unit": "计量单位"}


def _single_value(param: str, values: list[str]) -> str | None:
    """同一检索条件只接受一个值；传了多个互斥值时说明原因，而不是随便挑一个。"""
    cleaned = [value.strip() for value in values if value and value.strip()]
    if len(cleaned) > 1:
        label = FILTER_LABELS[param]
        raise HTTPException(
            status_code=400,
            detail=f"检索条件互相冲突：{label}同时给了「{'、'.join(cleaned)}」，请只保留一个再查询",
        )
    return cleaned[0] if cleaned else None


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按项目编码检索"),
    status: str | None = Query(default=None, description="草稿、已启用、待修订、已停用"),
    code: list[str] = Query(default=[], description="按项目编码组合检索"),
    standard: list[str] = Query(default=[], description="按方法标准号组合检索"),
    unit: list[str] = Query(default=[], description="按计量单位组合检索"),
    sort: str | None = Query(default=None, description="排序字段，目前支持收费单价"),
    order: str = Query(default="asc", description="排序方向：asc 升序、desc 降序"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按项目编码、方法标准号、计量单位组合过滤，并可按收费单价排序；条件冲突或没有命中时返回可读说明，绝不静默返回全量。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if sort is not None and sort not in SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"暂不支持按「{sort}」排序，目前仅支持收费单价")
    if order not in SORT_ORDERS:
        raise HTTPException(status_code=400, detail=f"排序方向「{order}」无法识别，只支持 asc（升序）或 desc（降序）")
    items, total = service.list_entries(
        keyword=keyword,
        status=status,
        code=_single_value("code", code),
        standard=_single_value("standard", standard),
        unit=_single_value("unit", unit),
        sort=sort,
        order=order,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检测项目明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检测项目 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检测项目，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检测项目已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条检测项目执行启用项目、提交修订、停用项目；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出检测项目清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "project", "total": total, "items": items}
