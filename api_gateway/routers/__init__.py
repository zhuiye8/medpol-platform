"""路由模块聚合，方便 FastAPI 入口按需导入。"""

from . import admin, articles, scheduler

__all__ = ["admin", "articles", "scheduler"]
