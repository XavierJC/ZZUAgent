# Phase4B-2：课程知识体系构建

2026-10-23导航更新：知识体系位于“课程构建 → 知识体系”，已确认体系可被[Phase5课程发布](PHASE5_GUIDE.md)引用。仍不自动扩展正式BKT或课件RAG；下文schema8与测试数字为本阶段历史，当前schema11。

后续配置更新（2026-10-22）：用户明确授权启用DeepSeek PDF手动选页入口，现用开关已开启；仍逐轮同意、不自动外发，本次无模型调用，真实视觉接口尚未实测。[启用记录](../data/evaluation/vision-manual-enable-v1.json)与下文阶段验收时“关闭”的历史报告分开保留。

2026-10-22。已完成工程实现、隔离测试、迁移与本机部署。入口为[学习页面](http://127.0.0.1:8000/)的「资料学习工作台 → 课程知识体系」。本阶段没有调用收费模型，没有外发教师课件/笔记，没有修改BKT参数、正式题库、评分、正式先修图或RAG排序。

## 使用方法

1. 创建体系，进入明确标注的草稿编辑模式。增加章节/小节，设置父章节与同级顺序；增加独立概念，编辑名称/Markdown简介。
2. 为概念勾选一个或多个所属章节；按需关联既有正式知识点。相同名字不会合并，概念身份使用稳定UUID。
3. 编辑概念关系列表；被子章节、概念归属或关系引用的节点，须先解除引用才能删除。
4. 保存草稿。勾选“已审阅全部章节、概念及关联”后发布，生成不可变版本；候选先修不会随之变为正式先修。
5. 正式导航只显示已发布版本。继续修改时，从所示发布版本另开草稿；旧版本内容不变，历史版本可切换查看。

从课件生成候选：选择1～3份当前本地解析已完成的课件，生成预览、查看证据，修改候选名称，勾选需要导入的章节/概念，再加入本机草稿。未选父章节或所属章节时会解除相应归属，之后可手动关联。预览不会直接编辑服务器草稿或发布；仍需保存和明确确认。

左侧为体系、确认状态、章节树/搜索和概念列表；中间为编辑、关系与原文证据；右侧为只读学情和候选预览。1200px以下学习状态移到下一行，720px以下全部堆叠；保持蓝白样式。原生表单标签、Tab/Enter/Space可用，树的展开按钮支持左右箭头。真实浏览器/窄屏人工验收仍待执行，不能用jsdom代替。

知识结构草稿与笔记/自评缓存独立，按演示学生及体系保存。普通切换保留草稿；有未保存内容时，体系切换提供保留/放弃/取消。缓存失败会阻止提交和切换学习标识；浏览器关闭提示未保存内容。断网请求保留request_id，刷新只GET回执，绝不自动重发。冲突草稿可保留恢复副本、显式读服务器，再手动恢复和保存；不会自动合并两个版本。候选预览中的名称与选择也可刷新恢复。

## 数据模型与约束

本轮开始时直接只读确认现库为schema7/21表，含1份已解析PDF、3个本地页面；不是从设计文档猜测。现已增量升级为**schema8/27表**。新增6表：

| 表 | 职责 |
| --- | --- |
| knowledge_architectures | 学生/课程作用域、标题、独立revision、最新发布版本及时间 |
| knowledge_entities | 章节/概念稳定身份账本，保留类型与作用域；历史身份不物理删除 |
| knowledge_drafts | 一个体系一个草稿，editing/locked、基础发布版本、严格验证的图快照 |
| knowledge_versions | 不可变发布图、图SHA-256、发布时来源证据快照、版本及时间 |
| knowledge_candidate_batches | 规则版本、候选图、服务端原文证据、未分类位置与时间 |
| knowledge_operations | 学生/课程/request_id复合主键，请求指纹与事务回执 |

小规模图采用版本化JSON完整保存，避免章节/关联分批更新产生半发布。图分别包含chapters、concepts和relations；章节归属不是概念contains关系。身份账本用于后续映射外键，名称不是唯一键。概念可属于多个章节，多个概念可同名；稳定ID不能改作另一节点类型。

图约束：

- 章节父节点必须存在，禁止环和自身父节点，深度≤10；同级按order、UUID稳定排序。
- contains：整体概念→组成概念，有向、禁止自身/重复/环。
- related_to：对称，端点UUID排序规范化，反向提交不能造成第二条重复边。
- prerequisite_candidate：先修候选→后续概念，禁止自身/重复/环；始终未确认，不写原Catalog/教学策略先修图。
- 概念章节关联、关系端点必须存在；删除节点却留下引用会拒绝整次保存。可在一次显式图编辑中同时解除引用与删除节点，旧发布版本/身份不删除。
- 节点来源只能引用本体系的候选批次/item，客户端不能提交任意原文或其他学生证据。

全部写入在同一SQLite事务内执行范围、CAS、图约束及回执校验。同请求ID/相同内容幂等；同ID不同内容409；旧revision不能覆盖新记录。发布再次验证结构与来源，版本/锁定/头指针/回执共同提交。测试SQL故障时全部回滚，没有部分发布。体系revision独立于students.revision和自评revision。

草稿请求≤256KiB，持久图≤512KiB；每学生≤25体系、每体系≤50发布版本/100候选批次；单图≤100章节/150概念/300关系，每节点≤8来源。当前仍只用machine_learning课程，不扩大为多课程平台。

## 候选规则与实际限制

规则版本`heading-and-explicit-concept-v1`，确定性、无模型密钥可运行：

- Markdown使用显式#标题，避开围栏代码和块公式；PPTX使用可靠的真实幻灯片标题，跳过隐藏幻灯片。
- PDF/TXT只采纳“第…章/节”或有层级的“1.2 标题”等明确短标题，不将普通“1. 句子”列表当章节。
- 概念来自“概念/定义/关键词：…”明确标记，或有限课程术语的完整标题匹配。术语涵盖PCA、SVM、树模型等，独立于正式五知识点；不将每个标题或每个术语子串都变成概念。
- 不按同名合并，不从目录顺序推断先修，不自动设置正式知识点关联，不自动关联全部笔记。不确定内容保留未分类，超限明确拒绝而非静默截断。

证据包含文档ID/元数据revision、文件版本/指纹、run/unit及指纹、解析器/规则版本、页或slide或单位位置、原文字符偏移与片段。客户端只持有batch_id/item_id引用。已发布证据保留当时快照，current_status动态区分current、modified、metadata_modified、reparsed、unavailable、deleted。来源变化后，旧候选不能保存/发布为当前来源；用户可重新提取，或明确解除旧来源、转为人工编辑内容并自行审核。

软删除不是物理清除，知识体系中的历史证据也可能继续保留；原件下载经过既有学生作用域和文件版本校验，已删除资料不提供下载入口。当前只读取本地原生解析，不使用视觉转录，不向第三方发送材料。

**实际现存资料验证**：[只读报告](../data/evaluation/phase4b2-existing-material-v1.json)处理现用1份3页PDF，最终规则产生0章节、0概念、3个未分类页面；没有写入现用数据库，也没有保存其私有正文到报告。初步规则曾把普通编号列表提成25个章节线索，复核后收紧规则，没有把该结果当准确识别。该PDF缺少可靠结构元数据，本轮不能声称自动构建成功，需要人工建树或更明确的标题资料。

自建Markdown/PPTX经实际上传、原生解析及HTTP生成候选，证据切片逐一与原文一致；不等于真实教学材料内容准确性已审核。首版不做复杂版面理解、语义知识图谱或OCR扩展。

## 正式知识点只读关联

概念可关联现有正式知识点ID，但不会新增BKT行、题目、评分配置、自评或先修边。学情读取复用GuidanceService同一事务快照，返回真实作答次数/最近结果、自评等级/信心/时间、答题和自评版本以及配置版本。

未关联时items为空，不凭概念名称猜状态；已关联而没有作答证据时objective.probability=null、status=pending_diagnosis，界面显示待诊断。有证据才显示关联正式知识点的概率，明确不是新概念的独立能力测量。规则查询不调用next_action，不偷偷分配练习。正式练习/历史入口只由用户点击现有页面。

## API

前缀`/api/v1/students/{student_id}/knowledge-architectures`。固定课程作用域由服务端决定，不接受客户端身份覆盖。JSON严格类型/额外字段拒绝，UUID须为标准小写。

| 方法/后缀 | 内容 |
| --- | --- |
| GET / POST 空路径 | 列表；创建体系（request_id、name、可选description） |
| GET /requests/{request_id} | 原写入回执，无自动执行 |
| GET /{id} | 体系revision、草稿状态/图/来源、已发布版本清单 |
| PUT /{id}/draft | 原子保存整图：request_id、expected_revision、graph |
| POST /{id}/draft | 从所选发布版本开新草稿：request_id、expected_revision、version；已有编辑草稿时409 |
| POST /{id}/publish | request_id、expected_revision、confirmed=true；明确审阅后发布 |
| GET /{id}/published | 当前已确认版本；从未发布为404 |
| GET /{id}/versions/{version} | 不可变图/证据快照与独立当前来源状态 |
| POST /{id}/candidates | request_id、expected_revision、documents（1～3个document_id/version_id/run_id），只生成批次，不编辑图 |
| GET /{id}/candidates/{batch_id} | 候选、规则版本、证据及未分类位置 |
| GET /{id}/concepts/{concept_id}/learning-state | 默认已发布版本，可指定version或draft=true读取服务器草稿的正式关联 |

新增10路径/12操作，全服务50路径。候选来源依据由批次GET或图详情sources查询；节点/关系编辑采用完整图PUT统一事务，不引入逐节点部分发布。

所有成功写入200，返回architecture_id、revision、replayed，发布另含version、候选另含batch_id。回执是当时结果，前端再GET当前状态。错误含architecture_not_found/candidate_not_found/version_not_found/concept_not_found（404），revision_conflict/request_id_conflict/draft_locked/draft_exists/source_changed/parse_not_ready（409），architecture_cycle/invalid_architecture（422），超大请求413。其他文档异常沿用4B-1错误契约。

图示例（ID替换为真实UUID）：

```json
{
  "name": "机器学习框架", "description": "人工整理",
  "chapters": [{"id":"<chapter UUID>","title":"线性模型","parent_id":null,"order":0,"summary":"","origins":[],"review_status":"candidate"}],
  "concepts": [{"id":"<concept UUID>","name":"损失函数","summary":"","chapter_ids":["<chapter UUID>"],"formal_knowledge_ids":["linear_regression_loss"],"origins":[],"review_status":"candidate"}],
  "relations": []
}
```

## 迁移、部署与回滚

没有新增依赖。部署前8000端口未监听，未终止无关进程。代码归档`data/local/phase4b2-prechange-96851556/code-before.zip`（195文件）；库备份`data/local/eduagent.before-v7-ccc46efc6ba3.sqlite3`。指纹、原21表摘要及副本路径见[迁移报告](../data/evaluation/phase4b2-migration-v1.json)。

schema7→8仅新增6表/索引，不改旧表；备份前后摘要匹配，完整性ok、外键0错误，原件与派生文件指纹不变。隔离测试验证DDL失败仍为7、原21表不变。归档旧7代码能读恢复的7副本，明确拒绝8副本；升级后8库副本保留。没有覆盖旧备份到现用库。

后续新环境启动前若存在7库，先停服务再显式迁移：

```powershell
.\.venv\Scripts\python.exe -m eduagent.storage.migrations --db data/local/eduagent.sqlite3
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

普通API启动拒绝不兼容旧库，不自动改版本。恢复旧版时先停写，保留最新8库的SQLite备份、整个documents目录、当前代码和前端；在新目录从7备份创建工作副本，配套恢复旧7代码并显式指向副本。知识体系新增数据仍保留在8库，旧7无法访问；没有自动无损降级合并。不要只改user_version或覆盖现用库。旧前端入口单独备份，旧哈希资源保留。

## 验证与待人工验收

- 后端**501 passed/42.29s**，含新增25项知识体系测试；前端**131 passed**，新增13项。全量最后一次37.23s，最终按钮禁用/方向文案调整后13项组件复验1.86s通过。构建成功，主JS655.88kB，默认500kB警告保留。
- [知识体系HTTP](../data/evaluation/phase4b2-http-v1.json)17组、2次进程启动、0模型：手建/候选/确认/历史、并发CAS、同名/多章节、来源过期、scope、真实正式评分和自评只读关联。
- 回归HTTP：[课件15组](../data/evaluation/phase4b2-documents-http-v1.json)、[4A指南18组](../data/evaluation/phase4b2-phase4a-http-v1.json)、[工作台14组](../data/evaluation/phase4b2-workbench-http-v1.json)。合计64组，27次仅模拟模型（视觉3/指南9/聊天15），真实模型0、真实课件/笔记外发0。
- [只读部署检查](../data/evaluation/phase4b2-deployment-v1.json)：schema8/27表、原21表一致、50路径、首页/资产与既有资料/指南GET通过，视觉仍关闭，主库未创建合成知识体系或学习记录。
- 首轮HTTP用例误期望2张PPTX都生成候选，实际隐藏slide应跳过，修正为3个总章节并增加隐藏位置断言后通过。PDF规则初轮把列表视作章节的问题已收紧并重新只读验证，未隐去结果或把候选当已审核内容。

以下人工清单**未执行**，没有绕过此前浏览器URL限制，HTTP/jsdom不充作人工结果：

- [ ] 1440/1024/390px：新建体系、多层树/展开搜索、多章节概念、长公式/表格、窄屏堆叠无整页溢出。
- [ ] 完整键盘：章节展开左右箭头、Tab/Space/Enter编辑表单和候选勾选、切换保护按钮、发布确认、焦点可见。
- [ ] 刷新/断网/重开：草稿、候选名称、未确认请求编号恢复；与原笔记/自评草稿互不覆盖。
- [ ] 用有权处理的真实课件逐条核对候选、证据页码/slide/字符位置及同名区分；特别检查PDF未分类内容。
- [ ] 发布v1→另开草稿→改名/移章节→发布v2，旧版不变；过期/删除来源明确标记，不能把历史资料当当前证据发布。
- [ ] 真实教学效果未验证；人工内容审阅、40候选题、原55检索评估与5/15课程外误检继续保留。

## 4B-3准备与阶段边界

可复用稳定的(architecture_id,entity_id,student_id,course_id)身份外键、版本图/graph_hash、候选批次/item引用及document/version/run/unit/位置/证据元数据；未来映射还需核验节点是否存在于所选发布版本、审核状态与来源当前性，不能仅凭身份账本视作当前有效映射。

尚未实现全量片段语义映射、个人笔记自动关联、图谱RAG重排、多源Agent全面改造、正式先修自动生成或BKT扩展。实体账本不是复杂知识图谱数据库，规则候选不是语义抽取准确率证明。本阶段完成后停在4B-2。

实际文件清单与验证摘要见[交付报告](../data/evaluation/phase4b2-delivery-v1.json)。
