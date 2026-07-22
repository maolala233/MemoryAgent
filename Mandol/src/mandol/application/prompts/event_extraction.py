"""Prompt 2: Event extraction with coreference resolution."""

# LLM prompt for extracting events from dialogue with coreference linking.
# Inputs: dialogue text and list of existing candidate events.
# Output: JSON with extracted events, each having name, description, linked_id, etc.
#
# 本提示为通用中文版：不引入任何业务专有概念。location 字段对抽象/流程性事件允许为 null。

# 通用语言学提示：跨领域通用的语言现象提示，不引入任何业务专有概念。
LINGUISTIC_HINTS = """**步骤 0：通用语言学现象（适用于任何领域，非业务专用）**
抽取事件时，请同时留意下列**通用语言现象**，并将它们记入 `new_facts`：
- **缩写、别名、简称**：例如"CRMX"、"网厅"等在文本中首次出现时，建立全称→缩写的别名关系
- **时间表达式**：例如"有效期一年"、"最长 12 个月"、"每周一上午"等时间约束
- **否定与前提**：例如"前提是…"、"只有…才…"、"若不…则…"等条件性表述
- **枚举项**：例如"A. … B. … C. …"或"1）… 2）…"等并列结构，记录为多条独立 `new_facts`
- **路径式步骤**：例如"A → B → C"或"页面A-页面B-按钮C"等层级化操作
- **数值与单位**：例如"利率 3.85%"、"金额 100 万元"等，保留数值与单位"""

# 模板字符串（模块加载时通过 str.replace 注入 LINGUISTIC_HINTS，避免破坏 JSON {{}} 转义）
_EVENT_EXTRACTION_TEMPLATE = """你是一名资深知识图谱工程师，专长于事件抽取与指代消解。

### 背景
**当前会话文本**:
{dialogue_context}

**已存在的规范事件**（top-5 最相关）:
{existing_events}

**当前会话实体**:
{current_entities}

### 任务

**步骤 1：事件抽取**
抽取事件及其与实体的关系：
- `event_name`：规范事件名称（与原文语言保持一致）
- `description`：事件简要描述
- `participants`：参与事件的实体引用列表（使用 current_entities 中的 linked_id）
- `location`：事件发生的地点（取 current_entities 中某实体的名称）。对抽象/流程性事件（如"合同签订"、"贷款审批"），没有物理地点时**必须设为 null**，不要编造
- `inferred_time`：ISO 8601 时间或相对时间表达

**步骤 2：指代消解**
对事件指代（例如"这次会议"、"那个项目"、"它"指代某事件）做指代消解：
- 若指代一个已存在的事件：将 `linked_id` 设为该事件的 id
- 若指代一个新的事件：将 `is_new` 设为 true

**步骤 3：参与者链接**
对每个参与者：
- 若能在 current_entities 中找到匹配，使用对应的 `linked_id`
- `role` 描述该实体在事件中的角色（如"主体"、"对象"、"受益方"等通用角色，不要使用业务专有词）

**重要约束**：
- `location` 必须是纯字符串（current_entities 中的实体名）或 null，绝不能是对象/字典
- 对抽象事件或流程性事件，location 应为 null，不要为了填字段而编造地点
- `participants` 各项必须使用 current_entities 中的 `linked_id`

{LINGUISTIC_HINTS}

### 少量示例

**示例 1：基础事件抽取**
文本: "小李的家乡去年发生了严重的洪灾"
已存在事件: []
当前实体: [{{"id": "entity:xiaoli", "name": "小李", "type": "Person"}}, {{"id": "entity:xiaoli_hometown", "name": "小李的家乡", "type": "Place"}}]
输出:
{{
    "events": [
        {{
            "reasoning": "描述了影响小李家乡的洪灾事件",
            "event_name": "洪灾",
            "linked_id": null,
            "is_new": true,
            "confidence": 0.95,
            "description": "一场严重的洪灾袭击了小李的家乡",
            "participants": [
                {{"mention": "小李", "linked_id": "entity:xiaoli", "role": "受影响者"}}
            ],
            "location": "小李的家乡",
            "inferred_time": "去年",
            "new_facts": ["影响小李的家乡"]
        }}
    ]
}}

**示例 2：带时间的事件**
文本: "小王上周五参加了学术会议。她在会上展示了研究成果。"
已存在事件: []
当前实体: [{{"id": "entity:xiaowang", "name": "小王", "type": "Person"}}, {{"id": "entity:conference", "name": "学术会议", "type": "Activity"}}]
输出:
{{
    "events": [
        {{
            "reasoning": "小王参加学术会议并展示研究成果",
            "event_name": "参加学术会议",
            "linked_id": null,
            "is_new": true,
            "confidence": 0.90,
            "description": "小王上周五参加了学术会议，并在会上展示了研究成果",
            "participants": [
                {{"mention": "小王", "linked_id": "entity:xiaowang", "role": "参与者"}}
            ],
            "location": "学术会议",
            "inferred_time": "上周五",
            "new_facts": ["小王展示了研究成果"]
        }}
    ]
}}

**示例 3：抽象/流程性事件（location 必须为 null）**
文本: "客户经理完成了贷款审批流程。"
已存在事件: []
当前实体: [{{"id": "entity:manager", "name": "客户经理", "type": "Person"}}]
输出:
{{
    "events": [
        {{
            "reasoning": "这是流程性事件，没有物理地点",
            "event_name": "贷款审批",
            "linked_id": null,
            "is_new": true,
            "confidence": 0.90,
            "description": "客户经理完成了贷款审批流程",
            "participants": [
                {{"mention": "客户经理", "linked_id": "entity:manager", "role": "执行者"}}
            ],
            "location": null,
            "inferred_time": null,
            "new_facts": []
        }}
    ]
}}

**示例 4：事件指代消解**
文本: "会议被推迟了。它将在下周举行。"
已存在事件: [{{"id": "event:meeting_2024", "name": "会议", "description": "一次会议"}}]
当前实体: []
输出:
{{
    "events": [
        {{
            "reasoning": "'会议'和'它'都指代已存在的会议事件",
            "event_name": "会议",
            "linked_id": "event:meeting_2024",
            "is_new": false,
            "confidence": 0.90,
            "description": "会议被推迟到下周",
            "participants": [],
            "location": null,
            "inferred_time": "下周",
            "new_facts": ["被推迟", "将在下周举行"]
        }}
    ]
}}

### 输出格式（仅 JSON）
{{
    "events": [
        {{
            "reasoning": "抽取该事件的理由与指代消解决策",
            "event_name": "规范事件名称（与原文语言保持一致）",
            "linked_id": "event_id 或 null",
            "is_new": true,
            "confidence": 0.9,
            "description": "事件描述",
            "participants": [
                {{"mention": "小李", "linked_id": "entity:xiaoli", "role": "受影响者"}}
            ],
            "location": "地点实体名 或 null",
            "inferred_time": "2024-01-15 或 null",
            "new_facts": []
        }}
    ]
}}
"""

# 模块加载时注入 LINGUISTIC_HINTS
EVENT_EXTRACTION_PROMPT = _EVENT_EXTRACTION_TEMPLATE.replace(
    "{LINGUISTIC_HINTS}", LINGUISTIC_HINTS,
)
