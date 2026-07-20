# Debug: retrieval-quality-deep-analysis

## Status: [OPEN]

## User Report
- 测试 xlsx 中约 22/35 题被判为"不可用"
- 关键内容（如"延展期"、"产品开通办理机构类型"、"利率白名单"、DPRB365、节假日2103010）未被命中
- 用户反馈：图谱(Mandol) 似乎没有用上
- 当前导入的 `科创e贷操作手册.md` (65KB) 缺 节假日/DPRB/2103010；完整版在 `科创e贷操作手册(1).docx` (135KB)

## Hypotheses
1. **H1**: 文档导入不完整（用了小 md，缺关键章节 节假日/2103010/DPRB）→ 必须导入完整 docx
2. **H2**: 分块后含 关键提示 的片段被切断或并入跨章节段落（chunk size/overlap 边界问题）
3. **H3**: 检索未启用 Mandol 图谱，单纯 keyword+semantic 不足以恢复关系
4. **H4**: top_k 太小（chat.py 中是 15），长 query 拆出 30+ 短语时单短语只命中一两个片段，ranking 偏低
5. **H5**: LLM 生成时无明确"必须从 context 中引用、不可使用通用知识"的约束

## Action Plan
1. 重新导入完整 135KB docx → 验证 db 中是否含 2103010/DPRB
2. 检查 chunk 内容是否包含 "延展期"、"产品开通办理机构类型" 原文
3. 检查 Mandol 状态 + 启用 holistic retrieval
4. 逐题复现 xlsx 中"不可用"题
5. 修复后对比 35 题
