from fastapi import Query
from pydantic import BaseModel


class PageParams(BaseModel):
    """分页参数模型"""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size

    def calc_has_more(self, total: int) -> bool:
        """计算是否有下一页"""
        return self.page * self.page_size < total


# 分页参数依赖项
def get_page_params(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=1000, description="每页数量"),
) -> PageParams:
    """获取分页参数"""
    return PageParams(page=page, page_size=page_size)
