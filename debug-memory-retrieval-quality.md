# 调试会话: MemoryAgent 检索质量差

**Session ID**: `memory-retrieval-quality`
**状态**: [OPEN]
**日期**: 2026-07-16

## 问题描述
用户通过前端 `http://localhost:3000/chat` 测试题目，得到结果与预期差距很大，几乎不可用，检索结果很多都检索不到。

测试结果文件: `sample/testfile/测试结果.xlsx`

## 假设列表（待验证）

1. **H1: 记忆构建不完整/有损** - 知识入库时切片(chunk)过大或过小、Embedding 维度/模型不匹配、元数据丢失，导致语义信息损失。
2. **H2: 检索召回率低** - 检索时 Query Embedding 未归一化、相似度阈值过高、Top-K 太小、未做混合检索(BM25+向量)。
3. **H3: 检索-生成拼接错位** - 检索到的记忆未正确注入 Prompt 上下文，或 Prompt 模板/系统提示词不准确，导致 LLM 拿到残缺上下文。
4. **H4: 向量库索引/元数据过滤错误** - 使用的 namespace/collection 不一致，过滤条件把正确文档过滤掉。
5. **H5: Embedding 模型/语言不一致** - 构建与检索用了不同模型/不同语种编码，或量化导致语义偏移。

## 调试计划
- [ ] 探查项目结构与入口
- [ ] 阅读构建记忆链路（ingest -> chunk -> embed -> store）
- [ ] 阅读检索记忆链路（query -> embed -> search -> prompt）
- [ ] 静态分析 + 必要插桩，定位 root cause
- [ ] 提出最小修复 + 验证

## 进展
(待补充)
