"""Task B: Description merge prompt for entities and events."""

# LLM prompt for merging entity descriptions from multiple sessions.
# Inputs: canonical name, type, and list of per-session fact descriptions.
# Output: JSON with merged_description and merged_aliases.
DESCRIPTION_MERGE_PROMPT = """你是一名资深知识图谱工程师。

### 任务
将已有的规范描述与新抽取的事实合并，生成更新后的统一描述。

### 背景
**实体/事件名称**: {name}
**类型**: {type}
**已有规范描述**: {existing_description}
**新抽取的事实**: {new_facts}
**历史会话事实**: {session_facts}

### 任务说明

1. 将所有信息合并为一段连贯的描述
2. 解决任何矛盾（信息冲突时优先采纳更新的信息）
3. 描述保持简洁（2-4 句，最多 120 字）
4. 保持事实准确性 - 不要虚构
5. 保留来自已有和新增信息的重要细节
6. 若原描述与新事实为不同语言，按原文主语言保持一致

### 少量示例

**示例 1：实体描述合并**
名称: 小李
已有描述: 小李是一名软件工程师。
新事实: ["昨天买了一台相机", "来自桃源村"]
历史会话事实: []
输出:
{{
    "merged_description": "小李是一名来自桃源村的软件工程师，最近购买了一台相机。",
    "confidence": 0.95
}}

**示例 2：实体描述存在矛盾**
名称: 小王
已有描述: 小王住在上海。
新事实: ["上个月搬到了北京"]
历史会话事实: []
输出:
{{
    "merged_description": "小王最近搬到了北京，此前曾居住在上海。",
    "confidence": 0.90
}}

**示例 3：事件描述合并**
名称: 洪灾
已有描述: 洪灾袭击了小李的家乡。
新事实: ["发生于 2024 年 1 月 15 日", "造成重大损失"]
历史会话事实: []
输出:
{{
    "merged_description": "2024 年 1 月 15 日，一场洪灾袭击了小李的家乡，造成重大损失。",
    "confidence": 0.95
}}

**示例 4：跨会话实体合并**
名称: 桃源村
已有描述: 小李来自桃源村。
新事实: ["遭受洪灾袭击", "位于北方"]
历史会话事实: [{{"session": "sess_1", "description": "小李的家乡"}}]
输出:
{{
    "merged_description": "桃源村是小李的家乡，位于北方，曾遭受洪灾袭击。",
    "confidence": 0.90
}}

### 输出格式（仅 JSON）
{{
    "merged_description": "合并已有与新信息的统一描述",
    "confidence": 0.95
}}
"""

# LLM prompt for merging event descriptions from multiple sessions.
# Inputs: canonical name, existing participants, time, and session facts.
# Output: JSON with merged_description, merged_participants, merged_time.
EVENT_DESCRIPTION_MERGE_PROMPT = """你是一名资深知识图谱工程师。

### 任务
将已有的规范事件描述与新抽取的事实合并，生成更新后的统一事件描述。

### 背景
**事件名称**: {name}
**已有规范描述**: {existing_description}
**已有参与者**: {existing_participants}
**已有时间**: {existing_time}
**新抽取的事实**: {new_facts}
**新参与者**: {new_participants}
**新时间**: {new_time}

### 任务说明

1. 合并参与者：合并已有与新参与者，去重
2. 解决时间冲突：优先采纳显式时间而不是推断时间，更新信息优先于旧信息
3. 将描述合并为一段连贯文字（1-2 句，最多 60 字）
4. 保持事实准确性 - 不要虚构

### 输出格式（仅 JSON）
{{
    "merged_description": "合并后的统一事件描述",
    "merged_participants": ["参与者1", "参与者2"],
    "merged_time": "ISO 8601 或相对时间",
    "confidence": 0.95
}}
"""
