"""检测项目接口：维护检测项目，覆盖启用项目、提交修订、停用项目等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.project import PRICE_SORTS, ProjectService

router = APIRouter(prefix="/api/project", tags=["检测项目"])

service = ProjectService()

LIST_FIELDS = ["项目编码", "项目名称", "检测方法", "方法标准号", "检出限", "计量单位", "收费单价", "项目状态"]
STATUSES = ["草稿", "已启用", "待修订", "已停用"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按项目编码检索（兼容旧参数）"),
    status: str | None = Query(default=None, description="草稿、已启用、待修订、已停用"),
    code: str | None = Query(default=None, description="按项目编码检索"),
    standard: str | None = Query(default=None, description="按方法标准号检索"),
    unit: str | None = Query(default=None, description="按计量单位检索"),
    sort: str | None = Query(default=None, description="price_asc 或 price_desc，按收费单价排序"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """组合检索检测项目：项目编码/方法标准号/计量单位按「且」叠加，可按收费单价排序；
    条件冲突或查无结果时通过 hint 给出可读说明，绝不悄悄退回全量数据。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if sort is not None and sort not in PRICE_SORTS:
        supported = "、".join(PRICE_SORTS)
        raise HTTPException(status_code=400, detail=f"不支持的排序方式「{sort}」，可选：{supported}")
    items, total, hint = service.list_entries(
        keyword=keyword,
        status=status,
        code=code,
        standard=standard,
        unit=unit,
        sort=sort,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size, hint=hint)


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
    items, total, _ = service.list_entries(page=1, size=10000)
    return {"module": "project", "total": total, "items": items}
