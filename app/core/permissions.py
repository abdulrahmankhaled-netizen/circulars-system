"""
نظام الصلاحيات (RBAC) — يدعم wildcards مثل 'requests.*'.
"""
from typing import List


def _role_permissions(user) -> List[str]:
    """يجمع كل صلاحيات المستخدم من دوره."""
    if not user or not user.is_authenticated:
        return []
    role = getattr(user, "role", None)
    if not role:
        return []
    return role.get_permissions_list()


def _matches(permission: str, rule: str) -> bool:
    """فحص مطابقة صلاحية مع قاعدة."""
    if rule == "*":
        return True
    if rule == permission:
        return True
    if rule.endswith(".*"):
        prefix = rule[:-2]
        return permission == prefix or permission.startswith(prefix + ".")
    return False


def has_permission(user, permission: str) -> bool:
    """يعيد True إذا كان للمستخدم الصلاحية المطلوبة."""
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, "role", None)
    if role and role.name == "admin":
        return True
    perms = _role_permissions(user)
    return any(_matches(permission, r) for r in perms)


def require_permission(permission: str):
    """
    Decorator للـ routes.
    
    @require_permission("contracts.create")
    def add_contract(): ...
    """
    from functools import wraps
    from flask import abort
    from flask_login import current_user

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not has_permission(current_user, permission):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_any(*permissions: str):
    """يقبل إذا كان للمستخدم أي صلاحية من الممررة."""
    from functools import wraps
    from flask import abort
    from flask_login import current_user

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not any(has_permission(current_user, p) for p in permissions):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_role(*role_names: str):
    """يتحقق من اسم الدور مباشرة."""
    from functools import wraps
    from flask import abort
    from flask_login import current_user

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            role = getattr(current_user, "role", None)
            if not role or role.name not in role_names:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator