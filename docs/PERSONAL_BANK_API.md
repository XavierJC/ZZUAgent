# 统一资源与个人题库 API

前缀 `/api/v1/students/{student_id}`，仍为本机演示作用域，不是真实认证。课程目前固定machine_learning。JSON严格类型、拒绝额外控制字段；写入需UUID `request_id`。相同编号/相同内容重放回执，相同编号/不同内容409，跨学生不可见。

| 方法/路径 | 功能 |
| --- | --- |
| GET /course-resources | 稳定资源目录、状态、已发布章节/概念；只读，无同步写入 |
| GET /course-resources/{id} | 当前资源与复用解析文本 |
| PUT /course-resources/{id} | expected_revision、resource_type、links；修改目录用途/关联 |
| GET /personal-bank/requests/{request_id} | 保存的幂等回执，不重新执行 |
| POST /personal-bank/extractions | 选择资源或粘贴文本，原子创建提取批次和待审核题目 |
| GET /personal-bank/questions | q/status/question_type/resource_id/chapter_id/concept_id筛选 |
| POST /personal-bank/questions | 手工录题；payload、status、reviewed、confirm_answer |
| GET /personal-bank/questions/{id} | 当前题目、来源证据、来源状态、审核信息 |
| PUT /personal-bank/questions/{id} | expected_revision＋完整payload，保存草稿或确认普通练习 |
| DELETE /personal-bank/questions/{id} | expected_revision，归档；历史保留 |
| GET /personal-bank/questions/{id}/revisions | 不可变编辑/审核历史 |
| POST /personal-bank/restructure | originals题目ID/revision，questions新题数组；合并或拆分 |
| POST /personal-bank/practice | 可选question_id/concept_id，创建一道普通练习快照 |
| GET /personal-bank/practice | 最近100次，可带wrong_only=true |
| GET /personal-bank/practice/{id} | 恢复原练习，不重新分配 |
| POST /personal-bank/practice/{id}/answer | selected_answer；只用保存的人工确认答案判分 |
| GET /documents/{id}/preview?version_id=…&page=1 | 私有受限PNG预览，no-store/nosniff；不调用模型 |

资源类型：teaching_material/reference/personal_note/exercise_material；原来源类型独立为document/course_material/personal_note/text，修改用途不会修改资料权威性或授权。链接格式 `{architecture_id,node_id,kind:"chapter|concept",review_status:"candidate|confirmed"}`，首次目录修订为0，保存后为1。

从已保存PDF解析提取（使用目录返回的真实ID和版本）：

```json
{"request_id":"替换为UUID","resource_id":"替换为资源UUID","source_version":"替换为文件版本UUID","ordinals":[1,2]}
```

默认使用当前本地run；可明确指定同文档同当前文件版本的已完成视觉run_id，未就绪/失效任务拒绝。个人笔记/课程文本不接受文件run或页码。

粘贴提取：

```json
{"request_id":"替换为UUID","title":"自建原题","text":"1. 求导？\nA. 2x\nB. x\n答案：A"}
```

确认题目：PUT使用详情里的payload，附 `expected_revision`、`status:"practice"`、`reviewed:true`，答案由本人核对时附 `confirm_answer:true`。没有可靠答案可以不确认，此时练习明确不判分。来源变化须先人工核对并显式 `acknowledge_source_change:true`；旧题文本不自动改写。

开始练习返回session_id；GET恢复本轮；POST answer带新的request_id和selected_answer。未作答时常规question字段不提供答案和解析，原始证据仍属可查看的学习资料，不能把普通练习当防作弊考试系统。评分后保存correct/score/说明，未人工确认答案时correct和score均为null，`bkt_updated=false`。一个session只作答一次，重复练习新建session；不会调用正式next/answers接口。

错误：404作用域下不存在；409 revision_conflict/request_id_conflict/source_changed/parse_not_ready/no_personal_practice/personal_attempt_exists；422字段、关系或答案无效；413请求/资源超限。题库JSON≤256KiB，每学生≤1000题（含归档）。前端断网后只GET回执，不自动重复写入；请求编号保留，可手动核对。
