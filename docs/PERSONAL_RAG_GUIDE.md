# v0.5.0 Phase 3A：本地个人检索与来源约束

后续Phase4A已完成schema6及自评/指南，见[指南](PHASE4A_GUIDE.md)。本地检索接口、来源/版本边界与分块算法保持，指南仍逐轮取得个人片段外发同意；下文3A/3B的schema与功能范围为阶段历史。

后续状态：用户已单独批准并完成 [Phase3B资料工作台](WORKBENCH_GUIDE.md)，当前schema5、318/87项回归；个人片段仅在本轮明确同意后才可发送模型，另存笔记与历史快照已实现。本指南的schema4、无Agent/无界面和295/75项记录属于Phase3A当时范围，不代表当前状态。原3A接口保持兼容。

日期：2026-10-20。状态：**实现、schema3→4迁移、295项后端/75项前端回归、构建及隔离真实HTTP验证已完成。** 本阶段没有模型请求，没有三栏工作台、个人笔记Agent问答或Studio。清单版本保留0.4.1，不宣称完整v0.5.0发布。

## 功能与使用入口

已保存笔记自动构建派生片段；支持课程、个人笔记及组合的显式来源检索。原笔记CRUD、课程检索和学习API保留，新增接口可在 [本机API文档](http://127.0.0.1:8000/docs) 调试。笔记页只补充当前索引状态说明，没有提前增加资料工作台。

本地预览、保存、分块、重建和检索不调用DeepSeek，不上传笔记，不执行脚本或笔记内的工具指令。匿名student_id只划分本机演示作用域，不具备账号认证；版本标识也不是访问凭证。

## 索引与保存机制

```text
笔记原文保存事务：校验revision → 保存原文/关联 → 删除旧片段 → pending
事务提交后：claim构建编号 → building → 有界分块
发布事务：核对owner/revision/hash/未删除/build_token → ready或empty
查询：验证所选来源 → 读取当前片段 → 独立TF-IDF计算 → 再验证版本 → 返回引用
```

原始Markdown是权威数据。笔记标题、正文或关联变化均使revision递增；旧片段在同一保存事务中立即删除，即使后续索引失败，也不会回退返回旧内容。无变化保存不递增版本。

分块器识别ATX标题、空行段落、反引号/波浪号围栏代码、独立行`$$`及`\[...\]`数学块。优先合并相邻段落，长普通段落以约800字符窗口、100字符重叠切分，保护常见行内数学和反引号片段；实际重叠会受段落及保护边界影响。这些是初始工程参数，不是实验得到的最优值。

原文片段、Python Unicode字符偏移、LF行号、标题和章节路径一起保存。`raw_md == content_md[start_offset:end_offset]`；字符位置不等同UTF-8字节位置。`content_text`仅去掉部分标题/围栏标记用于词项检索，不生成HTML。公式源码保留。

这是有界块识别器，不是完整CommonMark解析器；Setext标题、复杂嵌套及特殊数学环境不作完整语法保证。不能安全分割的代码/数学块超过8192字符时明确失败并保留原文；单篇最多256片段。没有为了成功而静默丢弃超长代码或正文。

个人检索使用标准库稀疏TF-IDF：复用原课程分词、log TF、平滑IDF、归一化余弦、0.12阈值和有效词组检查，不引入FAISS个人文件或新依赖。每次仅用当前学生且明确选中的片段建立词表，不设跨请求缓存。单次最多256片段、8192词项，超限413并要求缩小来源范围。

课程仍用原FAISS和课程专属词表/IDF。新增可选source_ids先限定候选向量，再召回；默认旧调用与全部课程来源保留原结果。个人词条不进入课程索引。组合模式分别取至多5条，固定等权RRF(k=60)排序后截取top_k；原分数保留，不能把两种TF-IDF得分当作统一可信度。

## 状态、失败和重启

| 状态 | 含义与处理 |
| --- | --- |
| disabled | 迁移前预留状态，或软删除后的停用状态；有效笔记在启用检索的启动恢复中处理 |
| pending | 原文已提交，当前版本尚未发布片段 |
| building | 正在构建；build_token区分同一revision的并发任务 |
| ready | 已发布当前revision/hash/分块器版本的片段 |
| empty | 原文无可索引词项，片段数0，不能据标题伪造正文依据 |
| failed | 原文仍可读取；公开固定error_code，可显式重试 |

片段构建不占用原文保存事务。发布和失败写入都检查构建编号及当前笔记版本；新保存、删除或另一次重建会使旧任务失去发布资格。旧失败也不能把新任务标成failed。索引异常不把原始异常文字或正文放进错误信息。

服务启动时，恢复有效笔记的disabled/pending/building，以及版本或分块器落后的ready/empty；失败状态不无限自动重试。已发布片段保存在SQLite，向量按请求重建，因此进程重启不依赖内存缓存。派生片段缺失或与原文切片/hash不一致时拒绝检索，需显式重建。

删除仍为软删除，原文与删除记录保留；派生片段立即移除，正常来源目录和检索均排除。未实现永久清除或历史笔记版本库。

## 配置与运行

项目根目录：

```powershell
# 新环境安装方式；现有环境已具备这些固定版本，本轮未重新安装
.\.venv\Scripts\python.exe -m pip install -e './backend[api,retrieval,dev]'

# 不提供密钥也可运行本地检索；以下只改变当前终端环境
$env:EDUAGENT_AGENT_ENABLED = 'false'
$env:EDUAGENT_RETRIEVAL_ENABLED = 'true'
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

新增`EDUAGENT_RETRIEVAL_ENABLED=true/false`，默认true，与Agent开关独立。关闭Agent不关闭本地检索。Agent启用且需要模型服务时仍沿用原密钥要求，Phase3A没有修改该配置或主动发送请求。

新增`retrieval`可选依赖组合，复用已有FAISS CPU1.15.1、NumPy2.5.4，不增加包或更换版本。个人索引仅需标准库；缺少课程检索依赖时，个人检索仍可用，课程请求明确503。health.retrieval_available表示课程索引可用状态；来源列表另提供检索开关状态。完整Agent安装可继续使用原`[api,dev,agent]`组合。

## API契约

`S = /api/v1/students/{student_id}`，课程固定`machine_learning`。请求采用严格字段与类型，不接受客户端HTML、SQL、索引状态或其他学生标识；知识检索与笔记路由请求体最多256KiB。

| 方法与路径 | 输入 | 返回 |
| --- | --- | --- |
| GET `S/knowledge/sources` | course_id可选，默认machine_learning | course_id、retrieval_enabled、items；只列现有课程来源与当前学生未删除笔记 |
| POST `S/knowledge/search` | query1～1000字符；sources1～55个；top_k默认3、1～5；course_id/knowledge_id可选 | 已选来源、当前片段和结构化引用、model_calls=0、检索/融合策略 |
| POST `S/notes/{note_id}/reindex` | `{"expected_revision":正整数}` | 当前索引状态、目标/已索引版本、hash、分块器版本、片段数、固定错误码 |

来源目录每项包含source_type、source_id、source_version、source_revision、content_hash、title、knowledge_point_ids、review_status、index_status、error_code。个人来源类型为`personal_note`，课程为`course_material`。个人review_status固定`personal_unverified`，不冒充课程资料。

source_version由后端生成：笔记为revision与原文SHA-256组合；课程为来源元信息与原文摘要的组合。客户端从列表取值原样回传，不自行拼造。课程原文件或manifest在服务运行期间变化时要求重启，避免课程版本与启动索引不一致。

示例流程：先用原API创建/恢复学习标识，再创建笔记、GET来源目录，最后提交选择：

```json
{
  "query": "梯度下降如何更新参数？",
  "sources": [
    {
      "source_type": "personal_note",
      "source_id": "从来源目录取得的笔记UUID",
      "source_version": "从来源目录取得的版本"
    }
  ],
  "top_k": 3
}
```

sources也可只含课程来源，或混合两类。空来源、重复来源和非法字段422；未知/外学生/已删除来源统一404；版本不一致409 source_changed；任一所选笔记未就绪或派生数据不完整503 index_unavailable；体积或索引预算超限413。不会悄悄跳过失败来源、改查全库或使用未选择的课程兜底。未索引失败也不是“没有匹配结果”。

返回引用包括citation_id、source_type/source_id/source_version/source_revision、完整原文content_hash、片段chunk_hash/chunk_id、标题/章节、知识点、审阅状态、raw_md/content_text、start/end_offset、start/end_line、retrieval_score/fusion_score。笔记引用如`note_<uuidhex>_r2:1`；课程保留`gradient:2`等原标识。没有Phase3B的引用抽屉、历史问答快照或模型引用接入。

所有所选来源在检索前检查owner/type/ID/version/删除/索引状态，返回前再次检查，包括本轮没有命中结果的来源。原文位置与片段hash另行核验。版本标识只能保护并发一致性，不能证明请求者身份。

原`GET/PATCH/DELETE S/notes...`、导入和`POST /api/v1/materials/search`不更换契约；笔记响应index_status从单一disabled扩展为真实状态。旧课程搜索不接收个人来源；现有Tutor仍只读取课程资料。

## 数据表、迁移和回滚记录

schema4新增`note_chunks`：chunk_id主键、note_id外键、student_id外键、course_id、revision、content_hash、ordinal、title、section、字符偏移/行号、raw_md、content_text、chunk_hash、indexer_version；(note_id,revision,ordinal)唯一，按student/course/note/revision建索引。

`note_index_state`在显式事务内复制重建，放宽状态和chunk_count约束，增加build_token、building_started_at；原九表旧列摘要必须完全一致后才提交。原notes/关联及学习表不重写。版本4连接不重复DDL；旧Phase2代码遇到4会拒绝，不得让更早写回版本号的程序连接新库。

实际记录：

- 升级前代码归档：`D:\ZZUAgent\data\local\phase3a-prechange-8ffd16d4.zip`，185文件，不含密钥或数据库。
- schema3备份：`D:\ZZUAgent\data\local\eduagent.before-v3-0f3561f44a87.sqlite3`。
- [迁移记录](../data/evaluation/personal-rag-migration-v1.json)：原九表摘要一致；12学生、27次答题、14条掌握度、37条决策、5条讲解、5篇含删除记录的笔记及6个关联均保留；完整性ok、外键违规0。
- [部署后完整性与回退探测](../data/evaluation/personal-rag-integrity-v1.json)：六张学习表、notes和关联表逐字内容摘要仍相同；仅派生状态按启动恢复变化，两篇有效笔记ready、11片段。
- 旧代码在独立目录成功读取schema3备份副本，且拒绝schema4副本；没有对现用库执行回滚。验证目录`data/local/personal-rag-rollback-check-24f0ec7b`。
- 本机服务实际PID25404，启动器28268；日志`data/local/personal-rag-api-bd63e201.stderr.log`。仍只监听127.0.0.1:8000，清单0.4.1，OpenAPI17路径。

迁移入口：`.\.venv\Scripts\python.exe -m eduagent.storage.migrations --db data/local/eduagent.sqlite3`。已有版本先sqlite3 backup、一致性核验，再排他事务复查、逐条DDL、外键/摘要检查及版本更新；失败回滚，备份不可用时不迁移。

回滚先停写并另做当前schema4库的SQLite备份，保留升级后数据；将代码归档与schema3备份副本放在独立目录，明确指向回退库和匹配的旧前端。不要覆盖现库或备份，不做删表降级。备份含用户笔记原文，须按本机私有数据保存；回退副本不含升级后新增内容。更详细操作原则沿用 [笔记回退说明](NOTES_GUIDE.md)。

## 实际验证与恢复报告

| 检查 | 实际结果 |
| --- | --- |
| 后端完整回归 | **295 passed in11.19s**，比Phase2增加26项；算法/评分/Agent/历史/笔记回归继续通过 |
| 前端回归 | **6 files /75 passed，14.82s**；本阶段未引入工作台交互 |
| 构建 | Vite退出0；主JS553.41kB/gzip193.26kB，CSS63.89kB/gzip16.41kB；保留500kB主包提示 |
| 独立真实HTTP | [13组全通过](../data/evaluation/personal-rag-http-v2.json)：明确空模型密钥、CRUD检索、来源限制/隔离、空集合、失败保文/重试、版本竞态、两次进程启动及恢复、原学习闭环 |
| 课程开发集 | [30例复验](../data/evaluation/personal-rag-course-dev-v1.json)：Hit@1=24/25、Hit@3=25/25、MRR@3=.98、课程外空结果5/5，与原报告逐例相同 |
| 课程挑战集 | [25例复验](../data/evaluation/personal-rag-course-challenge-v1.json)：Hit@1=9/10、Hit@3=10/10、MRR@3=.95、课程外空结果10/15；5个误检完整保留 |
| 新增模型调用 | **0**；个人数据只在本机测试/现用库内索引，没有个人RAG问答接入 |

个人检索的26项新增自动用例与HTTP工程场景不等于独立语义准确率评估。课程55例仍是待审开发集。旧关键词与新正文若共享“算法”等词仍可能匹配；应核验来源/版本/原文，不能用关键词黑名单或缩小来源后空结果冒充语义能力提升。

失败和竞态的具体证据：

- 超8192字符受保护代码块：HTTP创建仍201、原文可GET、索引failed，检索503；重试失败仍保留原文。
- 临时失败状态：只在独立测试库注入，真实reindex请求成功恢复；不是发生过真实服务故障的证据。
- 延迟构建：只在测试服务注入暂停钩子，真实HTTP并发保存获胜，旧重建409且不能覆盖新片段。
- 同revision不同构建编号、旧失败覆盖新任务、删除竞争和返回前版本变化：自动测试拒绝过期结果。
- 中断恢复：测试库模拟building和丢片段，实际停止并重启进程后检索恢复；新进程显式无模型密钥。
- 原学习流程：独立库完成六题finish、原事件重放、两次答错后题量不足暂停及历史恢复；不向现用库写合成成绩。

首轮新增测试有夹具重复关键字及把共享词误当成旧内容必然不可匹配的断言，已修正夹具和版本/原文断言，没有增加语义黑名单。HTTP测试早期的Windows子进程stdin控制不兼容造成健康探测超时，改为仅测试目录内的文件关闭信号；扩充原学习场景时又修正一处合成错答选项。最终自动测试和13组HTTP均通过，未隐藏上述失败。

复现：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
.\.venv\Scripts\python.exe scripts/verify_personal_rag.py --output data/local/personal-rag-http-new.json
.\.venv\Scripts\python.exe -m eduagent.retrieval.evaluate --output data/local/course-dev-new.json
.\.venv\Scripts\python.exe -m eduagent.retrieval.evaluate --dataset data/evaluation/retrieval-challenge-v1.json --output data/local/course-challenge-new.json
Set-Location frontend
npm.cmd run test
npm.cmd run build
```

HTTP脚本自己创建临时目录/数据库和短期本机服务，完成后关闭本次服务；保留测试库和日志以便检查。报告采用新文件名，不覆盖历史结果。测试用延迟钩子不进入生产create_app。

## 实际文件清单

逐文件状态见 [机器可读变更清单](../data/evaluation/personal-rag-files-v1.json)，对照本阶段开始前归档列出新增/修改文件；忽略的部署产物单独记录。

新增：

- `backend/src/eduagent/retrieval/lexical.py`、`note_chunks.py`、`personal.py`。
- `backend/src/eduagent/storage/personal.py`、`services/note_index.py`、`services/knowledge.py`。
- `backend/src/eduagent/api/knowledge.py`、`knowledge_schemas.py`。
- `backend/tests/test_personal_rag.py`、`test_knowledge_api.py`、`test_personal_migration.py`。
- `scripts/verify_personal_rag.py`、本指南及`data/evaluation/personal-rag-*.json`验证记录。

修改：

- `storage/migrations.py`：schema4与九表保留核验；`storage/notes.py`、`services/notes.py`：事务失效及保存后索引。
- `retrieval/index.py`：共享词项函数导入、候选来源约束，旧默认行为经55例验证。
- `api/app.py`、`api/settings.py`、`api/note_schemas.py`、`api/body_limit.py`、`config.py`：路由、索引状态、恢复、解耦与限额。
- `backend/pyproject.toml`、`.env.example`：仅新增retrieval组合与非密钥开关。
- 原测试`test_api.py`、`test_web.py`、`test_notes.py`、`test_notes_api.py`、`test_migrations.py`、`test_tutor.py`：健康/路径/真实索引状态和旧schema夹具随有意变更更新。
- `frontend/src/components/NotesPanel.vue`：索引状态与本地接口使用说明。
- `AGENTS.md`、`README.md`、项目上下文、开发计划、旧设计及API/Web/笔记/Markdown指南：同步实际阶段与兼容说明。

正式/候选题库、BKT参数、学习服务、评分规则、教学策略、Agent工具与前端依赖均未改；未初始化Git。索引不是模型训练，没有真实学习效果结论。

## 限制及Phase3B前确认事项

- 当前通过本地API检索；三栏工作台、勾选界面、引用抽屉、个人问答、回答转笔记及Studio均未实现。
- 词项匹配不理解公式等价、同义改写或课程外意图；个人内容非权威，课程内容也仍待审。
- 无跨请求缓存/任务队列，保存后同步分块；大段原子块和超预算选择会明确失败。尚无独立性能基准或个人语义评测集。
- 来源目录包含个人标题等元信息，只适合本机受控演示；没有认证、多人联网安全或物理擦除承诺。
- 浏览器视觉/完整键盘/窄屏人工验收仍待完成，本轮没有绕过既有浏览器限制。

Phase3B需另行确认：工作台布局与来源默认选择；个人片段外发的明确提示与本轮同意；独立问答响应/历史与引用快照；资料变化后的回答处理；回答另存笔记的生成来源；是否仅保留Studio入口而继续延后生成。没有该确认不继续编码。
