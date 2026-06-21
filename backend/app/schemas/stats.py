"""消费分析聚合（服务端 SQL group by，前端只画图不再全量 reduce）。"""

from pydantic import BaseModel


class StatBucket(BaseModel):
    amount: float
    count: int


class CategoryStat(BaseModel):
    category: str
    amount: float
    count: int


class MonthStat(BaseModel):
    month: str  # YYYY-MM
    amount: float
    count: int


class StatsOut(BaseModel):
    total: float
    count: int
    # 报销三态金额/张数：键为 unreimbursed/submitted/reimbursed，三态恒全（缺省为 0）
    by_reimbursement: dict[str, StatBucket]
    by_category: list[CategoryStat]  # 按金额降序
    by_month: list[MonthStat]  # 连续月份（缺月补 0），旧→新
