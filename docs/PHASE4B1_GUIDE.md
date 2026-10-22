# Phase4B-1：课程课件解析与管理

后续更新（2026-10-22）：用户明确授权后，现用PDF手动视觉入口已开启；逐轮页码/外发同意和预算限制保持，没有自动发送课件。本次启用请求0、真实视觉API尚未实测，见[配置记录](../data/evaluation/vision-manual-enable-v1.json)。下文默认关闭说明及测试报告是4B-1交付时记录；新环境样例仍默认关闭。

2026-10-21，工程交付。范围是课件原件、解析、位置、版本、恢复与管理界面。**知识树、知识映射和课件RAG尚未实施**；没有改动正式五知识点、BKT参数、题库、评分、自评或教学规划规则。

## 使用入口与当前能力

打开本机[学习页面](http://127.0.0.1:8000/)，恢复原学习标识，进入「资料学习工作台 → 课程课件解析」。选择文件、填写标题和来源说明，确认有权在本机处理后上传。可以查看提取文本、原始位置和提示，下载原件、修改信息、上传新版本、显式重新解析和软删除。

桌面为资料列表/上传与详情两栏；900px以下改为纵向布局，480px以下缩紧间距。使用原生文件输入和带标签的表单，可通过键盘操作；Markdown、LaTeX复用既有渲染净化组件，长文本/公式/原始XML限制在面板内。自动化验证不等于真实浏览器验收，后文人工清单仍待执行。

| 格式 | 实际实现 | 保真限制 |
| --- | --- | --- |
| PDF | pypdf逐页提取；物理页码、印刷页标签、文本与图像存在提示 | 非OCR。扫描页可以为empty；复杂公式、表格和阅读顺序始终需核对，不将文字提取完成标为内容已审核 |
| PPTX | python-pptx，实际幻灯片顺序；标题、正文、分组、表格合并坐标；受限OOXML | 保留OMML原始XML与位置，不能保证转为等价LaTeX；图片、图表、备注等提示未提取，隐藏页有标记；不执行宏或外链 |
| MD/TXT | 严格UTF-8，可带BOM；原文保留 | MD保存章节、代码/公式保护块的字符偏移和行号；TXT保留全文与行号；不猜测GBK或替换错误字符 |

首次没有提供真实教师材料，本轮全部使用自建合成文件。中文PDF夹具使用显式ToUnicode映射，只验证文本提取契约；不证明真实课件的视觉排版、公式准确率或教学效果。

## 可选DeepSeek页面转录

已实现可插拔适配器、PDF选页本地渲染和授权界面，**现用服务保持`EDUAGENT_DOCUMENT_VISION_ENABLED=false`**。本轮真实视觉请求0次，教师资料外发0次；只验证模拟模型的工程行为。DeepSeek真实图像接口兼容性、质量、延迟和费用尚未实测。

以后单独批准预算和材料外发后，才考虑启用：用户每轮明确指定1～3个已解析PDF物理页，并重新勾选外发同意，发送的图片可能包含这些页的全部文字和图像。服务固定为DeepSeek/deepseek-flash；每页至多1次请求、3000输出token，不沿用聊天或笔记授权，不自动续写或重发。PPTX本阶段没有视觉渲染入口。

模型不接收数据库、身份或历史，也没有工具。转录与图示解释分字段保存，固定页码/版本由服务端绑定，输出仅接受严格JSON。视觉结果不能覆盖原件或本地解析，统一标为待核验；超时、网络或上游执行不明保留uncertain，刷新只读原记录。启用开关是运营配置，不能代替本轮同意。

## 存储与版本

SQLite schema7新增6表，原15表结构和数据保留：

| 表 | 用途 |
| --- | --- |
| courses | 独立课程主键，当前只种入machine_learning，不提供多课程平台 |
| course_documents | 演示学生/课程作用域、标题、来源、材料角色、本地使用权确认、revision、文件与解析头指针、软删除 |
| document_versions | 不可变原文件版本、SHA-256、实际格式/大小、原文件名、服务端存储键 |
| document_parse_runs | local/vision任务、generation、预期revision、claim token、状态、原件版本、解析器版本、选页/授权、调用/用量、派生物指纹 |
| document_units | 页/幻灯片/文本单位，原文、Markdown、独立模型解释、位置、块/公式证据、提示及内容指纹 |
| document_operations | 学生/课程/request_id复合主键、请求内容指纹与回执 |

组合外键约束文档、版本、任务、单位处于相同作用域。`student_id`只是本机演示隔离，不是真实身份认证。`teaching_material`是资料类别，`imported_unverified`不代表教师身份或内容正确性。

默认文件目录为数据库旁的`*.documents`，现用为`data/local/eduagent.documents/`。`originals/<document UUID>/<version UUID>.bin`保存原字节；`derived/<run UUID>/<artifact UUID>.json`保存规范提取结果；`staging/<UUID>.bin`仅作临时处理。目录不作静态挂载，下载须经过相同学生作用域并校验原件指纹，以attachment/nosniff返回。文件名仅作展示，磁盘路径由服务端生成。

新文件增加file_revision、revision和parse_generation；重新本地解析增加revision和generation；修改标题只增加revision。保存新版本立即切换解析头，旧任务发布前重查文件版本、generation、token及删除状态；视觉任务额外检查revision。旧结果可以作为明确标注的历史查看，不能当作当前资料。4B-1的`index_status=not_implemented`，不会混进原课程/笔记检索。

本地队列落库，一次一个受限进程。重启仅恢复一次中断的本地任务，超过次数标失败、等待手动重试；模型任务绝不自动恢复执行。启动检查当前原件及已完成派生物的hash，缺失/损坏标失败并停止展示其有效单位，原文数据库记录不删除，可对完好原件手动重建。

同request_id和相同内容重放回执，不新建任务；同ID不同内容409；旧revision不能覆盖新内容。回执是操作当时快照，客户端随后GET当前详情。软删除关闭正常列表、详情、原件入口，不物理清除原件、历史、回执或备份，保留配额仍计入。

文件系统与SQLite不能组成单个原子事务。常规异常会回滚数据库并清理本次未提交文件；断电可能留下未引用原件/派生物/临时文件，均不进入当前视图。首版没有自动物理回收或全盘孤立文件修复工具，需停服务审计后处理，不应手动删除已登记原件。

## API契约

前缀：`/api/v1/students/{student_id}/documents`。所有UUID须为标准小写；JSON严格类型，拒绝额外字段。上传为multipart，一个`file`与一个JSON字符串`metadata`；后端再次核验文件、版本、作用域与授权。

| 方法/后缀 | 功能 |
| --- | --- |
| GET 空路径 | 正常资料列表，limit≤25、offset |
| POST 空路径 | 新建，metadata含request_id、title、local_rights_confirmed=true；可含course_id、material_role、source_note |
| GET /capabilities | 格式/限额、视觉开关/服务/预算；retrieval_connected=false |
| GET /operations/{request_id} | 操作回执；刷新恢复只调用GET |
| GET /{id} | 当前详情和本地解析状态 |
| PATCH /{id} | request_id、expected_revision，至少修改title/source_note之一 |
| DELETE /{id} | JSON含request_id、expected_revision；幂等软删除 |
| GET /{id}/versions | 保留文件版本，不返回内部存储键 |
| POST /{id}/versions | multipart更新；metadata含request_id、expected_revision、可选course_id |
| POST /{id}/parse | request_id、expected_revision，创建新本地任务 |
| POST /{id}/vision | 上述字段及version_id、pages、consent_external=true；需服务已启用 |
| GET /{id}/parse-runs | 最近30条解析记录 |
| GET /{id}/parse-runs/{run_id} | 原任务状态，不重复执行 |
| GET /{id}/units | 默认当前本地任务；可带run_id、limit≤20、offset查看历史/视觉单位 |
| GET /{id}/original | 默认当前文件，可带version_id；私有原件附件下载 |

新增11条OpenAPI路径、16个操作；全服务40条路径。新上传/解析/视觉任务202，回执重放200；修改/删除200。常见错误：422字段/编码/文件无效、415类型/MIME不匹配、413大小/配额、409版本/请求ID/重复文件、404当前作用域不可见、503视觉未启用或存储不可用。损坏PDF/PPTX可在已登记后异步解析失败，查询任务取得固定error_code，原件保留。

单位包含`id, ordinal, kind, title, text, content_md, interpretation_md, origin, location, blocks, warnings, content_hash`，并关联run/document/version。PDF位置是page_number/page_label，PPTX是slide_number/slide_id及shape/段落/单元格证据，MD/TXT是行号与块偏移。本阶段不是工作台citation，之后4B-4才扩展引用及来源选择契约。

## 资源边界与依赖

- PDF/PPTX20MiB，MD/TXT2MiB；上传总请求至多20MiB+256KiB，无Content-Length仍逐块限制；一个文件/一个元数据字段，其他资料JSON请求256KiB。
- 至多200页/幻灯片、100万提取字符、8MiB派生JSON。每学生25份有效文档，所有保留原件250MiB、派生物100MiB。软删除不自动释放。
- PPTX≤4096条目、解压实际/声明总量100MiB、单XML8MiB、压缩比100:1；禁止重复路径、穿越、宏、嵌入OLE、加密条目、DTD/实体；不解包到任意路径，不抓取外链。
- 本地墙钟60秒、CPU30秒、内存512MiB。Windows Job Object在解析开始前启用；允许venv启动器及解释器共2个进程。限制设置失败则停止。其他系统有RLIMIT分支，本轮只验证Windows/Python3.12.8。
- 一次一个任务、一个API worker，目录文件锁拒绝第二协调器。任务子进程不继承模型密钥和数据库连接。进程限制是资源控制，不能当作完整操作系统沙箱或公开上传服务的安全认证。

项目环境新增并固定：pypdf6.21.1、python-pptx1.0.2、python-multipart0.0.32、lxml6.1.3、defusedxml0.7.1、pypdfium2 5.14.0、Pillow13.0.0、XlsxWriter3.2.9。见`backend/requirements-documents.lock`与documents可选依赖组。已核对官方PyPI元数据、安装并通过`pip check`；未执行独立漏洞扫描。许可涉及BSD/MIT/Apache/PSFL及pdfium捆绑NOTICE，分发时保留各发行包许可，不能概括为单一许可证。

新环境安装及显式迁移（迁移前停写）：

```powershell
.\.venv\Scripts\python.exe -m pip install -e './backend[api,dev,agent,documents]'
.\.venv\Scripts\python.exe -m eduagent.storage.migrations --db data/local/eduagent.sqlite3
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

已有库版本不匹配时API启动拒绝，不在普通请求中静默升级；新空库可初始化。独立CLI迁移仍为显式运维入口。`.env.example`给出视觉默认关闭配置，未修改现用密钥。

## 本次迁移与回滚记录

部署前8000端口未监听，没有终止无关进程。代码归档`data/local/phase4b1-prechange-fbe47f37/code-before.zip`；现库备份`data/local/eduagent.before-v6-d6cc03e2934d.sqlite3`，指纹和原15表摘要见[迁移报告](../data/evaluation/phase4b1-migration-v1.json)。schema6→7只新增6表及索引、1课程行；原15表摘要一致、integrity=ok、外键0错误。备份指纹已验证，原非local数据文件未变。

独立副本验证：归档旧schema6代码可以打开还原的6库，明确拒绝7库；保留了一份升级后7库副本。测试DDL故障后事务仍为6且原表摘要一致。**未把旧备份覆盖现用库。**

如需回退：停服务，先用SQLite backup保留最新7库，并保存整个documents目录、当前代码和前端；另建隔离目录，从6备份创建新的工作副本并配套恢复旧6代码/旧前端；启动时明确指向这个副本，验证后切换。新增文档/解析仍保留在7库与文件目录，旧版不能读取，不存在自动无损降级合并。不得在写入时直接复制活动数据库或只改user_version。旧前端入口已另存frontend-index-before.html，旧哈希资源保留。

## 验证结果及人工清单

- 后端 **476 passed /39.13s**（原428+新增48），前端 **118 passed /5.68s**（原107+新增11），构建通过；主JS622.88kB，仍有默认500kB包体警告。
- [课件真实HTTP](../data/evaluation/phase4b1-http-v1.json)：15组、3次服务启动、3次模拟视觉调用；真实模型0、真实材料外发0。
- [4A回归HTTP](../data/evaluation/phase4b1-phase4a-http-v1.json)：18组、9次模拟模型；[原工作台HTTP](../data/evaluation/phase4b1-workbench-http-v1.json)：14组、15次模拟模型。合计47组，独立报告，不改写历史结果。
- 自动覆盖四格式/页码/公式/图像提示、原字节/作用域、幂等/冲突/更新/软删除、失败重试/重启/指纹损坏、发布版本竞争、模拟视觉同意/超时/历史、资源限额、流式请求上限、恶意Markdown净化、原学习流程回归。
- [部署只读检查](../data/evaluation/phase4b1-deployment-v1.json)：8000服务、首页/资源、40路径、schema7/21表、原15表保持、本地解析依赖、视觉关闭通过。主库没有合成课件或学习写入。
- 首轮失败已修复并重跑：pytest原始字节参数导致Windows长路径；venv启动器需2进程的Job限制；文件锁读阶段需捕获占用；HTTP恢复夹具应创建真正未完成任务；迁移审计脚本编码名笔误发生在写库前。未删断言或隐去失败。

以下**未执行**，不能用jsdom/HTTP替代：

- [ ] 1440/1024/390px真实浏览器：上传、进度刷新、列表/详情、长公式/表格/代码横向滚动、无整页溢出。
- [ ] 完整键盘：文件选择、表单、记录切换、原件下载、软删除确认，焦点可见。
- [ ] 有权使用的真实PDF/PPTX逐页对照：中文、公式、表格、页码/slide号与复杂图像提示；人工记录误差。
- [ ] 浏览器刷新/断网/重开：上传回执恢复、不自动重发；笔记/自评草稿保持原行为。
- [ ] 真正视觉API：另批小预算与外发范围后，用合成页测试质量、费用与超时；不能据模拟测试宣称识别精准。

原55条检索评估及5/15课程外误检保留；40道候选题仍待人工审核，现用原10题。没有新增学习效果结论。本阶段交付后停在4B-1，不自动进入知识树、映射、三来源RAG或图片习题识别。

实际文件清单和工程验证摘要见[phase4b1-delivery-v1.json](../data/evaluation/phase4b1-delivery-v1.json)。
