from pydantic import BaseModel, ConfigDict
from datetime import datetime


class PermissionOut(BaseModel):
    """单个权限的展示格式，用于嵌套在角色详情里"""
    id: int
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleOut(BaseModel):
    """角色基本信息，不含权限列表，用于嵌套在用户对象里展示"""
    id: int
    name: str
    is_system: bool

    model_config = ConfigDict(from_attributes=True)


class RoleDetail(RoleOut):
    """角色详情，比 RoleOut 多了权限列表，用于角色管理页面单独查看某个角色"""
    permissions: list[PermissionOut] = []



class UserWithRoleList(BaseModel):
    """后台用户列表专用，role 是嵌套对象而不是字符串"""
    id: int
    username: str
    email: str
    is_active: bool
    role: RoleOut

    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(BaseModel):
    """修改角色时的输入参数，全量替换权限集合"""
    id: int 
    name: str | None = None
    permission_ids: list[int] | None = None