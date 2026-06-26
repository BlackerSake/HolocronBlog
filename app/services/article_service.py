import re
import unicodedata
import mistune


def slugify(text: str) -> str:
    """生成slug, 保留中文, 空格/特殊字符替换为连字符"""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', text).strip('-')
    return text or 'untitled'


def render_markdown(content: str) -> str:
    markdown = mistune.create_markdown()
    return markdown(content)
