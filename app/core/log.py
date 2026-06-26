import functools
import logging

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def log_call(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        path = func.__code__.co_filename.split("HolocronBlog/")[-1]
        logger.info("[DB] %s (%s:%d)", func.__name__, path, func.__code__.co_firstlineno)
        return await func(*args, **kwargs)
    return wrapper
