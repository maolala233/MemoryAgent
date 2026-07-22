"""Prompt 1: Entity extraction with coreference resolution."""

# LLM prompt for extracting entities from dialogue with coreference linking.
# Inputs: dialogue text and list of existing candidate entities.
# Output: JSON with extracted entities, each having name, type, linked_id, etc.
#
# 本提示为通用中文版：指令与示例使用中文，但 entity_type schema
# 仍为英文枚举（Person|Group|Organization|Place|Object|Activity|Concept），
# 以保持与存储层和后续图谱代码的兼容。

# 通用语言学提示：跨领域通用的语言现象提示，不引入任何业务专有概念。
LINGUISTIC_HINTS = """**步骤 3：通用语言学现象（适用于任何领域，非业务专用）**
除上述指代消解与基础实体外，请同时留意下列**通用语言现象**，并将它们作为新事实记入对应实体的 `new_facts` 或 `aliases`：
- **缩写、别名、简称**：例如"CRMX"、"小粤"、"网厅"等在文本中首次出现时，建立全称→缩写的别名关系（`aliases` 字段）
- **时间表达式**：例如"有效期一年"、"最长 12 个月"、"每周一上午"等时间约束，原样记录在 `new_facts`
- **否定与前提**：例如"前提是…"、"只有…才…"、"若不…则…"等条件性表述，保留完整语义到 `new_facts`
- **枚举项**：例如"A. … B. … C. …"或"1）… 2）…"等并列结构，记录为多条独立 `new_facts`
- **路径式步骤**：例如"A → B → C"或"页面A-页面B-按钮C"等层级化操作，保留顺序与连接符
- **数值与单位**：例如"利率 3.85%"、"金额 100 万元"、"维度 384"等，保留数值与单位
注意：上述仅是**语言学层面的提醒**，不强制改变 entity_type 的判定。"""

# 模板字符串（模块加载时通过 .format() 注入 LINGUISTIC_HINTS）
_ENTITY_EXTRACTION_TEMPLATE = """你是一名资深知识图谱工程师，专长于实体抽取与指代消解。

### 背景
**当前会话文本**:
{dialogue_context}

**已存在的规范实体**（top-10 最相关）:
{existing_entities}

### 任务

**步骤 1：指代消解**
对文本中出现的代词（"他"、"她"、"它"、"他们"、"这"、"那"、"该"）和描述性指代
（例如"小李的家乡"、"她的公司"、"那个项目"）做指代消解：
- 若指代一个已存在的实体：将 `linked_id` 设为该实体的 id
- 若指代一个新的实体：将 `is_new` 设为 true

**步骤 2：实体抽取**
抽取文本中出现的所有实体，包括：
- 命名实体：人名、地名、机构名、产品名、专有名词等
- 描述性实体：例如"小李的家乡"应作为 Place 实体抽取，而不是仅作为小李的一个属性
- 代词消解后的实体：例如"他"消解到已存在的"小李"

对每个实体，给出：
- `entity_type`：必须为下列英文枚举之一 —— Person | Group | Organization | Place | Object | Activity | Concept
  - 通用选型建议：人 → Person；人群/团队 → Group；公司/机构/部门 → Organization；地点/区域 → Place；
    具体物品/产品/工具 → Object；行为/活动/事件 → Activity；抽象概念/规则/属性 → Concept
- `mention_text`：原文中指代该实体的精确文本片段
- `aliases`：该实体的简称、别称或常用缩写（每个不超过 6 个词，可为空列表）

{LINGUISTIC_HINTS}

### 少量示例

**示例 1：描述性指代**
文本: "小李的家乡去年发生了严重的洪灾"
已存在实体: []
输出:
{{
    "entities": [
        {{"reasoning": "'小李' 是人名实体", "entity_name": "小李",
         "entity_type": "Person", "linked_id": null, "is_new": true,
         "confidence": 0.95, "mention_text": "小李", "new_facts": [], "aliases": []}},
        {{"reasoning": "'小李的家乡' 是描述性指代，应作为 Place 实体抽取，而不是仅作为小李的属性",
         "entity_name": "小李的家乡", "entity_type": "Place", "linked_id": null,
         "is_new": true, "confidence": 0.90, "mention_text": "小李的家乡",
         "new_facts": [], "aliases": []}}
    ]
}}

**示例 2：代词消解**
文本: "他很喜欢它。小王昨天买了一台相机。"
已存在实体: [{{"id": "entity:xiaowang", "name": "小王", "type": "Person"}}]
输出:
{{
    "entities": [
        {{"reasoning": "'他' 在此上下文指代小王",
         "entity_name": "小王", "entity_type": "Person", "linked_id": "entity:xiaowang",
         "is_new": false, "confidence": 0.90, "mention_text": "他",
         "new_facts": ["昨天买了一台相机"], "aliases": ["他"]}},
        {{"reasoning": "'它' 指代后文提到的相机",
         "entity_name": "相机", "entity_type": "Object", "linked_id": null,
         "is_new": true, "confidence": 0.85, "mention_text": "它",
         "new_facts": [], "aliases": []}}
    ]
}}

**示例 3：与已存在实体链接**
文本: "小张在腾讯工作。她很喜欢自己的工作。"
已存在实体: [{{"id": "entity:xiaozhang", "name": "小张", "type": "Person"}}, {{"id": "entity:tencent", "name": "腾讯", "type": "Organization"}}]
输出:
{{
    "entities": [
        {{"reasoning": "'小张' 匹配已存在实体",
         "entity_name": "小张", "entity_type": "Person", "linked_id": "entity:xiaozhang",
         "is_new": false, "confidence": 0.95, "mention_text": "小张",
         "new_facts": ["在腾讯工作"], "aliases": []}},
        {{"reasoning": "'她' 指代小张",
         "entity_name": "小张", "entity_type": "Person", "linked_id": "entity:xiaozhang",
         "is_new": false, "confidence": 0.95, "mention_text": "她",
         "new_facts": ["很喜欢自己的工作"], "aliases": ["她"]}},
        {{"reasoning": "'腾讯' 匹配已存在实体",
         "entity_name": "腾讯", "entity_type": "Organization", "linked_id": "entity:tencent",
         "is_new": false, "confidence": 0.95, "mention_text": "腾讯",
         "new_facts": [], "aliases": []}},
        {{"reasoning": "'自己的工作' 是描述性指代，应作为 Activity 实体抽取",
         "entity_name": "小张的工作", "entity_type": "Activity", "linked_id": null,
         "is_new": true, "confidence": 0.80, "mention_text": "自己的工作",
         "new_facts": [], "aliases": []}}
    ]
}}

### 输出格式（仅 JSON）
{{
    "entities": [
        {{
            "reasoning": "抽取该实体的理由与指代消解决策",
            "entity_name": "规范名称（与原文语言保持一致）",
            "entity_type": "Person|Group|Organization|Place|Object|Activity|Concept",
            "linked_id": "entity_id 或 null",
            "is_new": false,
            "confidence": 0.95,
            "mention_text": "原文指代片段",
            "new_facts": ["事实1"],
            "aliases": ["简称或缩写，每个不超过 6 个词"]
        }}
    ]
}}
"""

# 模块加载时注入 LINGUISTIC_HINTS（用 str.replace 而非 format，避免破坏 JSON 中的 {{}} 转义）
ENTITY_EXTRACTION_PROMPT = _ENTITY_EXTRACTION_TEMPLATE.replace(
    "{LINGUISTIC_HINTS}", LINGUISTIC_HINTS,
)
