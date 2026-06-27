
import pytest
from app.services.article_service import slugify, render_markdown


class TestSlugify:
    """slugify 函数测试"""

    def test_normal_title(self):
        """普通英文标题 → 小写连字符"""
        assert slugify("Hello World") == "hello-world"

    def test_chinese_title(self):
        """中文标题 → 保留中文，空格变连字符"""
        assert slugify("我的 博客 文章") == slugify("我的-博客-文章")

    def test_special_chars_replaced(self):
        """特殊字符 → 替换为连字符"""
        assert slugify("Hello, World! #2024") == "hello-world-2024"

    def test_leading_trailing_dashes_removed(self):
        """首尾连字符被去除"""
        assert slugify("--hello--") == "hello"

    def test_empty_after_clean_returns_untitled(self):
        """纯特殊字符 → 'untitled'"""
        assert slugify("!!!") == "untitled"

    def test_whitespace_stripped(self):
        """首尾空格被去除"""
        assert slugify("  hello  ") == "hello"


class TestRenderMarkdown:
    """mistune markdown 渲染测试"""

    def test_heading(self):
        """# 标题 → <h1>"""
        html = render_markdown("# Title")
        assert "<h1>" in html
        assert "Title" in html

    def test_bold(self):
        """**粗体** → <strong>"""
        html = render_markdown("**bold**")
        assert "<strong>" in html
        assert "bold" in html

    def test_italic(self):
        """*斜体* → <em>"""
        html = render_markdown("*italic*")
        assert "<em>" in html
        assert "italic" in html

    def test_link(self):
        """[text](url) → <a href>"""
        html = render_markdown("[blog](https://example.com)")
        assert 'href="https://example.com"' in html
        assert "blog" in html

    def test_code_block(self):
        """```code``` → <pre><code>"""
        html = render_markdown("```\nprint('hello')\n```")
        assert "<pre>" in html or "<code>" in html

    def test_empty_string(self):
        """空字符串 → 空HTML"""
        assert render_markdown("") == ""

    def test_paragraph(self):
        """普通文本 → <p> 段落"""
        html = render_markdown("Hello")
        assert "<p>" in html
        assert "Hello" in html
