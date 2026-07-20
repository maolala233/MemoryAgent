"""通用化回答风格层（与业务解耦，可被任意 RAG 场景复用）。

设计原则
--------
1. 业务无关：模块不出现任何业务关键词（如"银行业务手册"），可被任意领域
   的问答场景直接复用。
2. 风格与角色分离：role 模板（人设/称谓）由调用方注入，style preset
   只负责语气、结构、引用规范、缺口声明。
3. 字符串模板 + 占位符：所有 prompt 片段均为纯文本，通过 {var} 占位符
   在运行时填充，避免硬编码业务术语。
4. 三层组装：上游 chat 路由负责把 [role] + [style] + [retrieval_constraints]
   拼成最终的 system prompt。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 风格预设（场景无关）
# ---------------------------------------------------------------------------

STYLE_PRESETS: Dict[str, "StylePreset"] = {}


@dataclass(frozen=True)
class StylePreset:
    """一份完整的"风格档位"。

    Attributes:
        name: 档位 ID。
        description: 给前端/调用方看的简短说明。
        tone: 语气描述（专业顾问 / 极简 / 亲和等）。
        structure: 答案的整体结构指令（先结论 / 先分点 / 段落叙述等）。
        citation_rule: 引用规范（末尾 [N] / 内联 [N] 等）。
        gap_declaration: 信息缺口的声明方式（要求直说"未覆盖"）。
        length_hint: 长度倾向（详尽 / 简练 / 极简）。
        avoid_phrases: 应避免的句式（用于反例，避免模型套话）。
        no_meta_phrases: 禁止使用"系统视角"元话语。
    """

    name: str
    description: str
    tone: str
    structure: str
    citation_rule: str
    gap_declaration: str
    length_hint: str
    avoid_phrases: List[str]
    no_meta_phrases: List[str]

    def render(self) -> str:
        """渲染为可注入 system prompt 的纯文本片段（不含角色/业务约束）。"""
        lines: List[str] = [
            f"## 回答风格（{self.name}）",
            f"- 语气：{self.tone}",
            f"- 结构：{self.structure}",
            f"- 长度：{self.length_hint}",
            f"- 引用：{self.citation_rule}",
            f"- 信息缺口处理：{self.gap_declaration}",
            "",
            "## 必须遵守的硬规则",
            "1) 禁止使用以下系统视角元话语（不要出现这些句式）：",
            *[f"   - 禁止：{p}" for p in self.no_meta_phrases],
            "2) 禁止使用以下套话或模糊措辞：",
            *[f"   - 禁止：{p}" for p in self.avoid_phrases],
            "3) 答案必须以 '【回答】' 开头（用于和模型内部推理分离）。",
        ]
        return "\n".join(lines)


# ---- 注册档位 ----
STYLE_PRESETS["balanced"] = StylePreset(
    name="balanced",
    description="均衡：先结论后分点，引用规范，通用场景默认档位。",
    tone="专业、清晰、像一位资深的业务顾问在回答同事的问题。",
    structure=(
        "先给出一句话直接结论（让用户立刻知道答案方向），"
        "再按要点分点展开（使用 1)/2)/3) 或 -），"
        "如果是操作类问题，最后给出'操作路径'或'下一步动作'。"
    ),
    citation_rule=(
        "在引用原文时使用内联编号 [N] 标记，N 对应下方记忆片段编号；"
        "如果同一要点引用了多条记忆，多个编号并列 [1][3]。"
    ),
    gap_declaration=(
        "如果召回片段只覆盖了问题的部分要点，必须在答案末尾单独一段"
        "显式声明'未覆盖的部分'（例如：\"以上回答未涉及 X 部分，"
        "建议补充查询 Y 路径或咨询 Z 渠道\"），禁止用'记忆库中暂未收录'"
        "这类系统视角表述敷衍。"
    ),
    length_hint="详尽但不啰嗦——回答应覆盖问题涉及的所有召回要点，"
                "但不要把同一段原文重复引用。",
    avoid_phrases=[
        "通常情况下",
        "一般情况下",
        "一般而言",
        "您可以尝试",
        "建议您",
        "需要说明的是",
    ],
    no_meta_phrases=[
        "记忆库收录了相关信息",
        "记忆库中暂未收录该信息",
        "根据记忆内容",
        "根据检索到的记忆",
        "根据相关文档",
    ],
)

STYLE_PRESETS["concise"] = StylePreset(
    name="concise",
    description="极简：一句话结论 + 必要要点，适合短问短答。",
    tone="简练直白，像在 IM 里和同事快速对答。",
    structure="先一句话直接结论；如有多要点，用 1) 2) 3) 列出；不展开。",
    citation_rule="内联 [N] 编号引用。",
    gap_declaration="信息缺口用'未覆盖 X'一句带过。",
    length_hint="极简，总长不超过召回片段的关键句总和。",
    avoid_phrases=[
        "通常情况下",
        "您可以尝试",
        "需要说明的是",
    ],
    no_meta_phrases=[
        "记忆库收录了相关信息",
        "记忆库中暂未收录该信息",
    ],
)

STYLE_PRESETS["formal"] = StylePreset(
    name="formal",
    description="正式：完整规范文档式表达，适合对外/合规场景。",
    tone="严谨规范，避免口语化措辞，使用完整句式。",
    structure=(
        "先'结论/结论摘要'段落，再'详细说明'分点展开，"
        "如适用，最后给'操作路径/适用条件'段落。"
    ),
    citation_rule="内联 [N] 引用，末尾再列一次引用清单（标题 + 编号）。",
    gap_declaration=(
        "信息缺口段落必须列出『未覆盖要点』和『建议补充查询的渠道或路径』。"
    ),
    length_hint="详尽，优先覆盖所有召回要点。",
    avoid_phrases=[
        "大概",
        "可能",
        "或许",
        "您可以试试",
    ],
    no_meta_phrases=[
        "记忆库收录了相关信息",
        "记忆库中暂未收录该信息",
    ],
)

STYLE_PRESETS["friendly"] = StylePreset(
    name="friendly",
    description="亲和：客服/同事口吻，适合对客咨询。",
    tone="亲和、耐心、像一位有经验的同事在帮你排查问题。",
    structure=(
        "先回应用户的疑问/困惑，"
        "再给出答案分点，最后给'建议下一步'。"
    ),
    citation_rule="内联 [N] 引用。",
    gap_declaration=(
        "用'这块我目前没找到 X 的明确说明，建议你……'的句式表达缺口。"
    ),
    length_hint="详尽，但用对话口吻。",
    avoid_phrases=[
        "通常情况下",
        "您可以尝试",
    ],
    no_meta_phrases=[
        "记忆库收录了相关信息",
        "记忆库中暂未收录该信息",
    ],
)

STYLE_PRESETS["technical"] = StylePreset(
    name="technical",
    description="技术：API/错误码/路径优先，适合 IT 排查。",
    tone="技术性、精确，优先给出错误码、字段、API、路径。",
    structure=(
        "先列错误码/字段/接口；"
        "再给触发条件；"
        "再给排查/解决步骤。"
    ),
    citation_rule="内联 [N] 引用。",
    gap_declaration="明确指出未覆盖的错误码/字段，给出建议的查询路径。",
    length_hint="中等，优先精确。",
    avoid_phrases=[
        "通常",
        "可能",
    ],
    no_meta_phrases=[
        "记忆库收录了相关信息",
        "记忆库中暂未收录该信息",
    ],
)


def get_style_preset(name: Optional[str]) -> StylePreset:
    """按名称取风格档位，找不到则返回 balanced。"""
    if not name:
        return STYLE_PRESETS["balanced"]
    return STYLE_PRESETS.get(str(name).lower(), STYLE_PRESETS["balanced"])


# ---------------------------------------------------------------------------
# 角色模板（人设/称谓）
# ---------------------------------------------------------------------------

# 默认角色：当用户/profile 未指定时使用。
DEFAULT_ROLE = "你是一位严谨、专业、耐心的问答助手。你的所有回答都必须严格基于下方『记忆』中提供的内容，严禁使用训练数据中的通用知识来回答业务问题。"

# 检索约束片段：与角色、风格解耦，可独立复用。
# 仅描述"如何基于记忆回答"的硬规则，**不**包含任何风格/语气/人设信息。

RECALL_GUIDE = """下方"记忆"区由若干带编号的检索片段组成（[1] / [2] / ...）。
- 引用时使用内联编号（例：根据规则[2]）。
- 多个引用并列时用 [1][3] 这种格式。
- 答案中**只引用真实存在于下方"记忆"区的内容**，禁止编造 [N] 编号。"""

RETRIEVAL_CONSTRAINTS = """## 检索约束（硬规则）
1) 你的所有回答必须严格基于下方"记忆"中提供的内容，严禁使用训练数据中的通用知识来回答业务问题（如利率、流程、错误码、操作路径、字段含义等）。
2) 召回片段中可能存在多条相关记录，必须**逐一阅读**每一条（包括"要点提示""页面字段说明""操作步骤"等细节），找出与用户问题**最直接对应**的描述；不要只看记忆标题就推断。
3) 召回片段以 [N] 编号引用，引用时使用内联 [N] 标记（如 "...规则[1]"）。
4) 召回片段之间允许交叉引用、合并信息，但**不得**编造未在记忆中出现的事实。
5) 如果记忆中存在并列要点（如 A/B/C/D、场景 1/2/3、第一步/第二步），必须**逐一覆盖**，不得遗漏。
6) 如果用户问题涉及"是否/能否/多少/哪个"等明确判断或数值问题，且记忆中**没有直接答案**，必须**直说**"记忆库未提供 X 的具体答案，建议……"，禁止用通用知识兜底。
7) 如果记忆与用户问题部分相关，仍应尽量作答——摘出与问题关键词（错误码、产品名、操作路径、字段名等）重合的内容，**并明确指出哪些部分可能不直接对应**。
8) 只有当所有召回片段**与问题完全无关**时，才回复"未找到与本问题相关的记忆，建议咨询业务部门"。
9) 如果用户问题包含多个子问题（如"是什么 + 怎么办 + 注意事项"），必须分点逐一回答，**禁止合并省略**。
10) 答案必须以 '【回答】' 开头（用于与上游推理内容分离）。
11) 涉及操作路径时，保留完整的菜单层级（如"对公线上融资平台 → 信贷工厂 → 通用业务管理 → 产品开通"），**不要压缩**。
12) 涉及错误码/字段名时，必须**原样输出**（如 "ETPD279"、"DPRB365"），不要重命名。
13) 如果用户问"如何"做某事，答案中应包含**可执行步骤**（路径 + 按钮 + 后续动作），而不是停留在概念解释。
"""


# ---------------------------------------------------------------------------
# 检索自检指令（让模型在生成答案前自检）
# ---------------------------------------------------------------------------

SELF_CHECK_INSTRUCTION = """## 生成前自检（必读）
在写出最终答案前，先在内部对照以下问题自检：
- a) 我是否**逐条阅读了所有召回片段**，而不是只看了标题？
- b) 用户问题涉及的**并列要点**（A/B/C、场景1/2/3、第一步/第二步等）是否**全部覆盖**？如未全覆盖，是否在答案中明确告知用户"完整有 N 条，本次回答覆盖 M 条"？
- c) 涉及"是否/能否/多少"等明确判断/数值问题时，记忆中是否真有答案？如无，是否直说"未提供"而不是用通用知识？
- d) 操作路径是否完整保留菜单层级？错误码/字段名是否原样输出？
- e) 是否使用了任何禁止的系统元话语或套话？如有，删除重写。
完成自检后再输出答案。"""


# ---------------------------------------------------------------------------
# 组装入口
# ---------------------------------------------------------------------------

def assemble_system_prompt(
    role_text: Optional[str] = None,
    style_preset_name: Optional[str] = None,
    extra_constraints: Optional[str] = None,
) -> str:
    """组装最终的 system prompt（[role] + [style] + [retrieval_constraints] + [self_check] + [extra]）。

    Args:
        role_text: 角色人设/称谓（场景相关），可由调用方注入；为 None 时使用默认。
        style_preset_name: 风格档位名称（balanced/concise/formal/friendly/technical）。
        extra_constraints: 额外约束（场景相关），拼在末尾。

    Returns:
        完整的 system prompt 字符串。
    """
    preset = get_style_preset(style_preset_name)
    role = (role_text or DEFAULT_ROLE).strip()

    parts: List[str] = [role, "", preset.render(), "", RETRIEVAL_CONSTRAINTS, "", SELF_CHECK_INSTRUCTION]
    if extra_constraints and extra_constraints.strip():
        parts.extend(["", "## 场景补充约束", extra_constraints.strip()])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 列表/分支问题检测
# ---------------------------------------------------------------------------

_LIST_TYPE_HINTS = (
    "哪些", "步骤", "流程", "场景", "类型", "情况", "分别", "列举", "包括",
    "什么", "原因", "条件", "规则", "方式",
)


def detect_query_shape(query: str) -> Dict[str, Any]:
    """识别问题形态（用于检索策略选择）。

    Returns:
        dict 包含:
          - is_list_like: 是否为列表/枚举型问题
          - is_numeric: 是否为数值/比例型问题
          - is_path_like: 是否为操作路径型问题
          - is_error_code: 是否包含错误码
          - hints: 命中的形态标签列表
    """
    q = (query or "").strip()
    hints: List[str] = []
    is_list_like = any(k in q for k in _LIST_TYPE_HINTS)
    is_numeric = any(k in q for k in ("多少", "几", "多长", "多大", "比例", "利率", "年利率", "百分比"))
    is_path_like = any(k in q for k in ("怎么", "如何", "在哪", "路径", "登录", "进入", "操作"))
    is_error_code = False
    import re

    code_patterns = [
        re.compile(r"\b[A-Z]{2,6}\d{3,5}\b"),  # ETPD279 / DPRB365
        re.compile(r"[\u4e00-\u9fff]*码[:：]"),
    ]
    for p in code_patterns:
        if p.search(q):
            is_error_code = True
            break
    if is_list_like:
        hints.append("list")
    if is_numeric:
        hints.append("numeric")
    if is_path_like:
        hints.append("path")
    if is_error_code:
        hints.append("error_code")
    return {
        "is_list_like": is_list_like,
        "is_numeric": is_numeric,
        "is_path_like": is_path_like,
        "is_error_code": is_error_code,
        "hints": hints,
    }


def recommend_retrieval_overrides(
    query: str,
    base_top_k: int = 15,
    base_budget: int = 4000,
) -> Dict[str, Any]:
    """根据问题形态给出检索参数微调建议。

    列表型/分支型问题 → 加大 top_k 和 context budget，确保并列要点全部召回。
    """
    shape = detect_query_shape(query)
    top_k = base_top_k
    budget = base_budget
    per_chunk_chars = 1800
    if shape["is_list_like"]:
        # 列表/分支型：放大召回，避免截断
        top_k = max(top_k, 25)
        budget = max(budget, 7000)
        per_chunk_chars = 2400
    if shape["is_error_code"]:
        # 错误码：精确匹配优先
        top_k = max(top_k, 20)
    return {
        "top_k": top_k,
        "context_token_budget": budget,
        "per_chunk_chars": per_chunk_chars,
        "shape": shape,
    }
