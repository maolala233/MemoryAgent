"""Prompt 4: Event-event causal relation extraction."""

# LLM prompt for extracting causal relationships between event pairs.
# Inputs: dialogue text and extracted events with their UIDs.
# Output: JSON with causal_relations list (cause_event, effect_event, type, confidence).
#
# 本提示为通用中文版：抽取因果关系时支持中英文因果连接词（因为、由于、导致、引起、促使、从而、因此、因为…所以…、由于…因此…、if…then…）。

EVENT_CAUSAL_PROMPT = """你是一名资深知识图谱工程师，专长于事件间因果关系抽取。

### 背景
**当前会话文本**:
{dialogue_context}

**当前会话事件**:
{current_events}

### 任务

抽取事件间的因果关系：
- A **导致** B：事件 A 直接引起事件 B
- 考虑时序：因在前、果在后
- 留意中英文因果连接词：
  - 中文：因为、由于、导致、引起、促使、从而、因此、所以、使得、造成、引发、故、于是
  - 英文：because、due to、led to、resulted in、caused、hence、therefore、so、consequently

### 少量示例

**示例 1：显式因果**
文本: "暴雨导致该地区发生了严重的洪涝。"
当前事件: [{{"id": "event:heavy_rain", "name": "暴雨"}}, {{"id": "event:flooding", "name": "洪涝"}}]
输出:
{{
    "causal_relations": [
        {{
            "cause_event": "event:heavy_rain",
            "effect_event": "event:flooding",
            "confidence": 0.95,
            "reasoning": "文本明确说暴雨导致洪涝"
        }}
    ]
}}

**示例 2：隐式因果**
文本: "小李错过了截止日期。他不得不加班赶进度。"
当前事件: [{{"id": "event:missed_deadline", "name": "错过截止日期"}}, {{"id": "event:work_overtime", "name": "加班赶进度"}}]
输出:
{{
    "causal_relations": [
        {{
            "cause_event": "event:missed_deadline",
            "effect_event": "event:work_overtime",
            "confidence": 0.85,
            "reasoning": "错过截止日期导致小李不得不加班"
        }}
    ]
}}

**示例 3：因果链**
文本: "由于访问量激增，服务器宕机。这导致网站无法访问，进而用户无法登录账号。"
当前事件: [{{"id": "event:server_crash", "name": "服务器宕机"}}, {{"id": "event:website_down", "name": "网站无法访问"}}, {{"id": "event:login_failure", "name": "用户无法登录"}}]
输出:
{{
    "causal_relations": [
        {{
            "cause_event": "event:server_crash",
            "effect_event": "event:website_down",
            "confidence": 0.95,
            "reasoning": "服务器宕机导致网站无法访问"
        }},
        {{
            "cause_event": "event:website_down",
            "effect_event": "event:login_failure",
            "confidence": 0.90,
            "reasoning": "网站无法访问导致用户无法登录"
        }}
    ]
}}

**示例 4：无因果关系**
文本: "小李去商店买东西。小王在看书。"
当前事件: [{{"id": "event:store_visit", "name": "去商店"}}, {{"id": "event:reading", "name": "看书"}}]
输出:
{{
    "causal_relations": []
}}

### 输出格式（仅 JSON）
{{
    "causal_relations": [
        {{
            "cause_event": "event:cause_id",
            "effect_event": "event:effect_id",
            "confidence": 0.85,
            "reasoning": "因果关系存在的原因"
        }}
    ]
}}
"""
