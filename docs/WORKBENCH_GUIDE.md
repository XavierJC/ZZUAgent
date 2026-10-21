# Phase 3B 资料学习工作台

当前混合问答：[WORKBENCH_HYBRID_GUIDE.md](WORKBENCH_HYBRID_GUIDE.md)；RAG提供参考，大模型综合生成，支持资料外知识补充。误加的时钟功能已移除，391/104项通过；下文仅依据资料的限定属于3B历史。

后续问答修复（2026-10-21）：[WORKBENCH_ANSWER_FIX.md](WORKBENCH_ANSWER_FIX.md)记录当前空检索继续模型解释、无依据标记、格式兼容和具体错误。382/103项与7+18组HTTP通过；下文“资料不足不调用模型”是3B历史行为，学习指南的依据规则不变。

后续状态（2026-10-21）：[Phase4A](PHASE4A_GUIDE.md)已授权实施并部署，当前schema6、355/101项、18组隔离HTTP通过；Studio现增加独立自评/规则建议/受控指南。下文schema5、318/87项及Studio仅有入口属于3B当时结果，旧问答契约保持。

2026-10-20。用户单独批准的 Phase 3B 已实现并在本机部署。工程验证与人工验收分开记录：后端 **318 项**、前端 **87 项**自动测试通过，14 组隔离真实 HTTP 通过；HTTP 中 6 次为**模拟模型**调用，本阶段**真实 DeepSeek 请求 0 次**。浏览器视觉、窄屏及完整人工操作仍待验收，真实模型冒烟等待预算确认。清单版本仍为 0.4.1，不宣称完整 v0.5.0 发布。

本阶段没有新增依赖或外部服务，没有修改正式/候选题库、BKT 参数、评分事实、教学策略、原 tutor_runs 契约或检索算法。40 道候选题仍待人工核验；55 条原评估记录与挑战集 5/15 课程外误检保留。工程测试不证明学习效果或语义检索准确率提高。

## 使用与布局

打开 [本机页面](http://127.0.0.1:8000/)，创建或恢复演示学习标识，进入“资料学习工作台”。该标识只是本机分组，不能作为身份认证。服务仅监听 127.0.0.1。

- 桌面宽度大于 1250px：来源、问答、学习工作室三栏；761～1250px：来源与问答两栏，工作室通过分栏按钮切换；760px 及以下：来源、问答、工作室单栏切换。保持原站蓝白风格，不改动原学习页。
- 课程来源首次默认选中，个人笔记首次默认不选；后续保留明确选择。刷新发现版本变化、删除或索引未就绪时取消该来源，提示重新核对，不自动同意新版本。
- “打开资料”查看当前原文，不会勾选或调用模型。索引失败的笔记仍能打开原文，但不能参与检索。来源版本完整值可通过标题提示或原文抽屉查看。
- 默认仅本地检索。选择模型模式后显示实际配置的服务与模型；没有密钥/模型未启用仍可本地检索。空选择不能提交，后端也拒绝空集合。
- 模型模式包含个人笔记时，列出这些笔记的标题并说明仅发送相关片段，必须勾选**本轮**同意。未同意整轮保留本地；问题、选择或模式变化，以及提交/查看历史均清除勾选。不保存或跨轮复用同意。
- 右栏只展示已有目标、BKT 概况、正式练习和学习历史入口，没有总结、卡片、指南等占位按钮。
- 公式、表格与代码复用唯一安全 MarkdownRenderer；长代码、表格及显示公式在容器内滚动。正文引用和下方引用卡片均可打开原文快照抽屉，支持 Tab、Shift+Tab、Escape 与焦点恢复。

## 后端请求边界与 Agent

新接口独立于原 `/tutor`。`WorkbenchService` 先使用 Phase 3A `KnowledgeService.search` 校验学生、课程、显式来源集合、版本、删除和当前索引，再保存请求声明。每轮不可变 `RequestContext` 保存 `student_id`、`course_id`、`request_id`、来源 ID/版本、逐轮同意和学习状态 revision；模型无法传入或修改这些值。

使用同一 LangGraph 单一 Agent 架构和既有 AgentSettings 调用预算，新增受控工具适配器，没有多智能体调度。模型可选调用：

| 工具 | 能力 |
| --- | --- |
| `retrieve_selected_sources(query)` | 后端重新验证原来源集合；改写检索也仅保留原问题实际获得的引用，不能扩展主题/来源 |
| `get_learning_state()` | 读取本轮已有目标和 BKT 快照，不包含学生标识，不更新任何学习事实 |

默认最多 3 次模型调用（既有可配置范围 1～4）、每次最多 4 个工具、合计最多 8 个工具。多余参数、未注册工具、SQL/文件/身份/来源/BKT 写入请求都被拒绝，终止该模型流程并显示明确原因。

每次外发前重新校验上下文并持久化调用计数。只有本轮检索片段与问题进入模型初始消息，不发送整本笔记、未选资料、旧聊天或历史引用；学情工具只返回当前请求快照。资料明确作为不可信数据，笔记不是权威材料或系统指令。LangSmith 跟踪关闭。最后验证 JSON、答案长度、内联引用与引用列表一致、引用在本轮已取得集合内；失败时回到带状态的本地片段。来源或学习状态在生成途中变化，结果标为 `stale`。

模型提示不能保证解释绝无事实错误；服务端能够强制限制的是工具、来源和引用边界。模型不得评分、更新 BKT 或推进练习，正式练习仍走既有服务。

## API

前缀 `S=/api/v1/students/{student_id}`。现共 **23 个 OpenAPI 路径**，原接口保留。所有 JSON 请求严格禁止未声明字段，工作台请求体同笔记限制为 256 KiB。

| 方法与路径 | 用途 |
| --- | --- |
| `GET S/knowledge/sources` | 沿用 3A 来源目录；仅当前学生非删除笔记与课程资料 |
| `GET S/workbench/capabilities` | 当前服务名称、模型名称、模型/检索开关，不返回密钥 |
| `POST S/workbench/sources/open` | 显式 SourceRef 的当前原文；校验作用域、版本与删除，打开不等于选中 |
| `POST S/workbench/questions` | 本轮本地检索或受控问答，唯一小写标准 UUID request_id |
| `GET S/workbench/runs?limit=20` | 读取最近记录，范围 1～50；不调用模型 |
| `GET S/workbench/runs/{request_id}` | 查询原请求状态及引用快照；不调用模型 |
| `POST S/workbench/runs/{request_id}/note` | 回答另存笔记，无请求体；重复保存返回同一笔记关联 |

问题请求示例（先从来源目录取得真实版本，不填写占位值调用）：

```json
{
  "request_id": "7e8fe6bf-97fa-46a2-a392-322460a7137d",
  "course_id": "machine_learning",
  "question": "梯度下降为什么沿负梯度方向更新？",
  "sources": [{"source_type": "course_material", "source_id": "gradient", "source_version": "从目录返回的完整版本"}],
  "mode": "local",
  "allow_personal_external": false
}
```

`mode=model` 才尝试模型；若含个人笔记且同意为 false，则整轮仅本地。无模型、依据不足、工具拒绝、引用校验失败均有 reason；超时、网络、上游执行/响应无法确认时为 uncertain。空来源/非法字段 422，版本变化或同编号内容冲突 409，跨学生/缺失记录统一 404，索引未就绪 503，超限 413。不要依据错误消息探测其他学生资料。

响应包含问题、状态、答案、实际引用、当时所选来源标题/版本、当前来源状态、不可变请求上下文、模型名称/调用数/token 用量、工具轨迹、原因、时间及已另存笔记 ID。服务端不接受客户端提供答案、引用、身份替换、评分或学情写入。

### 引用与历史保留

统一引用沿用 3A 的 `citation_id/source_type/source_id/source_version/source_revision/chunk_id/title/section`，加上 `raw_md/content_text` 快照、原文字符起止位置/行号、原文与片段 hash、知识点、审阅状态及检索分数。课程引用如 `gradient:1`，笔记引用如 `note_<UUID无横线>_r1:1`。

历史始终显示当时快照；读取时增加 current/modified/deleted/unavailable 状态，不把历史快照送回当前索引。**笔记软删除不是物理擦除**：原始笔记、工作台引用快照和可能的备份保留在本机。当前没有历史删除/永久清除接口、保留期限管理或认证平台；公开/联网部署前需另行设计。

### 请求幂等与中断

SQLite 原子保存 request_id 声明后才可创建模型客户端；同编号同请求只读取结果，内容不同 409、其他学生 404。并发重复请求遇到正在执行的声明，返回 `uncertain/execution_unconfirmed`，不接管模型执行。

状态为 running（内部）、complete、local、uncertain、stale、failed（预留）。GET 将未结束 running 显示为 uncertain；**服务重启不自动重跑模型**。这是保守的重复扣费保护，不声称能在断电/上游无幂等能力时证明模型是否收费。model_calls 是持久化的调用尝试数，不是账单。

浏览器发送前保存请求编号；刷新只 GET 历史/原编号。不确定时必须先查询，不能自动新 POST。若用户明确结束等待，可手动开始独立新请求，界面提示可能另计费。请求编号保护同一轮，不代替预算限制或身份认证。

### 回答另存笔记

复用 NotesService.create 的 UUID/限额/版本/索引机制；内部事务回调将 `workbench_note_origins` 与初始笔记一次提交，竞争保存失败会回滚多余笔记后返回既有关联。原接口不接受此内部参数。同一回答始终关联同一笔记；已编辑返回当前 revision/edited=true，已删除返回 deleted=true，不重建或覆盖用户编辑。

Markdown 附录记录生成时间、请求编号、引用和来源版本；独立来源表保存初始 hash/revision=1、引用 JSON 和时间。笔记详情增加只读 `generation_origin`，编辑器据此区分初版与修订，原始回答保留在工作台历史。保存、编辑均不改变 BKT，索引走 3A 当前版本机制。新笔记不会自动选中或授权模型外发。

## schema4→5 与回滚记录

仅新增两表：

| 表 | 主要字段/约束 |
| --- | --- |
| workbench_runs | request_id 全局主键；student_id FK；course_id；request_hash/request_json；context_json/result_json；status；model_calls；created_at/updated_at；按学生/课程/时间索引 |
| workbench_note_origins | request_id 主键/FK；note_id 唯一/FK；original_revision=1；original_hash；generated_at/saved_at；citations_json |

来源关联保存在受验证的上下文与引用 JSON；笔记软删除保留 UUID，关联不会因删索引丢失。没有重写既有十表，也没有改 tutor_runs。

实际迁移前先停止核实身份后的旧服务，SQLite backup 后核验 user_version、完整性和原十表摘要；EXCLUSIVE 事务再核验原版本/摘要，创建新表、检查原数据和外键后设置版本5。DDL 或检查失败整笔回滚。

- 迁移前代码/旧前端：`data/local/phase3b-prechange-ea87d691.zip`（224 文件），SHA256 `6093d0dcb182ffeb7f7fd78bad592a8e9b16cebbe7c8a9513af3369a079d2482`；未打包 .env 或数据库。
- schema4 备份：`data/local/eduagent.before-v4-0cb86001aa97.sqlite3`；备份含本机笔记，不公开。
- [迁移与回滚证据](../data/evaluation/workbench-migration-v1.json)：完整性 ok，外键无错误；12 学生、14 掌握记录、37 决策、27 作答、5 旧讲解、5 笔记（含软删除）、6 关联和11片段，以及 metadata/index 状态全部逐表摘要相同。
- 独立目录 `data/local/workbench-rollback-check-*` 实测：旧 schema4 代码能打开恢复的备份副本；拒绝 schema5 副本，副本摘要未变。现用库没有执行降级。

回滚流程：停止本项目服务/写入；**先用 SQLite backup 另外保留当前 schema5 库及升级后的新记录**；在新的独立目录恢复上述代码、旧编译页面与 schema4 备份副本，显式配置 EDUAGENT_DB_PATH 指向恢复副本后启动。不要覆盖现库、不要删表改 user_version、不要让旧代码连 schema5。回退到迁移前备份不包含升级后的问答/笔记，必须保留新库用于核对，不能宣称无损自动合并。旧库使用单独端口验证后再切换服务。

## 验证与复现

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
Set-Location frontend
npm.cmd run test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe scripts/verify_workbench.py
.\.venv\Scripts\python.exe scripts/verify_workbench_deployment.py
```

自动测试使用临时数据库；HTTP 脚本在 data/local 创建隔离数据库和随机本地端口，明确替换模拟提供者，重启后用无密钥配置检索。故障/延迟钩子仅存在验收脚本，不在生产 app。部署复验只 GET 健康、API、来源、历史和编译资源，不写学习记录、不调用模型。

- 后端318项：在295项基础上新增23项，含来源隔离、逐轮同意、混合引用位置、合法改写、越权拒绝、预算、模型异常、旧版请求重放、索引/删除/快照、另存/修订元数据、BKT与旧历史不变及迁移回滚。
- 前端87项：原75项保留，加12项选择/草稿/请求恢复、逐轮同意、空选择、学生切换、版本变更、存储故障、引用/键盘/焦点、历史、Studio入口、另存与现有笔记联动。
- [真实 HTTP 14组](../data/evaluation/workbench-http-v1.json)：6次模拟模型、0次真实模型、2次服务启动；覆盖并发重复、超时不重发、生成途中修改、并发保存、软删除历史快照、重启/无密钥、旧检索与评分回归。主库没有写入合成答案。
- [本机部署核验](../data/evaluation/workbench-deployment-v1.json)：127.0.0.1:8000、schema5、23路径、工作台来源/历史与静态资源；不等价于浏览器验收。
- 构建成功；现有 Markdown/KaTeX 使主包仍超过默认500kB警告，没有隐藏警告或引入拆包重构。

此前浏览器工具对 localhost 给出安全限制，本轮未绕过或改用其他自动浏览器渠道。jsdom 和 HTTP 不冒充真实浏览器测试。**少量真实 DeepSeek 冒烟未执行**；需负责人明确请求次数/预算后，再使用合成资料和逐轮同意测试并单独记录。

## 浏览器人工验收清单（未勾选即未完成）

- [ ] 桌面1440px三栏、中等1024px折叠/切换、手机390px单栏；长公式/代码/表格不撑开页面，页面与导航可滚动。
- [ ] 首次课程默认选中，个人默认不选；打开不等于选择；普通切页后保留问题与选择，来源版本变化后提示重选。
- [ ] 课程、个人、混合、空选择分别验证；引用类型与实际选择一致，未就绪项不能勾选，失败索引仍可打开原笔记。
- [ ] 个人笔记模型模式显示标题/服务及片段外发说明；未勾选仍本地；每轮/改问题后同意重置。
- [ ] Tab 到引用并回车打开；核对标题、版本、位置、原始Markdown；Shift+Tab循环、Escape关闭并回到原触发位置。
- [ ] 新窗口编辑/删除笔记后刷新：新查询拒绝旧版本，历史标注修改/软删除且保留旧片段。
- [ ] 断网/超时刷新只查询原请求，不重复生成；错误可理解，开始新请求有明确费用提示。
- [ ] 回答另存→既有笔记编辑器→编辑/保存→刷新恢复→重新选中后可本地检索；重复保存无新笔记；修订标记清楚；原草稿保护仍工作。
- [ ] 工作室正式练习/历史入口有效，掌握度不因聊天或保存笔记改变；原学习、旧助教和资料页面可用。
- [ ] 合成恶意Markdown不执行脚本；真实模型测试另行预算确认并记录，不能把模拟测试算作真实调用。

## 实际文件与剩余边界

精确清单见 [workbench-files-v1.json](../data/evaluation/workbench-files-v1.json)，与迁移前代码摘要比较。核心新增：`agent/workbench.py`、`services/workbench.py`、`api/workbench.py`/`workbench_schemas.py`、后端测试、`useStudyWorkbench.js`、`StudyWorkbench.vue`、`SourceDrawer.vue`、`workbench.css`、前端测试及两份 HTTP 验证脚本。现有迁移、笔记服务/响应、API路由/体积限制、App/API适配器、统一渲染器和文档按需要增量修改。

本机同步请求、词项检索和小型资料限额保持不变。没有跨轮对话记忆、持久作业队列、上游账单核对、历史清理、真实认证、个人语义准确率结论或真人试用结果。工作台问答原始请求和引用快照保存在本地，需按个人数据管理。

Phase 3B 工程交付后停止。下一步由负责人确认浏览器/内容验收及真实模型冒烟预算；Studio 总结/卡片/学习指南、自评、教材PDF、图片识题均需另行授权。
