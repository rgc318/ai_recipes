# -*- coding: utf-8 -*-
"""
应用程序权限定义 - Single Source of Truth

1. PERMISSIONS_CONFIG (List[Dict]):
 - 权限的“事实来源”定义，一个字典列表。
 - 用于“同步权限”功能，将权限信息写入数据库。

2. Permissions (Class Enum-like):
 - 一个自动生成的、类似枚举的类，用于在后端代码中安全地引用权限代码。
 - 它消除了魔法字符串，提供了IDE自动补全，并使得重构变得简单。
"""
class PermissionGroups:
    DASHBOARD = "仪表盘"
    USER_MANAGEMENT = "用户管理"
    ROLE_MANAGEMENT = "角色管理"
# ----------------------------------------------------------------
# 步骤一：保留我们用于“同步”的原始列表
# ----------------------------------------------------------------
PERMISSIONS_CONFIG = [
  {
    "code": "dashboard:view",
    "name": "查看仪表盘123",
    "group": PermissionGroups.DASHBOARD,
    "description": "允许用户查看分析页和工作台。",
  },
  {
    "code": "management:user:list",
    "name": "查看用户列表",
    "group": PermissionGroups.USER_MANAGEMENT,
    "description": "允许用户查看用户分页列表。",
  },
  {
    "code": "management:user:create",
    "name": "创建用户",
    "group": PermissionGroups.USER_MANAGEMENT,
    "description": "允许用户创建新用户。",
  },
  {
    "code": "management:user:update",
    "name": "编辑用户",
    "group": PermissionGroups.USER_MANAGEMENT,
    "description": "允许用户更新现有用户信息。",
  },
  {
    "code": "management:user:delete",
    "name": "删除用户",
    "group": PermissionGroups.USER_MANAGEMENT,
    "description": "允许用户删除用户。",
  },
  # ... 其他所有权限
]

# ----------------------------------------------------------------
# 步骤二：自动生成一个易于在代码中使用的“权限枚举”类
# ----------------------------------------------------------------
class _Permissions:
    """
    一个用于在代码中提供权限代码自动补全和类型安全的类。
    通过动态属性赋值，将权限代码（如 'management:user:list'）
    映射到一个易于访问的类属性上（如 Permissions.MANAGEMENT_USER_LIST）。
    """
    def __init__(self):
        for perm in PERMISSIONS_CONFIG:
            # 将 'management:user:list' 转换为 'MANAGEMENT_USER_LIST'
            key = perm['code'].replace(':', '_').replace('-', '_').upper()
            # 设置类属性，值为原始的 code 字符串
            setattr(self, key, perm['code'])

# 创建一个该类的单例，供整个应用导入和使用
Permissions = _Permissions()

