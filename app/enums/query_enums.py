from enum import Enum

class ViewMode(str, Enum):
    """
    一个通用的枚举，用于定义列表查询时的数据查看模式。
    继承自 str 和 Enum，可以让成员在 API 中作为字符串值直接使用。
    """
    ACTIVE = 'active'   # 只看活跃的（未被软删除）
    ALL = 'all'         # 查看全部（包括软删除的）
    DELETED = 'deleted'   # 只看已被软删除的