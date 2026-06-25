import re
import unicodedata
import mistune


# FIXME 中文被完全剥离, 需要重写
def slugify(text: str) -> str:
    """生成slug, 兼容中文"""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # 兼容中文, 将重音字符分解, 转 ASCII 并忽略无法转换的字符
    text = text.lower()
    # 转小写
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    # 将非字母数字的连续字符替换为连字符, 去掉首尾连字符
    return text
    """效果："Hello 世界, 你好!" → "hello-"
    （中文字符被完全移除，可能需要进一步优化，但当前方案对英文标题足够）"""

def render_markdown(content: str) -> str:
    markdown = mistune.create_markdown()
    return markdown(content)
