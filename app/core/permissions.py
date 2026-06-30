
"""
权限常量定义
"""

ARTICLE_CREATE = "article:create"
ARTICLE_UPDATE = "article:update"
ARTICLE_DELETE = "article:delete"
ARTICLE_PUBLISH = "article:publish"
ARTICLE_UNPUBLISH = "article:unpublish"

COMMENT_CREATE = "comment:create"
COMMENT_DELETE = "comment:delete"

CATEGORY_MANAGE = "category:manage"
TAG_MANAGE = "tag:manage"

USER_MANAGE = "user:manage"
ROLE_MANAGE = "role:manage"

UPLOAD_CREATE = "upload:create"



"""定义admin角色权限集合"""
ALL_PERMISSIONS: set[str] = {
    ARTICLE_CREATE,
    ARTICLE_UPDATE,
    ARTICLE_DELETE,
    ARTICLE_PUBLISH,
    ARTICLE_UNPUBLISH,

    COMMENT_CREATE,
    COMMENT_DELETE,

    CATEGORY_MANAGE,
    TAG_MANAGE,

    USER_MANAGE,
    ROLE_MANAGE,
    UPLOAD_CREATE,
}

"""定义Author角色 权限集合
作者: 创建、修改、删除、发布文章、创建、删除评论、管理标签、上传文件
"""
AUTHOR_PERMISSIONS: set[str] = {
    ARTICLE_CREATE,
    ARTICLE_UPDATE,
    ARTICLE_DELETE,
    ARTICLE_PUBLISH,
    ARTICLE_UNPUBLISH,

    COMMENT_CREATE,
    COMMENT_DELETE,

    TAG_MANAGE,
    UPLOAD_CREATE,
}

"""定义User 角色 权限集合
用户: 评论创建,上传文件
"""
USER_PERMISSIONS: set[str] = {
    COMMENT_CREATE,
    UPLOAD_CREATE,
}




"""定义角色对应权限映射"""

DEFAULT_ROLES: dict[str, dict] = {
    "admin": {
        "description": "管理员角色",
        "is_system": True,
        "permissions": ALL_PERMISSIONS,
    },
    "author": {
        "description": "作者角色",
        "is_system": True,
        "permissions": AUTHOR_PERMISSIONS,
    },
    "user": {
        "description": "用户角色",
        "is_system": True,
        "permissions": USER_PERMISSIONS,
    },
}
