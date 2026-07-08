import functools
import logging

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def log_call(func):
    """
    异步函数调用日志装饰器。

    记录被装饰函数的名称、文件路径及行号，用于追踪数据库操作等调用。

    Args:
        func: 被装饰的异步函数。

    Returns:
        Callable: 包装后的异步函数。
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        path = func.__code__.co_filename.split("HolocronBlog/")[-1]
        logger.info("[DB] %s (%s:%d)", func.__name__, path, func.__code__.co_firstlineno)
        return await func(*args, **kwargs)
    return wrapper
