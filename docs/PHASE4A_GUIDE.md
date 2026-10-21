# Phase 4A 自评、学情建议与学习指南

2026-10-21（Asia/Shanghai）。按用户批准的[设计](PHASE4A_DESIGN.md)完成工程实现及本机部署。当前schema6、29个OpenAPI路径，清单版本仍0.4.1。**后端355项、前端101项测试通过，构建成功；18组隔离真实HTTP通过，9次模拟模型调用，真实模型调用0次。** 浏览器人工验收、真实模型冒烟及真实教学效果尚未完成，不能混同自动测试。

本阶段没有新增依赖/外部服务，没有修改BKT公式/参数、正式评分、先修配置、RulePolicy、题库、个人分块或检索算法。40道候选题仍待审，原55条检索评估及5/15课程外误检保留。

## 使用方式

打开[本机页面](http://127.0.0.1:8000/)，创建/恢复演示学习标识，进入“资料学习工作台”的“学习工作室”。中小屏通过原“学习工作室”分栏按钮进入。

1. **我的自评**：对五个知识点选择1不了解、2理解概念、3能够完成基础习题、4能够独立应用；信心可留空，填写时1～5。未填保持未填，不能默认成0级或3分。保存只提交变动行，修改追加历史。
2. **学情对照与重点**：分别显示自评/信心/时间与正式答题次数、最近结果、BKT模型估计。没有正式答题显示“待诊断”，不把0.20先验当成测评。重点、理由、先修与题目可用性由程序确定。
3. **本地规则指南**：默认不检索任何资料、也不调用模型。可勾选附加当前选中资料的本地检索片段。生成前须先保存/核对自评；指南使用已保存状态，不读取本机未保存草稿。
4. **模型辅助讲解**：显式选择模型方式后，说明将向当前服务发送目标、自评/信心、BKT与答题摘要及所选相关片段。个人笔记还需指南本轮单独勾选；Chat的同意不会传给指南，下轮或版本/来源变化后清除。
5. **指南历史**：刷新/打开只读取原结果。答题、自评、资料或规则变化后标记“可能过期”，仍保留当时正文和引用。执行待确认时只查询原请求，不自动重发。

自评与笔记分别保存本机草稿。自评冲突会保留本机输入；点击“读取新版本并保留本机修改”后核对并明确保存。保存后的刷新使用GET，不调用原会创建练习分配的`/next`。

进入正式练习仍由原RulePolicy决定下一题，不保证直接跳到推荐点。题耗尽/累计上限明确提示，不新增、启用或替换题目。来源引用可打开现有抽屉，查看类型、版本、位置和原始Markdown，支持Escape与焦点恢复。

## 推荐算法与可解释依据

`GuidanceService`在单一SQLite事务中读取目标、Mastery、相关作答与最新自评，计算独立的`guidance-rules-v1`：

| 条件 | 规则行为 |
| --- | --- |
| 无答题 | 待诊断；probability=null，prior_probability单独保留，不判定实际薄弱 |
| 最近答错 | 优先复习并核验，列出真实次数/最近结果/事件时间 |
| 尚未达到原演示推进条件 | 建议复习练习，原条件仍为有证据、p≥原阈值且最近答对 |
| 高自评但答题证据不匹配，或低自评但证据较好 | 提示“可能存在差异、建议进一步诊断”，不判断任何一方必然错误 |
| 信心较低 | 回顾成功作答、解释步骤并核验；不调整p |
| 自评早于最近作答 | 标记时间先后，建议更新自评 |
| 先修未满足 | 展示blocked_by，重点先安排可核验的先修 |
| 新题耗尽/累计轮数上限 | 明确诊断受限，保留资料与学习历史入口，不绕过原流程 |

目标及先修集合内最多3个重点，按最近错误、无证据、未达条件、差异/信心支持排序，同类按原拓扑与ID稳定排序。所有五点仍可对照，目标外不自动变成本轮重点。

等级不换算概率，信心不当作正确率。数据包含来源版本（BKT/策略/知识点/题库/指南规则）、自评记录与批次版本、最近至多3条相关事件。作答按真实decisions.revision排序，不从前端截断的历史猜测全量次数。这些是可复查的产品规则，不是校准量表或学习效果结论。

## 实际API

前缀`S=/api/v1/students/{student_id}`，course_id固定machine_learning。新接口严格禁止额外字段/bool冒充整数；自评与指南请求体限256KiB。演示student_id仅用于本机作用域，不是认证。

| 方法与路径 | 契约 |
| --- | --- |
| GET S/self-assessments/latest | 五点最新自评/null，assessment_revision |
| POST S/self-assessments | 1～5项原子保存；首次201、重放200 |
| GET S/self-assessments | 历史；knowledge_id可选、limit1～50、offset≥0 |
| GET S/self-assessments/requests/{request_id} | 只读原保存回执 |
| GET S/learning-guidance | 一致学情快照、规则建议、双版本、snapshot_hash；不分配题目 |
| POST S/study-guides | 显式生成/保存指南，默认rules |
| GET S/study-guides | 最近历史，limit1～50，不调用模型 |
| GET S/study-guides/{request_id} | 原结果/引用、当前过期原因与执行状态 |

自评示例（每次新报告使用新UUID，重试保留原UUID和原内容）：

```json
{
  "request_id": "a03076ba-2036-435a-af2b-4784f7bd4c29",
  "course_id": "machine_learning",
  "expected_revision": 0,
  "items": [{"knowledge_id": "gradient_descent", "level": 2, "confidence": null}]
}
```

回执分别返回`committed_revision`和`current_revision`，以及原值、记录ID、服务端时间和保存时答题revision。原请求重放先于新版本校验，旧回执不能覆盖新自评；同编号不同有效内容409，其他学生/不存在404，旧revision409，非法字段/量表422，超限413。

指南示例（版本从GET learning-guidance取得，下面数字仅为示例）：

```json
{
  "request_id": "0990c6d9-dab3-4cb7-bc82-1d8c574fa3cf",
  "course_id": "machine_learning",
  "expected_learning_revision": 0,
  "expected_assessment_revision": 1,
  "mode": "rules",
  "sources": [],
  "allow_personal_external": false
}
```

`rules + sources=[]`完全不执行检索，不是默认查询全库。`model`必须非空sources，使用现有SourceRef `{source_type,source_id,source_version}`；空集合422。原knowledge/search、workbench/questions仍拒绝空来源，契约未扩大。

所选来源继续校验学生、课程、当前版本、删除及索引就绪；旧版本409、缺失/其他学生404、索引不可用503，不能静默换成全库。规则概况GET独立可用，用户可明确选择不附资料生成本地指南。两个学情版本在生成前变化返回409 `learning_context_changed`；生成途中变化保留旧快照并标记过期。

指南返回不可变snapshot、**已保存的原始rules_md**、explanation_md、实际citations、来源当前状态、stale_reasons、模型用量/工具/时间和原因。规则与模型文案分开显示，不能从模型文本反解析执行动作。

## 受控模型与失败恢复

`StudyGuideService`复用KnowledgeService与WorkbenchAgent的LangGraph执行器。新增冻结GuideRequestContext，在原学生/课程/来源版本/逐轮同意/答题revision之上增加自评revision、snapshot_hash和规则版本。每次检索、模型调用前与发布前复查。

本地按最多3个已确定重点检索，去重后最多5片段。模型初始消息显式包含经允许字段筛选的`server_guide_context`；不依赖模型自行选择是否读取学情工具，不传学生/自评/事件ID、完整试题历史、答案或未选笔记。旧QA默认输入/输出保持兼容。

仍只有`get_learning_state`、`retrieve_selected_sources`两个只读工具，沿用默认最多3模型调用、每次最多4工具、合计8工具。拒绝额外身份/来源字段、自评/BKT/评分/SQL/文件/分配工具。改写也仅限原集合及初始取得的引用。指南输出只允许辅助文本与citation_ids；规则覆盖字段、任意链接或未验证引用会丢弃模型补充，保留规则。

缺少密钥/依据、没有本轮个人笔记外发同意时模型0调用。模型错误保存明确的规则结果；超时/网络/上游执行未知为uncertain，不接管和重试。同编号同内容只读原请求，不重复生成。中断running在重启后显示uncertain。model_calls是已持久化的尝试次数，不是账单。

**uncertain与过期可同时存在**：若超时期间自评/资料也变化，保留uncertain和原错误原因，同时返回stale_reasons，不能因过期而解除重复发送保护。普通已完成指南后来变化时显示stale。

历史引用保留当时Markdown快照，修改/软删除后标注，不作为当前检索来源。软删除不物理清除原文、工作台/指南快照和备份。模型文案仍可能出现事实错误；工具和引用边界校验不证明句子级真实性或彻底解决提示注入。

## schema5→6、备份与回滚

新增三张表，原12张表及旧tutor/workbench记录契约保留：

- `self_assessment_batches`：request_id PK、student FK、course、独立assessment_revision/expected_revision、request_hash/payload_json、learning_revision_at_save、created_at。学生/课程/revision唯一，并提供请求/学生/课程复合唯一键。
- `self_assessment_entries`：服务端UUID、batch_id/student/course复合外键、knowledge_id、level CHECK1～4、confidence CHECK null或1～5；每批每知识点唯一。知识点仍由Catalog验证，没有虚构SQL知识点表。
- `study_guide_runs`：独立请求、学生/课程、请求hash、两种学情revision、context/snapshot/recommendations/result JSON、状态、调用数与时间；按学生/课程/时间索引。

自评批次在短事务内CAS分配新版本并原子追加全部行，不覆盖原报告。指南在任何可能的外发前持久化声明。数据库与API/算法分层，相关仓储位于storage/self_assessments.py与study_guides.py。

实际记录：

- 迁移前代码/旧前端归档：`data/local/phase4a-prechange-85a21e83.zip`，248文件，SHA256 `2205ce01ffb6958bcfeab0df1d83d7e0bb91caa27295aca3986f63cfdf001040`；不含.env或数据库。
- schema5备份：`data/local/eduagent.before-v5-4c770859bdb5.sqlite3`，含本机资料，按私有备份保留。
- [迁移/回滚记录](../data/evaluation/phase4a-migration-v1.json)：迁移前后及备份完整性/外键检查通过；原12表数量及摘要一致；当前15表。保留12学生、14掌握度、37决策、27作答、5旧讲解、5笔记、6关联、11片段及原metadata/index/workbench事实。
- 在独立`data/local/phase4a-rollback-check-*`目录实测旧schema5代码读取备份副本，拒绝schema6副本，拒绝后数据摘要不变。现用库没有执行回滚。

迁移采用SQLite backup，验证原版本/摘要后开启EXCLUSIVE事务，再复查防并发写入，新增表/索引并复核原12表、integrity_check与foreign_key_check后设置6；失败回滚并保留备份。不是复制正在写入的裸数据库文件。

若需回退：先停止本项目写入，另用SQLite backup保留当前schema6及新增自评/指南；在独立目录恢复旧代码/旧前端与schema5备份副本，明确指向恢复库并用单独端口核验，再决定切换。**不覆盖现库、不删表改版本、不让旧代码连接schema6。** 迁移前备份不包含后来新增数据，不能宣称无损自动合并。

## 测试与部署证据

复现命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
Set-Location frontend
npm.cmd run test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe scripts/verify_phase4a.py
.\.venv\Scripts\python.exe scripts/verify_phase4a_deployment.py
```

- 后端：**355 passed in 19.13s**，原318项加37项。覆盖量表/原子/幂等/旧版本/学生隔离、独立学习事实、无先验诊断、差异规则/先修/题耗尽、版本竞争、受控来源/模型补充、规则/异常恢复、迁移失败与回滚。
- 前端：**101 passed in 4.32s**，原87项加14项。覆盖独立草稿、保存/刷新、冲突、断网回执、迟到响应、逐轮同意、空来源/未保存状态、历史/原文/焦点、App无额外分配和待确认+过期组合。
- [18组真实HTTP](../data/evaluation/phase4a-http-v1.json)：独立数据库、两次服务启动、9次模拟模型、0次真实模型；并发自评/指南、三个版本竞争、超时叠加过期、不重新付费、重启无密钥、旧评分/BKT/检索/历史通过。脚本故障钩子只存在测试进程/文件，不是生产端点。
- [只读部署检查](../data/evaluation/phase4a-deployment-v1.json)：本机8000、schema6、29路径、静态资源与自评/建议/指南查询；没有给主库写入合成学习记录或调用模型。
- [最终完整性报告](../data/evaluation/phase4a-integrity-v1.json)：原12表摘要一致，55个受保护文件（含全部30个原数据文件）未变，备份和旧代码归档摘要校验通过。
- Vite构建成功；现有Markdown/KaTeX使主包继续超过500kB默认警告，没有隐藏警告或扩大拆包重构。

`verify_workbench.py`及`verify_workbench_deployment.py`保留Phase3B的历史基线，不能用其中schema5/23路径的预期验收当前服务；当前阶段使用上述两个`verify_phase4a`脚本，旧报告不覆盖。

曾失败及修复：自评单测初轮8项因测试字典重复关键字构造失败，修正夹具后通过；前端初轮100项断言完成但有1个未处理异步表单异常，不能记为通过，补充草稿就绪保护后通过；首轮HTTP跨学生请求误带A的自评版本，先得到合法409，修正B的版本以实际验证404隔离。旧schema测试夹具随新表/版本调整，原数据与断言保护未削弱。

本轮**未执行真实DeepSeek请求**；须另行确认次数/预算后，使用合成资料及指南本轮外发同意冒烟并单独记录。此前浏览器URL安全限制未绕过，本轮没有实际浏览器视觉/端到端操作；jsdom和HTTP不能冒充浏览器验收。

## 浏览器人工验收清单（待完成）

- [ ] 1440px桌面、1024px工作室切换、390px单栏均可操作；五行自评/长理由/公式/代码/表格不撑开页面。
- [ ] 五个知识点的四级自评及1～5信心有标签，信心可空；单点/多点保存后刷新恢复、历史追加、自评版本变化而答题版本不变。
- [ ] 自评未保存时切换普通页或学习标识可恢复本机草稿；笔记草稿保持独立；存储不可用时阻止丢失输入的导航并给出错误。
- [ ] 双标签修改自评触发冲突，保留草稿，读取新版本后须明确保存；旧回执不能显示成最新事实。
- [ ] 无答题时对照/指南显示待诊断；有真实合成评分后次数/最近结果/原因更新，先修/题耗尽解释与原服务一致。
- [ ] 本地规则无密钥可生成；未附来源时不请求检索；模型空来源不可提交，未勾选指南个人外发同意则不发送个人片段，Chat勾选不影响指南。
- [ ] 修改自评、正式作答、修改/删除笔记后，历史指南保留原正文和快照并标过期；待确认状态不因此解除。
- [ ] 模拟断网后刷新只GET原回执/指南；不自动调用付费模型；独立新请求有费用提示。
- [ ] Tab/Shift+Tab访问所有控件，表单回车可提交；引用可打开匹配原文，Escape关闭，焦点回到触发位置。
- [ ] 保存自评、只读刷新、生成指南不新增练习分配；只有显式进入原练习流程才按原策略安排；原学习、Chat、笔记CRUD/索引/草稿/另存仍可用。

## 文件与限制

精确文件与摘要见[phase4a-files-v1.json](../data/evaluation/phase4a-files-v1.json)，完整验证摘要见[phase4a-validation-v1.json](../data/evaluation/phase4a-validation-v1.json)。

规则是工程启发式，未校准自评量表、BKT或信心，不能证明学习提升。单课程、单机演示作用域不等于真实认证；自评/指南历史暂无物理清除或保留期限管理。同步请求、词项检索和原调用预算保持；当前支持现有练习与资料入口，不增加目标指定分配、指南另存笔记、总结/卡片、教材/图片或新题库。

Phase4A工程交付后停止。后续仅等待负责人验收、内容审阅与真实模型预算；下一阶段须另行确认。
