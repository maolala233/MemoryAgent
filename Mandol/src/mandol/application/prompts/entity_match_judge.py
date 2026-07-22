"""Prompt for LLM-based entity match judging.

Determines whether a newly extracted entity refers to the same real-world
entity as a known canonical entity candidate.
"""

ENTITY_MATCH_JUDGE_PROMPT = """你是核心指代消解与实体匹配专家。

给定一个新抽取的实体和一组候选规范实体，判断新实体是否指代与某候选相同的现实世界实体。

## 新实体
名称: {new_entity_name}
类型: {new_entity_type}
事实: {new_facts}
指代表达: "{mention_text}"

## 候选规范实体
{candidates}

## 任务说明
1. 将新实体与每个候选仔细对比。
2. 综合考虑：名称相似度、类型兼容性、描述重叠度、事实一致性。
3. 若新实体明显指代与某候选相同的现实实体，选出该候选。
4. 若新实体与所有候选均不同，输出无匹配。
5. 名称比较时注意：
   - 中英别名/全称/缩写差异（例如"小李"/"李明"/"Li Ming"）
   - 描述性指代与真实名称（例如"小李的家乡"/"桃源村"）
   - 同义词、近义词、口语与书面语差异
6. 当不确定但两个实体可能是同一个时，倾向匹配（用较低 confidence）。

## 输出格式
返回 JSON 对象：
```json
{{
    "matched_index": <整数或 null>,
    "confidence": <0.0~1.0 之间的浮点数>,
    "canonical_name_suggestion": <字符串或 null>,
    "new_aliases": <字符串列表>,
    "reasoning": "<简要说明>"
}}
```

字段说明：
- `matched_index`：匹配候选的 0-based 索引，无匹配则为 null
- `confidence`：对该匹配决策的置信度（0.0 = 无信心，1.0 = 绝对确定）
- `canonical_name_suggestion`：若合并，建议的规范名称（或 null 保持原名）
- `new_aliases`：应加入规范实体的别名列表
- `reasoning`：决策的简要说明
"""
