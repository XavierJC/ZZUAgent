# v0.5.0 Phase 2：个人笔记管理

后续Phase4A已部署schema6及独立自评/指南，见[PHASE4A_GUIDE.md](PHASE4A_GUIDE.md)；笔记CRUD、草稿、索引及回答另存契约保留。下文各阶段schema编号与无自评描述属于当时记录。

日期：2026-10-20。状态：**前后端、自动测试、现用库迁移及本机 HTTP 验证已完成；浏览器人工验收待完成。** 版本清单仍为 0.4.1，本阶段不是完整 v0.5.0 发布。Phase 3 个人检索须待用户确认。

后续已单独批准并完成 [Phase3A本地检索](PERSONAL_RAG_GUIDE.md)及[Phase3B工作台](WORKBENCH_GUIDE.md)：现用schema5，当前318/87项回归；笔记可显式选择参与问答，外发须本轮同意。笔记详情增加只读generation_origin，原CRUD、草稿与revision兼容。本文disabled/schema3、无个人检索及269/75项属于Phase2当时记录，当前运行/回退以新指南为准；Studio生成未实施。

## 使用与范围

启动现有服务后打开 [学习页面](http://127.0.0.1:8000/)，创建或恢复演示学习标识，进入“我的笔记”。支持新建、打开、修改、保存、删除、标题搜索、知识点筛选，以及 UTF-8 `.md` / `.markdown` / `.txt` 导入。知识点来自原五项课程目录，可关联 0～5 个；同名笔记允许存在。

使用 textarea 编辑 Markdown，预览复用 `MarkdownRenderer.vue`，停止输入约 300ms 后更新。宽屏同时显示原文和预览，1150px 以下切换显示，760px 以下列表与编辑器纵向排列。正文支持 Ctrl+S / Cmd+S 保存；输入、文件选择、关联复选框和对话框有标签，对话框支持 Escape、Tab 循环和焦点恢复。实际布局与辅助技术体验仍须人工验收。

页面显示未保存、保存中、已保存、保存失败、版本冲突或结果待确认。切换笔记、页面或学习标识前，未保存内容可选择保存后继续、保留本机草稿后继续、取消。刷新/关闭页面时请求浏览器确认；浏览器自行决定是否展示提示。草稿按 student/course 放在 localStorage，本机数据不加密，也不是服务器备份。存储不可用时明确提示，不能保存请求编号时不发送写入，需先复制正文。

保存采用 UUID 和 revision。超时或响应丢失时保留原请求，先 GET 对账；确认未生效后才允许手动重试原编号和原内容。保存期间继续输入的文字保留为下一次未保存修改。遇到 409 不自动覆盖，可另存为新笔记，或保留本地副本后读取服务器版本。

笔记不发送给模型、不构建个人索引、不改变课程资料、BKT、评分或规划。`student_id` 是任何人都能输入的演示标识，只有 SQL 作用域隔离，**不具备真实身份认证**。服务继续仅监听本机，不适合直接作为多人公开服务。

## 实现与文件

```text
NotesPanel / NotesDialogs → useNotesWorkspace → api.js
  ↳ MarkdownRenderer（唯一受清理的 HTML 出口）
  ↳ noteStorage（分标识的本机草稿与待确认请求）
FastAPI notes router → NotesService → NoteRepository → SQLite
  ↳ domain/notes（格式、大小、标题、UUID 校验）
  ↳ migrations（备份、事务 DDL、原表摘要与版本）
```

| 文件 | 职责 |
| --- | --- |
| [domain/notes.py](../backend/src/eduagent/domain/notes.py) | Markdown/UTF-8、导入和资源限制；独立于学习算法 |
| [storage/migrations.py](../backend/src/eduagent/storage/migrations.py) | schema 0/1/2→3，备份、事实核验、失败回滚与 CLI |
| [storage/notes.py](../backend/src/eduagent/storage/notes.py)、[services/notes.py](../backend/src/eduagent/services/notes.py) | 作用域 SQL、原文/关联/版本的原子写入、幂等、配额 |
| [api/notes.py](../backend/src/eduagent/api/notes.py)、[note_schemas.py](../backend/src/eduagent/api/note_schemas.py)、[body_limit.py](../backend/src/eduagent/api/body_limit.py) | 学生子资源、严格字段、响应白名单与请求体上限 |
| [NotesPanel.vue](../frontend/src/components/NotesPanel.vue)、[NotesDialogs.vue](../frontend/src/components/NotesDialogs.vue)、[notes.css](../frontend/src/notes.css) | 列表、编辑/预览、导入、关联、确认对话框和断点布局 |
| [useNotesWorkspace.js](../frontend/src/useNotesWorkspace.js)、[noteStorage.js](../frontend/src/noteStorage.js) | 草稿恢复、保存状态、冲突处理、迟到响应隔离 |
| [test_notes.py](../backend/tests/test_notes.py)、[test_notes_api.py](../backend/tests/test_notes_api.py)、[test_migrations.py](../backend/tests/test_migrations.py) | 服务、HTTP、并发、限额和迁移测试 |
| [notes.test.js](../frontend/src/__tests__/notes.test.js)、[notes-ui.test.js](../frontend/src/__tests__/notes-ui.test.js) | 恢复/冲突/导入状态机和 App 集成；复用原前端回归 |
| [verify_notes.mjs](../scripts/verify_notes.mjs) | 通过实际前端适配器请求本机服务，不自动操作浏览器 |

另修改 `storage/sqlite.py` 的初始化、`api/app.py` 路由与错误映射、前端 `App.vue` 和 `api.js`。原测试中 OpenAPI 路径总数更新为 14；旧 schema 1 测试夹具明确移除新表再模拟旧库。未修改学习服务、算法、策略、题库或课程材料。没有新增依赖、外部服务或富文本编辑器。

## SQLite 设计

保留原六张表及所有原始 JSON。schema 3 增加：

| 表 | 实际字段与约束 |
| --- | --- |
| `notes` | id TEXT PK（规范小写 UUID，服务校验）；student_id NOT NULL FK→students.id；course_id CHECK=`machine_learning`；title 1～120 字符；content_md 原始文本、UTF-8 最多 65536 字节；revision≥1；content_hash SHA-256；created_via=`manual/import`；created_at/updated_at UTC；deleted_at 可空 |
| `note_knowledge_points` | (note_id, knowledge_point_id) 联合主键；note_id FK→notes.id，ON DELETE CASCADE；知识点来自 JSON 目录，在服务层校验，不能对 JSON 伪造数据库外键 |
| `note_index_state` | note_id PK/FK→notes.id；status 固定 `disabled`；target_revision≥1；indexed_revision/indexed_hash/indexer_version/error_code 均可空；chunk_count 固定 0；updated_at |

索引为 notes(student_id,course_id,deleted_at,updated_at,id) 和关联表(knowledge_point_id,note_id)。来源 ID 使用稳定的 note UUID；正文 hash、revision、创建方式、时间和预留索引状态支持后续阶段追踪。**没有 note_chunks、向量、索引作业或个人检索接口。** 其他索引状态须 Phase 3 迁移后才允许，当前不能伪造 ready。

创建 revision=1。正文、标题或关联实际变化后 revision+1；无变化请求校验原版本后返回当前记录。正文 SHA-256 不包括标题/关联，所以后续索引新旧不能仅依赖 hash。所有变更在 `BEGIN IMMEDIATE` 事务中完成，并使用 owner/course/revision 条件更新；关联和索引状态更新失败时整体回滚。

删除采用**软删除**：设置 deleted_at、递增 revision，列表、详情和更新不再返回该笔记。这样能拦截延迟到达的原创建请求，避免硬删除后相同 UUID 被重新创建。删除记录、原文及关联仍在本机数据库和备份中；没有恢复、永久清除或自动清理功能，也不能承诺删除后物理擦除。50 篇/1 MiB 配额只统计有效笔记，已删除记录仍会占磁盘。后续如需清理，应保留用于拦截旧请求的独立编号记录并另行设计，不在本阶段扩展。

## API 契约

以下 `S` 表示 `/api/v1/students/{student_id}`。必须先用原 API 创建学习标识；course_id 默认且只能为 `machine_learning`。请求 JSON 使用严格字段白名单，不能提交 student_id、revision、content_hash、HTML、索引状态或评分。JSON 中 expected_revision 必须为正整数；DELETE 查询参数按 HTTP 查询规则解析整数。

| 方法与路径 | 输入 | 返回 |
| --- | --- | --- |
| GET `S/notes` | q≤100（标题字面搜索，转义 SQL 通配符）；knowledge_id 可选；limit 默认20、1～50；offset≥0 | `{items,total,limit,offset}`，按 updated_at DESC/id 排序；列表不含正文 |
| POST `S/notes` | id、title；content_md 默认空；knowledge_point_ids 默认[]；course_id 可选 | 首次201；同 ID、同内容/关联/创建方式且仍为版本1时200；其他编号冲突409 |
| GET `S/notes/{note_id}` | 合法 UUID；course_id 可选 | 200，详情含 Markdown；不存在、删除或其他学生的笔记均404 |
| PATCH `S/notes/{note_id}` | expected_revision；至少一个 title/content_md/knowledge_point_ids，不能为 null | 200，新版本或无变化的原版本；旧版本409 |
| DELETE `S/notes/{note_id}` | expected_revision 查询参数必填 | 204，无 JSON 正文；旧版本409；已删除/不存在404 |
| POST `S/notes/import` | id、file_name、content_base64；title/knowledge_point_ids/course_id 可选 | 201或幂等200；详情加 import_warnings |

详情字段：id、student_id、course_id、title、content_md、revision、content_hash、created_via、created_at、updated_at、content_bytes、knowledge_point_ids、index_status（恒为 disabled）。列表为同一白名单去掉 content_md。标题更新不接受更换所有者、课程或 UUID。

创建示例（UUID 每篇生成一次，重试保留原编号）：

```json
{
  "id": "4a973493-950c-4970-82c4-d29d3346d10c",
  "title": "梯度与损失",
  "content_md": "# 我的理解\n\n$w := w-\\eta\\nabla L$",
  "knowledge_point_ids": ["linear_regression_loss", "gradient_descent"]
}
```

更新示例：`{"expected_revision":1,"content_md":"补充后的 Markdown"}`。错误沿用 `{error:{code,message,...}}`：404 note_not_found/student_not_found，409 revision_conflict，413 content_too_large，422 validation_error/invalid_input，数据库不可用503 storage_unavailable。不将其他用户的正文或字段值放入错误信息。

PATCH/DELETE 超时不代表失败。客户端先按原 ID GET：若内容符合原提交即可确认保存；若版本有其他变化，保留草稿并提示冲突；若删除后 GET404，确认删除。确认仍未生效后可手动重试；对 PATCH 的重复提交最多触发版本冲突，不重复递增。已删除 UUID 的创建重放返回409，不能恢复删除内容。

## 导入、体积和内容安全

- 原文件/每篇正文最多 64 KiB UTF-8；每个学习标识/课程最多 50 篇有效笔记，正文合计 1 MiB。
- 笔记路由 JSON 请求体最多 256 KiB，包含无 Content-Length 的分块请求。base64 约增加三分之一传输体积；极多 JSON 转义也计入该限制。
- 文件名1～200字符，仅基础名，拒绝路径分隔符、Windows 特殊字符、控制字符与首尾空格；不按上传名读取或写入文件系统。默认标题取文件名 stem，超过120字符时截断并提示。
- 服务端严格验证扩展名、base64、真实字节数、UTF-8、NUL/控制字符及明显 PDF/ZIP/图片/ELF 文件头；不信任客户端 MIME，不猜测 GBK。二进制伪装无法靠所有文件头穷举识别；只接受通过严格文本规则的内容，不执行它。
- BOM 移除、CRLF/CR→LF 均返回提示；其他 Markdown 和公式不自动改写。导入失败不产生半篇服务器记录。
- 原始 HTML、脚本或“工具指令”作为普通笔记文字存储。预览经过既有 MarkdownRenderer 的 HTML 禁用、KaTeX trust=false 与 DOMPurify，不执行脚本、代码、工具，不加载 Markdown 图片；详见 [渲染边界](MARKDOWN_GUIDE.md)。

## 迁移、备份与回滚

部署前先停止所有旧应用/CLI 写入，再迁移并启动新版。**旧代码每次连接都会执行 PRAGMA user_version=2，并不会安全拒绝新版本**；不能让旧程序打开 schema 3，也不能仅恢复旧前端后共用新库。

迁移入口（项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m eduagent.storage.migrations --db data/local/eduagent.sqlite3
```

已有1/2版本：先用 sqlite3 backup API 创建同目录、带旧版本和随机后缀的新备份，核验 integrity_check；再 `BEGIN EXCLUSIVE`，复查备份后版本/原表摘要未变化，逐条 DDL，核验六表摘要与外键，最后设置版本3并提交。任一步失败回滚、拒绝启动，保留备份。首次空库直接建 schema3；未知版本或未版本化的非空库拒绝；版本3只检查表与版本，不重复 DDL/备份。备份目录不可写时不升级原库。

本机实际迁移已完成：

- 原库：`D:\ZZUAgent\data\local\eduagent.sqlite3`，2→3。
- 升级前数据库：`D:\ZZUAgent\data\local\eduagent.before-v2-4058e3fc7d1e.sqlite3`。
- 升级前代码/前端归档：`D:\ZZUAgent\data\local\phase2-prechange-85d644af.zip`；不含密钥、数据库或 node_modules。
- [迁移记录](../data/evaluation/notes-migration-v1.json)：原 metadata1、students8、mastery10、decisions26、attempts18、tutor_runs4，六表行数与内容 SHA-256 全部相同，integrity=ok、外键违规0。之后 HTTP 检查新建了独立的合成标识，不将新增验证记录冒充迁移前数据。

回滚步骤：

1. 停止新版服务和其他写入。先对**当前 schema3 库另做 SQLite backup**，保留迁移后新增笔记/答题；同时保留当前源码和草稿。不要覆盖该库或升级前备份。
2. 把升级前代码归档展开到独立目录，将升级前 schema2 备份复制为**新的**回退数据库。核验 integrity_check、user_version=2 和 [迁移记录](../data/evaluation/notes-migration-v1.json) 的六表摘要。
3. 使用旧代码/旧前端和与之匹配的环境，从独立目录运行；明确指向回退库，不指向现用 schema3库。必要的本机模型配置单独提供，密钥不写进归档/命令/日志。
4. 恢复原学习查询和历史核验后再使用；该回退库不含升级后的笔记及新答题。新数据仍在第一步保留的 schema3库中，没有自动合并或破坏式降级工具。

自动测试验证备份可读、DDL中途失败回滚、备份失败时零迁移写入。现场回退核验结果另见 [完整性记录](../data/evaluation/notes-integrity-verification-v1.json)；不能把这些工程检查等同于已经发生过生产回滚。

## 实际测试与复现

| 检查 | 2026-10-20 实际结果 |
| --- | --- |
| 后端完整回归 | `269 passed in 12.04s`，新增44项；BKT、评分、恢复、Agent与来源等原225项继续通过 |
| 前端完整回归 | 6 files / `75 passed`，6.17s；新增28项，原47项继续通过 |
| 生产构建 | 成功；暂存到 data/local/phase2-dist 后部署。主JS553.33kB/gzip193.22kB，CSS63.89kB/gzip16.41kB；保留默认500kB主包提示 |
| 真实笔记 HTTP | [8组检查全通过](../data/evaluation/notes-http-verification-v1.json)：CRUD/恢复、重放、多关联、两次并发仅一成功、跨学生隔离、MD/TXT导入、限额/非法字段、删除防重建、学情不变 |
| 原学习 HTTP 回归 | [六题完成与答错复习/暂停通过](../data/evaluation/notes-learning-regression-v1.json)，答题原事件重试和历史恢复通过；无依据助教反馈0模型调用 |
| 浏览器实际操作 | 未执行；jsdom 交互测试不能替代真实浏览器视觉/键盘验收 |
| 模型/个人 RAG | 本阶段新增模型请求0；个人索引未实现 |

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
Set-Location frontend
npm.cmd run test
npm.cmd run build
Set-Location ..
# 服务启动后；脚本会新建合成标识，报告路径使用新的文件名以免覆盖
node scripts/verify_notes.mjs data/local/notes-http-check-new.json
node scripts/verify_workflows.mjs data/local/learning-check-new.json
```

首轮后端测试暴露 Python 类方法 `list` 与后续类型注解冲突，已采用延迟注解；长参数化用例名称超过 Windows 临时路径限制，已改短用例 ID。随后完整269项通过。前端新增测试首轮完整75项通过。本轮没有付费重测模型，也没有宣称学习效果或人工内容审阅完成。

## 浏览器人工验收清单

以下项目**均未勾选**。此前浏览器自动化被 URL 安全策略拒绝，本阶段没有改用其他浏览器控制或抓取页面绕过。可由负责人在浏览器按以下顺序检查：

- [ ] 建立合成学习标识A，进入“我的笔记”；新建含标题、列表、代码、行内公式、分数/矩阵及块级公式的笔记，预览清晰。
- [ ] 关联两个知识点并保存，看到“保存中/已保存”；刷新后标题、正文、关联和版本正确恢复；仅关联变化也能保存。
- [ ] 导入UTF-8 MD和TXT（含BOM/CRLF），检查内容及转换提示；非法格式、GBK文件、超过64KiB文件有清晰错误且列表无半成品。
- [ ] 修改笔记后打开另一篇、新建、切换导航和切换学习标识；分别检查取消、保存并继续、保留草稿继续；刷新能找回草稿。
- [ ] 两个标签打开同一笔记，依次修改保存；旧标签提示版本冲突，本地文本仍在；“保留副本并读取服务器”和“另存为新笔记”均正确。
- [ ] 使用浏览器离线模式模拟保存失败；恢复网络后先核对服务器，再手动重试；不能重复创建或覆盖较新的版本。
- [ ] 删除确认可取消，确认后列表消失；刷新不恢复。注意这只是软删除，本机数据库与备份仍含内容。
- [ ] 用标识B无法看到A的列表；这是演示范围检查，不是身份认证测试。切换回来，草稿仍属于A。
- [ ] 只用Tab/Shift+Tab访问新建、导入、标题、关联、正文、保存、列表和对话框；Escape取消、焦点返回、Ctrl+S/Cmd+S可用；检查屏幕阅读器标签。
- [ ] 1366px桌面以及760/640/375px宽度，列表/编辑区可用，预览切换正常，长公式/表格/代码内部滚动，不撑开页面。
- [ ] 放入脚本标签、onerror、javascript链接和工具指令文字；只显示原文，不执行脚本/工具，不加载图片或调用模型。
- [ ] 记录保存前后掌握度/答题历史相同；回到学习工作台，答题、助教、资料与历史仍正常。模型实调另行记录，不能将历史实调当作本轮验收。

Phase 2 工程交付到此；待用户确认后再开始 Phase 3。原题库/课程资料人工审阅、课程外误检和独立效果评估继续保留原待办。
