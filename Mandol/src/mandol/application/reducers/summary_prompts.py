"""LLM prompt templates for the SummaryMapReducer.

Defines prompt templates for four summary types: episodic, knowledge,
emotional, and procedural. Each prompt includes formatting placeholders
for context text and optional existing summary content.
"""

from __future__ import annotations

from typing import Any, Dict, List


# 情节性摘要（事件/时间线）的提示词
EPISODIC_SUMMARY_PROMPT = """你是一名专业的记忆组织专家。请将以下记录整理为带唯一 ID（UID）的情节性记忆摘要，抽取关键的时间、地点、人物、事件信息。
并识别形成该摘要的最核心记录 UID（最好 3-5 条，确有需要可适当增减）。

原始记录：
{records}

请按以下 JSON 格式返回情节性记忆摘要：
{{
    "reasoning": "对记录的简要分析以及该摘要如何形成",
    "key_source_uids": ["最核心的源记录 UID 列表"],
    "summary": {{
        "timeline": ["按时间顺序组织的关键时间点"],
        "key_people": ["涉及的重要人物及其角色"],
        "main_events": ["核心事件的简明描述"],
        "location_info": ["涉及的重要地点"],
        "event_relationships": ["事件之间的因果或关联关系"]
    }}
}}

摘要要求：
1. 保持事实准确性，不添加推测内容
2. 突出时间和空间的连续性
3. 体现人物之间的互动
4. 简洁明了，重点突出
5. 准确识别最重要的源 UID

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""


# 程序性摘要（步骤/流程）的提示词
PROCEDURAL_SUMMARY_PROMPT = """你是一名流程优化专家。请将以下记录整理为带唯一 ID（UID）的程序性记忆摘要，抽取最优执行路径、关键步骤、决策点。
并识别形成该摘要的最核心记录 UID（最好 3-5 条，确有需要可适当增减）。

原始记录：
{records}

请按以下 JSON 格式返回程序性记忆摘要：
{{
    "reasoning": "对记录的简要分析以及该摘要如何形成",
    "key_source_uids": ["最核心的源记录 UID 列表"],
    "summary": {{
        "process_name": ["流程/工作流的名称或标题"],
        "key_steps": ["流程中关键步骤的有序列表"],
        "decision_points": ["关键决策节点或分支条件"],
        "preconditions": ["开始前所需的前置条件"],
        "expected_outcomes": ["预期的结果或产出"],
        "optimization_opportunities": ["潜在的改进点或效率提升方向"]
    }}
}}

摘要要求：
1. 聚焦可操作、可重复的流程
2. 突出关键成功因素
3. 识别潜在的失败点或风险
4. 步骤顺序清晰无歧义
5. 准确识别最重要的源 UID

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""


# 知识性摘要（事实/概念）的提示词
KNOWLEDGE_SUMMARY_PROMPT = """你是一名知识组织专家。请将以下记录整理为带唯一 ID（UID）的知识性记忆摘要，抽取概念、原则、技术和事实信息。
并识别形成该摘要的最核心记录 UID（最好 3-5 条，确有需要可适当增减）。

原始记录：
{records}

请按以下 JSON 格式返回知识性记忆摘要：
{{
    "reasoning": "对记录的简要分析以及该摘要如何形成",
    "key_source_uids": ["最核心的源记录 UID 列表"],
    "summary": {{
        "core_concepts": ["解释的核心概念或原则"],
        "key_facts": ["重要的事实或数据点"],
        "techniques_methods": ["具体的技术、方法或途径"],
        "prerequisites_knowledge": ["理解所需的前置知识"],
        "related_concepts": ["用于进一步学习的相关概念"],
        "practical_applications": ["实际应用或用例"]
    }}
}}

摘要要求：
1. 事实准确，不加推测
2. 简明扼要抓住复杂信息的核心
3. 突出因果关系
4. 让具备基本背景知识的人能看懂
5. 准确识别最重要的源 UID

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""


# 情感性摘要的提示词
EMOTIONAL_SUMMARY_PROMPT = """你是一名用户体验分析专家。请将以下记录整理为带唯一 ID（UID）的情感性记忆摘要，抽取用户偏好、态度、情绪反应和行为模式。
并识别形成该摘要的最核心记录 UID（最好 3-5 条，确有需要可适当增减）。

原始记录：
{records}

请按以下 JSON 格式返回情感性记忆摘要：
{{
    "reasoning": "对记录的简要分析以及该摘要如何形成",
    "key_source_uids": ["最核心的源记录 UID 列表"],
    "summary": {{
        "user_preferences": ["明确表达或隐含的用户偏好和喜好"],
        "emotional_reactions": ["观察到的情绪反应与态度"],
        "behavioral_patterns": ["反复出现的行为模式或习惯"],
        "satisfaction_factors": ["带来满意或不满意的因素"],
        "frustration_points": ["痛点或挫折来源"],
        "underlying_values": ["推断出的底层价值观或优先级"]
    }}
}}

摘要要求：
1. 共情而不评判
2. 区分明确表达的偏好与推断出的模式
3. 同时捕捉积极和消极的情绪信号
4. 聚焦可操作的情感洞察
5. 准确识别最重要的源 UID

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""


SUMMARY_TYPE_DEFINITIONS = {
    "episodic": "情节性记忆记录具体的时间、地点、人物和事件 —— 即具体的经历和发生的事。",
    "procedural": "程序性记忆记录流程、工作流、方法以及分步操作 —— 即『如何做某事』。",
    "knowledge": "知识性记忆记录概念、事实、原则和技术信息 —— 即抽象层面的理解。",
    "emotional": "情感性记忆记录偏好、态度、感受和行为模式 —— 即情感与动机层面的内容。",
}


SUMMARY_PROMPTS: Dict[str, str] = {
    "episodic": EPISODIC_SUMMARY_PROMPT,
    "procedural": PROCEDURAL_SUMMARY_PROMPT,
    "knowledge": KNOWLEDGE_SUMMARY_PROMPT,
    "emotional": EMOTIONAL_SUMMARY_PROMPT,
}


def get_summary_prompt(category: str, records: List[Dict[str, Any]]) -> str:
    prompt_template = SUMMARY_PROMPTS.get(category, EPISODIC_SUMMARY_PROMPT)
    records_text = "\n\n".join(
        f"Record {i}(UID: {r.get('uid', 'unknown_uid')}):\n"
        f"Time: {r.get('metadata', {}).get('timestamp', 'Unknown time')}\n"
        f"Speaker: {r.get('metadata', {}).get('speaker', 'Unknown')}\n"
        f"Content: {r.get('text', r.get('content', ''))}"
        for i, r in enumerate(records, 1)
    )
    return prompt_template.format(records=records_text)


def get_summary_prompt_with_context(
    category: str, records: List[Dict[str, Any]], context: Dict[str, Any] = None
) -> str:
    prompt = get_summary_prompt(category, records)
    if context:
        context_str = f"\n\nAdditional context:\n{context.get('summary', '')}"
        prompt = prompt.replace("{context}", context_str)
    return prompt