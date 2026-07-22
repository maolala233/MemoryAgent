"""Document chunking strategies."""
from __future__ import annotations

import re
from typing import List, Optional


class Chunk:
    __slots__ = ("text", "section", "tokens", "index")

    def __init__(self, text: str, section: str, tokens: int, index: int) -> None:
        self.text = text
        self.section = section
        self.tokens = tokens
        self.index = index

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "section": self.section,
            "tokens": self.tokens,
            "index": self.index,
        }


def _estimate_tokens(text: str) -> int:
    # 中英文混合估算: 中文按 0.6 token/字, 英文按 0.3 token/字
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return max(1, int(chinese * 0.6 + other * 0.3))


# 归一化: 删除 CJK 之间的多余空格
# 源文档(PDF/Word 提取)经常出现 "维护近 三年的财务报表" 这种空格,
# 会导致 FTS5 把 "维护" "近" 切成单字,无法 phrase 匹配
_CJK = r"\u4e00-\u9fff"
_CJK_RUN = re.compile(rf"([{_CJK}])\s+([{_CJK}])")
_MULTI_SPACE = re.compile(r"[ \t]+")


def normalize_cjk(text: str) -> str:
    """归一化 CJK 文本: 合并 CJK 之间的多余空格,但保留必要的标点间距。"""
    if not text:
        return text
    # 1) 合并 CJK 之间的连续空格(保留 1 个用于英文/数字边界)
    text = _CJK_RUN.sub(r"\1\2", text)
    # 2) 折叠多个普通空格为单空格(用于英文/数字 token 间)
    text = _MULTI_SPACE.sub(" ", text)
    return text


# 标题识别正则(支持 markdown 标题 + Word 导出的加粗标题)
_BOLD_HEADING_RE = re.compile(r"^\s*(\*{1,3})(.+?)\1\s*$")


class ChunkingService:
    def chunk_by_section(self, text: str, headings: Optional[List[str]] = None) -> List[Chunk]:
        sections = self._split_by_headings(text)
        chunks: List[Chunk] = []
        idx = 0
        for section_title, body in sections:
            if not body.strip():
                continue
            chunks.append(Chunk(body, section_title, _estimate_tokens(body), idx))
            idx += 1
        return chunks

    def chunk_by_size(self, text: str, max_tokens: int = 250, overlap: int = 40) -> List[Chunk]:
        """按 token 数切分,中英文混合估算更准确。

        优先按句子边界(。！？!?；;\\n)切,无法识别句子边界时按硬长度切。
        """
        if not text or not text.strip():
            return []
        # 句子切分(中英文)
        sentence_sep = re.compile(r"([。！？!?；;]|\n{2,})")
        parts = sentence_sep.split(text)
        sentences: List[str] = []
        for i in range(0, len(parts), 2):
            s = (parts[i] or "").strip()
            tail = parts[i + 1] if i + 1 < len(parts) else ""
            if s:
                sentences.append(s + tail)
        if not sentences:
            sentences = [text]

        chunks: List[Chunk] = []
        idx = 0
        cur_texts: List[str] = []
        cur_tokens = 0
        for sent in sentences:
            st = _estimate_tokens(sent)
            # 单句就超过 max_tokens: 单独成块,或按字符硬切
            if st > max_tokens:
                # 先把现有 cur 提交
                if cur_texts:
                    chunk_text = "".join(cur_texts).strip()
                    if chunk_text:
                        chunks.append(Chunk(chunk_text, "Body", _estimate_tokens(chunk_text), idx))
                        idx += 1
                    cur_texts = []
                    cur_tokens = 0
                # 硬切长句
                start = 0
                while start < len(sent):
                    # 按 max_tokens 估算的字符数
                    char_budget = int(max_tokens / 0.6) if any('\u4e00' <= c <= '\u9fff' for c in sent) else int(max_tokens / 0.3)
                    end = min(start + char_budget, len(sent))
                    piece = sent[start:end]
                    chunks.append(Chunk(piece, "Body", _estimate_tokens(piece), idx))
                    idx += 1
                    if end >= len(sent):
                        break
                    start = end - int(overlap * 0.6)
                continue
            if cur_tokens + st > max_tokens and cur_texts:
                chunk_text = "".join(cur_texts).strip()
                if chunk_text:
                    chunks.append(Chunk(chunk_text, "Body", _estimate_tokens(chunk_text), idx))
                    idx += 1
                # 重叠: 保留尾部若干句
                if overlap > 0 and cur_texts:
                    tail_texts: List[str] = []
                    tail_tokens = 0
                    for prev in reversed(cur_texts):
                        pt = _estimate_tokens(prev)
                        if tail_tokens + pt > overlap:
                            break
                        tail_texts.insert(0, prev)
                        tail_tokens += pt
                    cur_texts = tail_texts
                    cur_tokens = tail_tokens
                else:
                    cur_texts = []
                    cur_tokens = 0
            cur_texts.append(sent)
            cur_tokens += st
        if cur_texts:
            chunk_text = "".join(cur_texts).strip()
            if chunk_text:
                chunks.append(Chunk(chunk_text, "Body", _estimate_tokens(chunk_text), idx))
                idx += 1
        return chunks

    def chunk_document(self, text: str, max_tokens: int = 250,
                       overlap: int = 40) -> List[Chunk]:
        """Section-aware chunking that falls back to size-based for big sections.

        改进点:
        1. 默认 max_tokens 从 400 降到 250,避免单 chunk 太大丢失细节
        2. 支持识别 **加粗** 形式的标题(Word/PDF 导出的 markdown 经常用)
        3. 支持 (一)/(1)/第N章 等中文编号标题
        4. 大段无法识别的内容按字符硬切
        5. 入参归一化: 删除 CJK 之间的多余空格,避免 FTS 切碎短语
        """
        # 关键: 先归一化源文本(去 CJK 间空格),否则 chunk 内的 CJK 短语会被切散
        text = normalize_cjk(text)
        sections = self._split_by_headings(text)
        chunks: List[Chunk] = []
        idx = 0
        for section_title, body in sections:
            if not body.strip():
                continue
            tokens = _estimate_tokens(body)
            if tokens <= max_tokens * 1.2:
                chunks.append(Chunk(body, section_title, tokens, idx))
                idx += 1
            else:
                for sub in self.chunk_by_size(body, max_tokens=max_tokens, overlap=overlap):
                    sub.index = idx
                    sub.section = section_title
                    chunks.append(sub)
                    idx += 1
        if not chunks:
            chunks = self.chunk_by_size(text, max_tokens=max_tokens, overlap=overlap)
        return self._merge_short_chunks(chunks, min_tokens=40)

    def _merge_short_chunks(self, chunks: List[Chunk], min_tokens: int = 40) -> List[Chunk]:
        merged: List[Chunk] = []
        for c in chunks:
            if merged and c.tokens < min_tokens:
                prev = merged[-1]
                prev.text = prev.text + "\n\n" + c.text
                prev.tokens = _estimate_tokens(prev.text)
            else:
                merged.append(Chunk(c.text, c.section, c.tokens, len(merged)))
        for i, c in enumerate(merged):
            c.index = i
        return merged

    @staticmethod
    def _split_by_headings(text: str) -> List[tuple]:
        """切分章节。

        支持以下标题形式:
        1. 标准 markdown 标题: # / ## / ### ...
        2. **加粗行**(Word/PDF 导出常用): **（一）产品参数配置** / **1. xxx**
        3. 中文编号标题: 第N章 / （一） / (1) / 1.

        关键修复 (标题继承):
        - 标题行被识别后, 立即作为新 section body 的首行(同时保留为 section.title),
          保证 chunk 的正文里**能看到**自己的标题, 不丢失上下文
        - 第一个未识别的 preamble(前言/目录)仍归入 "Introduction" 段
        """
        sections: List[tuple] = []
        current_title = "Introduction"
        buffer: List[str] = []

        def _is_bold_heading(line: str) -> Optional[str]:
            """判断一行是否是"加粗标题",返回清洗后的标题;否则返回 None。"""
            stripped = line.strip()
            if not stripped:
                return None
            # 1) 标准 markdown
            m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
            if m:
                return re.sub(r"\s+", " ", m.group(2)).strip()
            # 2) **加粗** 整行
            m2 = _BOLD_HEADING_RE.match(stripped)
            if m2 and len(m2.group(2).strip()) <= 60:
                content = m2.group(2).strip()
                # 只接受看起来像标题的: 不能包含句号,不能太长
                if "。" not in content and ";" not in content and ";" not in content and "?" not in content and "?" not in content:
                    return content
            # 3) 中文章节标题(docx 转换后无 markdown 符号)
            #    第一章 / 第二章 / 第N章 / 第十一章 等
            if re.match(r"^第[一二三四五六七八九十百零〇0-9]+章[　\s　]?", stripped) and len(stripped) <= 60:
                return stripped
            # 4) 中文括号编号: （一）/（1）/（十一）/（1.1） + 短标题
            m3 = re.match(r"^（[一二三四五六七八九十0-9]+(?:[.．][0-9]+)?）\s*(.{0,40})$", stripped)
            if m3 and len(stripped) <= 80 and "\n" not in m3.group(0):
                return stripped
            # 5) 英文括号编号: (1) / (1.1) / (1.1.1)
            m4 = re.match(r"^\([0-9]+(?:[.．][0-9]+){0,3}\)\s*(.{0,40})$", stripped)
            if m4 and len(stripped) <= 80:
                return stripped
            # 6) 阿拉伯数字编号: 1. / 2.1. / 3.1.1. (必须以点结尾, 后面跟短标题)
            m5 = re.match(r"^([0-9]{1,2}(?:[.．][0-9]{1,2}){0,3})[.．]?\s*([^\n]{0,30})$", stripped)
            if m5 and len(stripped) <= 80 and not m5.group(0)[-1].isdigit():
                return stripped
            # 7) 顿号/中文列表: 一、/ 二、/ 十一、
            m6 = re.match(r"^[一二三四五六七八九十]+、\s*(.{0,30})$", stripped)
            if m6 and len(stripped) <= 60:
                return stripped
            return None

        for line in text.splitlines():
            heading = _is_bold_heading(line)
            if heading:
                if buffer:
                    sections.append((current_title, "\n".join(buffer).strip()))
                    buffer = []
                current_title = heading
                # 标题继承修复: 把标题行作为新 section body 的首行,
                # 保证 chunk 正文里能看到自己的标题 (LLM 召回后不会丢上下文)
                buffer = [line.rstrip()]
            else:
                buffer.append(line)
        if buffer:
            sections.append((current_title, "\n".join(buffer).strip()))
        if not sections:
            sections = [("Document", text)]
        # 兜底: 校验每个 chunk 的 body 是否包含自己的 title (允许 title 出现在首行/任意位置)
        # 跳过 "Introduction" / "Document" 这种无明确标题的占位段
        fixed: List[tuple] = []
        for title, body in sections:
            if title not in ("Introduction", "Document") and title and title not in body:
                # 仍然修复: 在 body 开头显式补一行标题, 哪怕正文里没有, 也确保 LLM 检索时能看到
                body = f"【{title}】\n" + body
            fixed.append((title, body))
        return fixed


chunking_service = ChunkingService()
