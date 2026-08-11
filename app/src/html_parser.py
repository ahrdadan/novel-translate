import re

from bs4 import BeautifulSoup, Comment

TAG_REPLACEMENTS = {
    "strong": "**", "b": "**", "em": "*", "i": "*",
    "h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### ",
}
UNWANTED_ELEMENTS = {
    "script", "style", "meta", "title", "head", "noscript", 
    "iframe", "video", "audio", "nav", "footer", "header", "aside", "svg"
}

def convert_html_to_md(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(string=lambda text: isinstance(text, Comment)):
        element.extract()
        
    body = soup.body if soup.body else soup
    if not body:
        return ""

    def process_node(node):
        if isinstance(node, str):
            text = re.sub(r'[\s\xa0]+', ' ', node)
            text = re.sub(r'(.)\1{4,}', r'\1\1\1\1\1', text)
            return text
        if node.name in UNWANTED_ELEMENTS:
            return ""
        if node.name == "hr":
            return "***\n"
        if node.name == "br":
            return "\n"
        if node.name == "img":
            return ""
        if node.name in ("p", "div", "blockquote"):
            result_parts = [process_node(child) for child in node.children]
            inner = "".join(result_parts).strip()
            
            if node.name == "blockquote":
                if inner:
                    lines = inner.split('\n')
                    inner = '\n'.join([f"> {line}" if line.strip() else ">" for line in lines])
                    return inner + "\n\n"
                return ""
                
            if inner == "*":
                return "***\n\n"
            if inner:
                return inner + "\n\n"
            return ""

        if node.name in TAG_REPLACEMENTS:
            prefix = TAG_REPLACEMENTS[node.name]
            result_parts = [process_node(child) for child in node.children]
            inner = "".join(result_parts)
            
            if prefix.endswith(" ") or prefix.startswith("#"):
                if inner.strip():
                    return prefix + inner.strip() + "\n\n"
                return ""
            else:
                if not inner.strip():
                    return inner
                leading_spaces = len(inner) - len(inner.lstrip())
                trailing_spaces = len(inner) - len(inner.rstrip())
                left_space = inner[:leading_spaces] if leading_spaces else ""
                right_space = inner[len(inner)-trailing_spaces:] if trailing_spaces else ""
                clean_inner = inner.strip()
                return left_space + prefix + clean_inner + prefix + right_space

        if node.name == "a":
            result_parts = [process_node(child) for child in node.children]
            inner = "".join(result_parts).strip()
            href = node.get('href', '')
            if inner and href:
                return f"[{inner}]({href})"
            elif inner:
                return inner
            return ""

        result_parts = [process_node(child) for child in node.children]
        return "".join(result_parts)

    md = process_node(body)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = md.strip()
    return md

def minify_markdown(text: str) -> str:
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines)
