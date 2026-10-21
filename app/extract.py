import os
import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "meta", "link"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "meta", "link") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            t = data.strip()
            if t:
                self.parts.append(t)


def _extract_notes(directory):
    """尽力从 Axure 生成的 annotations / notes 相关 JS 中提取批注文本。"""
    out = []
    for root, _, files in os.walk(directory):
        for f in files:
            if not f.lower().endswith(".js"):
                continue
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                continue
            if "annotation" not in content.lower():
                continue
            for m in re.findall(r'"([^"\\]{2,200})"', content):
                low = m.lower()
                if ("annotation" in low or "需求" in m or "说明" in m
                        or "note" in low or "批注" in m):
                    out.append(m)
    # 去重保序
    seen = set()
    result = []
    for x in out:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return "\n".join(result)


def extract_text(directory, max_chars=60000):
    """从 Axure 生成的原型目录中提取全部可读文字（页面名+可见文字+批注）。"""
    texts = []
    html_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".html"):
                html_files.append(os.path.join(root, f))

    for hf in html_files:
        try:
            with open(hf, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            continue
        parser = _TextExtractor()
        try:
            parser.feed(content)
        except Exception:
            pass
        rel = os.path.relpath(hf, directory)
        body = "\n".join(parser.parts)
        if body.strip():
            texts.append(f"[页面 {rel}]\n{body}")

    notes = _extract_notes(directory)
    if notes.strip():
        texts.append("[Axure 批注/需求]\n" + notes)

    full = "\n\n".join(texts)
    return full[:max_chars]
