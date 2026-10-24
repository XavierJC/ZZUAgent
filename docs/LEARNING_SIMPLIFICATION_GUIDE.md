# 学习主流程收敛：使用与接口（2026-10-24）

本轮按用户“开始下一步开发”实施：资料学习、练习、学习进度三个学生主入口；原课程管理、正式诊断、笔记和历史仍可访问。目标是上传后可问、识别后可练，保留正式测评和资料外发边界。

## 从哪里开始

打开 `http://127.0.0.1:8000/#/study`，恢复原学习标识。

- **资料学习**：左侧添加PDF/PPTX/MD/TXT，解析就绪后勾选提问；中间回答，点击 `[1]` 等编号查看原文及文件位置；右侧只保留下一步建议和学习入口。个人笔记默认不选。模型参数放在“回答设置”，自评和指南放到学习进度。
- **练习**：点击“导入习题”，选择上传文件、已有资料或粘贴文字，点击“导入并自动整理”。结构完整的题自动进入普通练习；异常进入“需要处理的题目”。现有旧草稿可以点击“整理已有题目”批量处理，每批最多50题，不需要逐题勾选。
- **学习进度**：查看客观学情与规则建议；自评、学习指南及其历史分别折叠。保存和刷新不分配题目。

“课程管理”和“更多工具”默认折叠。原 `#/learn` 正式学习、`#/notes` 笔记、`#/history` 历史及管理深链接保持；从普通入口进入学习空间不自动分配正式题，明确进入正式学习后沿用原分配规则。

## 习题自动整理

流程：原文件/文字保存 → 受控Agent识别 → 原文依据和结构检查 → 去重 → 可练或待处理。复用现有LangGraph原题提取和一次结构复核，不执行文档中的指令。

- 初版每次最多3个相邻页，默认前3页；其他页不会发送。后续页面需从已有资料选择新范围。文件/图片与粘贴文字均支持；模型未配置时可在识别设置选择本地规则，本地不是OCR。
- PDF/图片可同时发送指定原页，帮助还原公式和版面；必须在本轮明确同意外发。页面/文字/身份变化后旧授权失效，刷新不自动重发付费请求。
- 已识别题型、完整题干、有效选项和无未解决依赖的题可练；未知题型、缺失图、无法辨认或结构疑点留作草稿。缺少答案不阻止作答，但不编造答案。
- 新题标记“自动整理 · 未人工核验”，`reviewed=false`、`answer_confirmed=false`，不伪造人工审核。已有草稿的批量整理是结构规则检查，不是重新调用AI。修正稿仍需显式接受，不能借批量整理跳过原接受流程。
- 同一请求幂等；重复识别相同题目复用已有可用题，不覆盖用户编辑。冲突答案保留待处理；已归档/来源失效题不会让新导入解析到不可练旧题。
- 原文提供的答案由AI提取时记录 `source_extracted_by_ai`；未人工核验的选择答案可显示“与参考一致/不同”，`correct/score`仍为空，不计客观错题。主观作答只保存内容和自行复习标记。未额外开发模型自动解题或主观评分。

普通练习可以重复。已有正式知识点的有效概念关联可只读参考有客观证据的BKT排序；没有正式关联时按既有错题和练习次数选择，不给新概念制造掌握概率。正式BKT仍使用原5点/10题，40候选不自动启用；本轮没有新增正式测评证据。

## 资料上传后问答

新增 `uploaded_document`，与 `course_material`、`personal_note`、已审核 `teaching_material` 分开。已解析课件无需先发布知识体系或审核页面关联，即可作为**未核验阅读来源**；不能冒充课程权威资料。

原件和解析文本仍在原存储。阅读索引按请求从当前SQLite解析单位重建，分块复用Markdown标题/段落与公式保护规则，没有新增外部服务、向量数据库或嵌入依赖。明确选中的文件、当前文件/解析版本、学生作用域在检索前后再次校验，原件指纹也要匹配；空来源不能查全库，文件修改/重解析/删除使旧引用范围失效。

来源列表显示“可问 X / Y 个页面或文本单位”。当前通用规则排除少于24个非空白字符的稀疏单位和隐藏幻灯片；字符数只是可检索门槛，不是准确性证明。资料未就绪或正文不足不能参与当前检索，但仍可以打开其原件。

PDF正文不足时，可直接点击“识别缺失页面”：指定最多3页并单独确认整页图片外发到DeepSeek，每页最多3000输出token。复用已有视觉入口及可恢复记录；本轮没有实际调用。PPTX复杂图片暂不作视觉识别。

聊天默认在模型已启用时使用AI讲解，也可在回答设置选仅本地检索。上传资料和个人笔记的相关片段，均需本轮明确同意才发送；这与页图识别、学习指南授权分开。未同意则整轮本地检索。模型只看到当前实际检索的片段，不默认发送整库或旧聊天；不足部分可标注为模型自身知识，不伪造引用。

一般资料问答使用独立workbench接口；只有选择严格属于当前发布允许范围时才复用课程会话讲解接口。没有扩大原课程发布权限，也不把一般问答补认成绑定课程版本的教学事实。

## 接口

已有接口保持兼容，自动整理通过显式字段启用：

```text
POST /api/v1/students/{student}/personal-bank/extraction-tasks
{ request_id, text 或 resource_id/source_version/run_id/ordinals,
  consent: true, include_images: false, auto_import: true }

GET  /api/v1/students/{student}/personal-bank/extraction-tasks/{request_id}
     result.intake = { ready, needs_attention, duplicate }

POST /api/v1/students/{student}/personal-bank/organize
{ request_id, question_ids?: [UUID...] }
     返回 processed/ready/needs_attention；相同编号内容冲突409。
```

原本地规则 `/personal-bank/extractions` 也接受 `auto_import`。不传/false沿用草稿流程；重识别修正稿不自动晋级。开始和提交普通练习继续复用原 `/personal-bank/practice`。

```text
GET  /api/v1/students/{student}/knowledge/sources
POST /api/v1/students/{student}/knowledge/search
POST /api/v1/students/{student}/workbench/questions
POST /api/v1/students/{student}/workbench/sources/open
```

新来源引用仍是 `{source_type, source_id, source_version}`，类型为 `uploaded_document`；来源额外返回 `document_id/version_id/run_id/file_format/readable_units/total_units`，审核标记 `document_unverified`。引用保留页/幻灯片、片段快照、偏移和版本；打开原文/原件不调用模型。历史快照不充当当前来源。

聊天上传资料外发沿用服务器 `allow_teacher_external` 字段，笔记仍为 `allow_personal_external`，都不能被模型修改。指南没有新增上传资料外发授权入口，选中上传资料时仍提供本地规则/引用，不借用聊天同意。

## 数据版本、备份及回退

schema12→13，表数仍45；没有新增依赖或数据表。新JSON来源类型和自动整理审核元数据需要版本保护，避免旧程序读取不支持的新记录。普通API拒绝连接12库，旧12程序拒绝13库。

现库已显式升级，**不要重复运行旧迁移脚本**。新环境/旧12副本需先停写并备份，再使用本版迁移入口：

```powershell
cd D:\ZZUAgent
.\.venv\Scripts\python.exe -m eduagent.storage.migrations --db data/local/eduagent.sqlite3
```

本轮备份 `data/local/eduagent.before-v12-ad326e48f82b.sqlite3`；代码和初始备份在 `data/local/learning-simplification-0d9bec9e/`。实际45表摘要、原正式题库、完整性/外键均通过核对，原题/笔记/学习事实没有被自动改写。

回退必须先停止服务，把**回退时的13库及原件目录**保留到新位置，再恢复12备份到独立位置并使用原12代码。不要向已有13库直接写回12或用旧备份覆盖新数据。已演练保留带升级后新记录的13副本、恢复12副本，旧代码接受12并拒绝13；故障注入在提交版本号前失败时完整回滚。详见迁移验收JSON。

本机启动命令不变：

```powershell
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

仅本机演示；student_id仍不是身份认证。不能从本轮整理推断真实材料已经人工审阅，不能据工程测试宣称教学效果提升。
