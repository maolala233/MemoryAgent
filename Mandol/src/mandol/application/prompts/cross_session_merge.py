"""Prompts for cross-session entity/event merging."""

# LLM prompt for judging whether an entity cluster should be merged.
# Inputs: entity name, type, and per-session fact descriptions.
# Output: JSON with should_merge, confidence, canonical_name, reasoning.
CLUSTER_JUDGE_PROMPT = """你是一名资深知识图谱工程师，专长于实体核心指代消解。

### 任务
判断给定聚类中的实体是否指代同一个现实世界实体。

### 聚类信息
{cluster_info}

### 任务说明

1. 分析每个实体的名称、类型、描述
2. 检查语义等价性（同一实体被不同名称/描述指代）
3. 综合考虑：
   - 名称相似度（精确匹配、别名、缩写）
   - 类型一致性（必须同类型才能合并）
   - 描述兼容性（信息不矛盾）
   - 会话上下文线索

4. 决策规则：
   - 若**所有**实体明显指代同一现实实体：返回 `should_merge: true`
   - 若**任一**实体明显不同或有矛盾：返回 `should_merge: false`
   - 若不确定但可能相同：返回 `should_merge: true`（使用较低 confidence）

5. 名称比较时注意：
   - 中英别名/全称/缩写差异（例如"小李"/"李明"/"Li Ming"）
   - 描述性指代与真实名称（例如"小李的家乡"/"桃源村"）

### 少量示例

**示例 1：同一实体，不同名称**
聚类:
- 实体 A: "小李" (Person) - "小李是一名来自桃源村的软件工程师"
- 实体 B: "李明" (Person) - "李明昨天买了一台相机"
输出:
{{
    "should_merge": true,
    "confidence": 0.95,
    "canonical_name": "李明",
    "reasoning": "两者指代同一人。'李明'是全名，'小李'是常见昵称。描述信息兼容。"
}}

**示例 2：不同实体，同名**
聚类:
- 实体 A: "苹果" (Organization) - "苹果公司是一家科技企业"
- 实体 B: "苹果" (Place) - "苹果是英国的一座小镇"
输出:
{{
    "should_merge": false,
    "confidence": 0.90,
    "canonical_name": null,
    "reasoning": "名称相同但类型不同，明显指代不同的现实实体。"
}}

**示例 3：描述性指代合并**
聚类:
- 实体 A: "小李的家乡" (Place) - "小李的家乡遭受了洪灾"
- 实体 B: "桃源村" (Place) - "桃源村位于北方"
输出:
{{
    "should_merge": true,
    "confidence": 0.85,
    "canonical_name": "桃源村",
    "reasoning": "'小李的家乡'是描述性指代，可能指代'桃源村'。两者都是 Place 类型。"
}}

**示例 4：不确定但可能相同**
聚类:
- 实体 A: "那家公司" (Organization) - "那家公司宣布裁员"
- 实体 B: "腾讯" (Organization) - "腾讯是一家科技巨头"
输出:
{{
    "should_merge": false,
    "confidence": 0.60,
    "canonical_name": null,
    "reasoning": "'那家公司'太模糊，无足够上下文无法确认指代'腾讯'。"
}}

### 输出格式（仅 JSON）
{{
    "should_merge": true|false,
    "confidence": 0.0-1.0,
    "canonical_name": "合并时的首选规范名称，或 null",
    "reasoning": "决策的简要说明"
}}
"""

# LLM prompt for judging whether an event cluster should be merged.
# Output: JSON with should_merge, confidence, canonical_name, reasoning.
EVENT_CLUSTER_JUDGE_PROMPT = """你是一名资深知识图谱工程师，专长于事件核心指代消解。

### 任务
判断给定聚类中的事件是否指代同一个现实世界事件。

### 聚类信息
{cluster_info}

### 任务说明

1. 分析每个事件的名称、描述、参与者、时间
2. 检查语义等价性（同一事件被不同方式描述）
3. 综合考虑：
   - 事件类型/性质相似度
   - 参与者重叠度
   - 时间邻近性
   - 地点一致性
   - 描述兼容性

4. 决策规则：
   - 若**所有**事件明显指代同一现实事件：返回 `should_merge: true`
   - 若**任一**事件明显不同或有矛盾：返回 `should_merge: false`
   - 若不确定但可能相同：返回 `should_merge: true`（使用较低 confidence）

5. 名称比较时注意中英文别名/简称差异。

### 少量示例

**示例 1：同一事件，不同描述**
聚类:
- 事件 A: "洪灾" - "洪灾袭击了小李的家乡"
- 事件 B: "那场灾害" - "那场灾害对桃源村造成重大损失"
输出:
{{
    "should_merge": true,
    "confidence": 0.90,
    "canonical_name": "洪灾",
    "reasoning": "两者指代同一场洪灾事件。'那场灾害'是'洪灾'的指代。"
}}

**示例 2：不同事件**
聚类:
- 事件 A: "会议" - "会议在周一举行"
- 事件 B: "学术报告" - "学术报告在周三开始"
输出:
{{
    "should_merge": false,
    "confidence": 0.85,
    "canonical_name": null,
    "reasoning": "不同日期的不同事件，会议和学术报告是独立事件。"
}}

**示例 3：同一事件，更多细节**
聚类:
- 事件 A: "小李买了一台相机" - "小李昨天买了一台相机"
- 事件 B: "那次购物" - "那次购物在亚马逊完成"
输出:
{{
    "should_merge": true,
    "confidence": 0.95,
    "canonical_name": "小李买了一台相机",
    "reasoning": "'那次购物'指代买相机这一事件，同一事件包含更多细节。"
}}

### 输出格式（仅 JSON）
{{
    "should_merge": true|false,
    "confidence": 0.0-1.0,
    "canonical_name": "合并时的首选规范名称，或 null",
    "reasoning": "决策的简要说明"
}}
"""

# LLM prompt for merging entity descriptions across multiple sessions.
# Inputs: {name}, {type}, {session_facts} JSON.
# Output: JSON with merged_description, merged_aliases.
CROSS_SESSION_MERGE_PROMPT = """你是一名资深知识图谱工程师。

### 任务
将多个会话的描述合并为统一的规范描述。

### 背景
**实体/事件名称**: {name}
**类型**: {type}
**会话事实**: {session_facts}

### 任务说明

1. 将所有会话事实合并为一段连贯描述
2. 解决矛盾（优先采纳更新或更具体的信息）
3. 描述保持简洁（2-4 句，最多 120 字）
4. 保持事实准确性 - 不要虚构
5. 保留所有会话的重要细节
6. 关于 merged_aliases：只包含**简短的**别称或指代（每个不超过 6 个词）。不要把完整描述或句子作为别名

### 输出格式（仅 JSON）
{{
    "merged_description": "合并所有会话信息的统一描述",
    "merged_aliases": ["简短别名1", "简短别名2"],
    "confidence": 0.95
}}
"""

# LLM prompt for merging event descriptions across multiple sessions.
# Inputs: {name}, {session_facts}, {existing_participants}, {existing_time}.
# Output: JSON with merged_description, merged_participants, merged_time.
CROSS_SESSION_EVENT_MERGE_PROMPT = """你是一名资深知识图谱工程师。

### 任务
将多个会话的事件描述合并为统一的规范描述。

### 背景
**事件名称**: {name}
**会话事实**: {session_facts}
**已有参与者**: {existing_participants}
**已有时间**: {existing_time}

### 任务说明

1. 合并所有会话的参与者
2. 解决时间信息（优先显式时间而不是推断时间）
3. 合并描述为一段连贯文字（1-2 句，最多 60 字）
4. 保持事实准确性 - 不要虚构

### 输出格式（仅 JSON）
{{
    "merged_description": "合并后的统一事件描述",
    "merged_participants": ["参与者1", "参与者2"],
    "merged_time": "ISO 8601 或相对时间",
    "confidence": 0.95
}}
"""
