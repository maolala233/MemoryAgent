"""Prompt 3: Entity-entity relation extraction."""

# LLM prompt for extracting semantic relationships between entity pairs.
# Inputs: dialogue text and extracted entities with their UIDs.
# Output: JSON with relations list (source, target, rel_type, confidence, reasoning).
#
# 本提示为通用中文版：保持原英文关系子类型 schema（hometown/lives_in/works_at/located_in/part_of）以兼容存储层。

ENTITY_RELATION_PROMPT = """你是一名资深知识图谱工程师，专长于实体间语义关系抽取。

### 背景
**当前会话文本**:
{dialogue_context}

**当前会话实体**:
{current_entities}

### 任务

根据当前文本抽取实体间关系。

**通用抽取原则**：
- 描述性指代暗含关系：例如"小李的家乡"暗含"小李 --RELATED_TO {{subtype:"hometown"}}--> 地点"
- 仅抽取文本中有明确依据的关系，不要凭空猜测
- 关系方向要保持准确：源 → 目标

**可用的关系子类型**（保持原 schema 不变，以便与存储层兼容）：
- `hometown`：人的家乡
- `lives_in`：人当前居住地
- `works_at`：人的工作单位
- `located_in`：实体所处的位置
- `part_of`：整体与部分的关系

**注意事项**：
- 若文本中出现的关系不在上述 5 个子类型内，请优先使用语义上最接近的（如"某公司是某集团的子公司" → `part_of`）
- 不要新增未定义的子类型

### 少量示例

**示例 1：家乡关系**
文本: "小李的家乡去年发生了严重的洪灾"
当前实体: [{{"id": "entity:xiaoli", "name": "小李", "type": "Person"}}, {{"id": "entity:xiaoli_hometown", "name": "小李的家乡", "type": "Place"}}]
输出:
{{
    "relations": [
        {{
            "source": "entity:xiaoli",
            "target": "entity:xiaoli_hometown",
            "rel_type": "RELATED_TO",
            "subtype": "hometown",
            "confidence": 0.90,
            "reasoning": "'小李的家乡' 暗含家乡关系"
        }}
    ]
}}

**示例 2：多种关系**
文本: "小张在腾讯工作，住在深圳。腾讯总部位于南山。"
当前实体: [{{"id": "entity:xiaozhang", "name": "小张", "type": "Person"}}, {{"id": "entity:tencent", "name": "腾讯", "type": "Organization"}}, {{"id": "entity:shenzhen", "name": "深圳", "type": "Place"}}, {{"id": "entity:nanshan", "name": "南山", "type": "Place"}}]
输出:
{{
    "relations": [
        {{
            "source": "entity:xiaozhang",
            "target": "entity:tencent",
            "rel_type": "RELATED_TO",
            "subtype": "works_at",
            "confidence": 0.95,
            "reasoning": "小张在腾讯工作"
        }},
        {{
            "source": "entity:xiaozhang",
            "target": "entity:shenzhen",
            "rel_type": "RELATED_TO",
            "subtype": "lives_in",
            "confidence": 0.95,
            "reasoning": "小张住在深圳"
        }},
        {{
            "source": "entity:tencent",
            "target": "entity:nanshan",
            "rel_type": "RELATED_TO",
            "subtype": "located_in",
            "confidence": 0.90,
            "reasoning": "腾讯总部位于南山"
        }}
    ]
}}

**示例 3：无关系**
文本: "今天天气很好。"
当前实体: []
输出:
{{
    "relations": []
}}

### 输出格式（仅 JSON）
{{
    "relations": [
        {{
            "source": "entity:source_id",
            "target": "entity:target_id",
            "rel_type": "RELATED_TO",
            "subtype": "hometown|lives_in|works_at|located_in|part_of",
            "confidence": 0.9,
            "reasoning": "关系存在的原因"
        }}
    ]
}}
"""
