# 本轮实际验收记录（2026-10-22）

## 完成结果

五入口/独立资料和题库页面、ID导航、扩展题型/文字答案/子问、受控LangGraph提取、任务恢复、原稿/修正稿对照与显式接受、文字普通练习已实现并部署。新依赖0。schema9→10新增两表；原34表、原件、旧评估摘要一致，现有12道个人题、5篇笔记、2份课件及27条正式作答保持。

| 验证 | 实际结果 |
| --- | --- |
| 后端完整pytest | 552通过，最终0失败；包含27项新增参数化/提取相关测试 |
| 前端Vitest/jsdom | 149通过，最终0失败；新增6项授权/恢复/文字输入/子问/路由测试 |
| 前端构建 | 通过，仍有主JS约712kB超过500kB提示 |
| 新提取真实HTTP | 13组通过，4次模拟模型；两次服务启动，超时/重启不重发 |
| 原题库/课件/知识体系/指南/聊天HTTP | 21＋15＋17＋18＋14＝85组通过 |
| 最终HTTP报告集合 | 98组，33次模拟模型，真实模型0；不是所有重复调试的累计调用数 |
| 独立真实DeepSeek验证 | 合计12次：文字4＋4＋3，视觉1；均为自建资料 |
| 副本迁移、现库迁移、旧代码恢复 | 均通过；旧9代码拒绝10库，恢复9副本可打开 |
| 现用8000服务只读验证 | 健康、67条API路径、静态资源、能力入口与原事实一致性通过 |
| 真实浏览器/人工内容审阅/学习效果 | 未执行/未验证，不能用HTTP、jsdom或模型输出替代 |

后端完整验证包含原课程/个人检索、Chat/指南、笔记CRUD、自评、客观评分、BKT、正式学习历史和课件/知识体系。正式题库仍原10道演示题；40道候选题未启用，原55条检索记录及5/15课程外误检未删除。

## 真实文字提取对照

[固定样本](../data/evaluation/question-extraction-samples-v2.json)：24道自建工程参考，23道明确题型＋1道遮挡未确定题；包含A/B任务、选择、多选、判断、填空、简答、计算、证明、子问、公式和缺图。参考由开发者自建，**未经用户独立人工审阅**，不代表真实试卷分布。

同一输入分别运行备份中的旧正则、新本地规则、真实语义模型；逐题结果和分母保留于[最终文字报告](../data/evaluation/extraction-v2-model-v3.json)。以下是该集合的检查计数，不是泛化准确率：

| 检查 / 24 | 旧规则 | 新本地规则 | 最终真实语义提取 |
| --- | ---: | ---: | ---: |
| 题目边界/原题号唯一对应 | 22 | 24 | 24 |
| 题型与自建参考一致 | 6 | 24 | 24 |
| 必需文字/公式要素保留 | 21 | 24 | 24 |
| 选项数量（判断固定控件另计） | 22 | 24 | 24 |
| 原文答案/未知状态与参考一致 | 18 | 22 | 24 |

最终子问与缺图依赖检查通过。只有一例要求结构化子问、一例要求明确图形依赖；其余题的该项多数是“不需要”，不能描述成24例复杂子问/图表测试。未知题保持未确定，没有通过全部标unknown绕过验收。实际人工校正量和真实教师资料准确率未测，不报告。

真实视觉另使用自建两页清晰栅格PDF：[报告](../data/evaluation/extraction-v2-visual-v1.json)。1次请求返回2道题，分别计算/证明，第一题跨页含2个子问，原文没有答案时未解题补答案；记录待核对标记。只证明当前接口能接收本流程原页、该自建样例可还原，不证明扫描件/复杂公式普遍可靠。

## 失败与修复，保留原记录

- 首轮前端7项因入口名称/位置及地址持久化测试隔离失败；逐项迁移用户路径断言，未删除原草稿/安全/学习流程验收。
- 早期个人题库6项失败，修复共享背景保留、仅A/B标签不决定题型、未知内容提示及新表旧库夹具。一次完整回归524/525，剩旧v1夹具未删新表；修复后完整通过。新增自测一例判断答案夹具错误，已修正。
- [真实文字第1轮](../data/evaluation/extraction-v2-model-v1.json)：4次、2批均失败；判断题固定控件被误作原文选项。没有发布失败草稿。该历史报告的早期空结果答案计数也含评估器缺陷，不能作为有效质量结论，最终评估器已要求题目存在。
- [真实文字第2轮](../data/evaluation/extraction-v2-model-v2.json)：4次，一批完成、一批结构失败。发现判断答案仅保存在文字字段及多选键表示差异；增加无歧义表示兼容，同时将答案校验限制到本题引句，防止借用同页别题答案。
- 第3轮3次，两批完成，24题通过上述自建参考检查。前两轮不重写为成功，不隐藏失败调用。
- 视觉自测脚本先有两次本地夹具参数错误（缺source_note、缺runner参数），均在模型前失败、调用0；修复后1次真实成功。
- 旧HTTP文档/知识体系脚本第一次最终版本断言仍写schema9，导致失败；仅将期望同步10后重跑通过，不删除功能断言。

## 工程边界验证

模拟自动化验证了：重复请求只执行一次、同ID不同内容拒绝、学生隔离、不允许模型添加来源/工具/控制字段、原文答案依据、最多一次复核、截断不重发、网络调用无写事务、模型等待期间其他写入可进行、来源更新/原题编辑使任务失效、重启uncertain不重发、原文保留、文字草稿CAS/幂等、自主复习标记不变成客观错题、不写BKT及评分事实。

真实HTTP验证了完整提取→审核→练习→文字草稿→结果→修正稿显式接受→来源竞争→超时→服务重启路径；HTTP中的模型为模拟，不能将模拟次数算作真实DeepSeek质量证据。

迁移采用真实SQLite备份/原34表原列摘要比对/事务DDL/故障回滚测试/完整性和外键校验。保留现库升级副本和旧9恢复副本，没有用旧库覆盖新库。详见[迁移](../data/evaluation/extraction-v2-migration-v1.json)、[演练](../data/evaluation/extraction-v2-migration-rehearsal-v1.json)、[部署](../data/evaluation/extraction-v2-deployment-v1.json)。

## 报告索引

- [新提取HTTP最终](../data/evaluation/extraction-v2-http-v2.json)，[第一次通过记录](../data/evaluation/extraction-v2-http-v1.json)。
- [原题库HTTP](../data/evaluation/extraction-v2-bank-http-v1.json)、[文档HTTP](../data/evaluation/extraction-v2-documents-http-v1.json)、[知识体系HTTP](../data/evaluation/extraction-v2-architectures-http-v1.json)。
- [指南HTTP](../data/evaluation/extraction-v2-guidance-http-v1.json)、[问答HTTP](../data/evaluation/extraction-v2-chat-http-v1.json)。
- 完整修改文件和自动摘要见`data/evaluation/extraction-v2-delivery-v1.json`；文件列表在本记录末尾生成。

## 待人工浏览器验收（均未勾选）

此前localhost浏览器访问被拒，未更换工具绕过；本轮没有声称已操作真实浏览器。

- [ ] 桌面五入口可直接进入，课程资料与题库无多层嵌套；旧课程检索仍可使用。
- [ ] 窄屏目录/编辑器为单列，长公式、表格、代码和原页图不撑开页面。
- [ ] Tab可操作来源、页码、同意、提取、审核和文字输入；错误有可见提示。
- [ ] 改变来源/页码清除外发同意；未同意零外发，下一轮重新确认。
- [ ] 选择真实有权使用的1～3相邻页，对照模型输出逐项核对边界/题型/图表/公式/跨页条件，记录人工改动。
- [ ] 审核后单选/判断按已确认答案评分；简答/计算/证明为文字输入、不评分；多选/填空暂用文字作答。
- [ ] 文字作答保存后刷新恢复；断网/模型超时不重发付费请求，任务编号仍能查到。
- [ ] 原稿与修正稿对照可保留原稿；接受后产生新草稿revision，旧历史可回看。
- [ ] 返回/前进/直接ID链接恢复目标，题目、笔记、自评草稿互不串用；浏览器刷新来源选择保持。
- [ ] 现有笔记编辑、Agent引用抽屉Escape/焦点恢复、正式诊断和历史原样可用。

未开展真人教学效果试验。本轮完成工程范围后停止，不自动进入4B-3、新题生成、主观批阅或正式BKT准入。

## 实际源代码与文档修改文件（62个）

- `AGENTS.md`
- `README.md`
- `backend/src/eduagent/agent/deepseek.py`
- `backend/src/eduagent/agent/question_extractor.py`
- `backend/src/eduagent/api/app.py`
- `backend/src/eduagent/api/personal_bank.py`
- `backend/src/eduagent/documents/extraction_coordinator.py`
- `backend/src/eduagent/documents/question_extraction.py`
- `backend/src/eduagent/domain/personal_bank.py`
- `backend/src/eduagent/services/personal_bank.py`
- `backend/src/eduagent/services/question_extraction.py`
- `backend/src/eduagent/storage/extraction_schema.py`
- `backend/src/eduagent/storage/migrations.py`
- `backend/src/eduagent/storage/sqlite.py`
- `backend/tests/test_architectures.py`
- `backend/tests/test_documents.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_personal_bank.py`
- `backend/tests/test_personal_migration.py`
- `backend/tests/test_self_assessments.py`
- `backend/tests/test_semantic_extraction.py`
- `backend/tests/test_tutor.py`
- `backend/tests/test_web.py`
- `backend/tests/test_workbench.py`
- `docs/DEVELOPMENT_PLAN.md`
- `docs/EXTRACTION_V2_GUIDE.md`
- `docs/EXTRACTION_V2_VALIDATION.md`
- `docs/PROJECT_CONTEXT.md`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.test.js`
- `frontend/src/__tests__/extraction-v2.test.js`
- `frontend/src/__tests__/notes-ui.test.js`
- `frontend/src/__tests__/personal-bank.test.js`
- `frontend/src/__tests__/setup.js`
- `frontend/src/__tests__/study-guidance.test.js`
- `frontend/src/__tests__/workbench.test.js`
- `frontend/src/api.js`
- `frontend/src/api/notes.js`
- `frontend/src/api/resources.js`
- `frontend/src/api/workbench.js`
- `frontend/src/components/PersonalBankWorkspace.vue`
- `frontend/src/components/StudyWorkbench.vue`
- `frontend/src/features/questions/ExtractionTasks.vue`
- `frontend/src/features/questions/QuestionContent.vue`
- `frontend/src/features/questions/QuestionFields.vue`
- `frontend/src/features/questions/types.js`
- `frontend/src/usePageRoute.js`
- `frontend/src/usePersonalBank.js`
- `frontend/src/views/LearningHistory.vue`
- `frontend/src/views/LearningOverview.vue`
- `frontend/src/views/QuestionBankView.vue`
- `frontend/src/views/ResourcesView.vue`
- `frontend/vite.config.js`
- `scripts/verify_architectures.py`
- `scripts/verify_documents.py`
- `scripts/verify_extraction_deployment.py`
- `scripts/verify_extraction_migration.py`
- `scripts/verify_extraction_model.py`
- `scripts/verify_extraction_visual.py`
- `scripts/verify_phase4a.py`
- `scripts/verify_semantic_extraction.py`
- `scripts/verify_workbench_answers.py`

另新增自建样本和本轮JSON报告，更新前端dist构建；data/local中保留独立测试库、代码/数据库备份、回退副本及服务日志。现用.env未改写，未新增依赖或启用40道候选题。
