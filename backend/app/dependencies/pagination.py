from fastapi import Query

from app.common.base import PageParams


# 分页参数依赖项
def get_page_params(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=1000, description="每页数量"),
) -> PageParams:
    """获取分页参数"""
    return PageParams(page=page, page_size=page_size)
