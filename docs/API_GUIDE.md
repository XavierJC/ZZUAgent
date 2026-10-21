# 第二阶段 HTTP 接口说明

聊天字段兼容后续修复：`WorkbenchRun.validation_summary`记录已知字段名、根类型和未知字段数量，不保存字段值；428项后端通过，路径/schema6不变，见[字段兼容记录](ANSWER_SCHEMA_GUIDE.md)。

混合问答后续修复：`WorkbenchRun`增加`answer_basis=mixed`、`supplement_md`，误加的`time_snapshot`接口字段已撤回，旧原始历史不重写。现有路径/schema6不变，391项后端通过，见[混合问答指南](WORKBENCH_HYBRID_GUIDE.md)。

工作台问答后续修复：`WorkbenchRun`增加默认字段`answer_basis`、`validation_error`，空检索可继续模型解释但无本地引用。382项后端通过，schema6和29路径不变，实际行为见[修复记录](WORKBENCH_ANSWER_FIX.md)。

当前Phase4A（2026-10-21）：共29个OpenAPI路径，新增自评保存/历史/回执、只读学情建议及受控指南/历史8个操作（6条路径），schema6已备份迁移，355项后端通过。实际契约见[PHASE4A_GUIDE.md](PHASE4A_GUIDE.md)，原学习/笔记/工作台兼容，下文各旧路径数与验证为阶段历史。

当前Phase3B：共23个OpenAPI路径，新增独立工作台6条路径，原tutor_runs与学习API兼容；笔记详情增加只读generation_origin。318项后端回归通过，schema5备份与回滚副本已验。实际问答、逐轮同意、引用/历史和另存契约见[工作台指南](WORKBENCH_GUIDE.md)。下文此前版本的路径数和验证保留为历史。

Phase3A补充：新增学生来源目录、显式来源检索、索引重建3个路径，当前共17个OpenAPI路径；本地检索无模型密钥可用，当前后端295项回归通过，schema4已备份迁移。实际请求与版本/错误契约见 [个人检索指南](PERSONAL_RAG_GUIDE.md)；下文保留原学习接口和历史验证。

当前补充（2026-10-20）：v0.5.0 Phase2个人笔记已实现，完整269项后端/75项前端测试通过，OpenAPI共14个路径。新增笔记六类操作、严格字段、revision、导入、schema3迁移/回滚见 [NOTES_GUIDE.md](NOTES_GUIDE.md)。本页保留原学习API及其历史验证记录，原评分/BKT契约未变；个人检索未实现。

截至 2026-10-19，完整测试为 **138 passed in 5.16s**，已增加基础模型与课程检索。本文保留基础 HTTP 契约；新增 `/tutor` 与检索配置见 [Agent 说明](AGENT_GUIDE.md)。学习推进仍受规则约束，Vue 页面尚未实现。

2026-10-20 补充：Vue 学习页面已实现并构建，后端 186 项、前端 17 项测试通过。新增答题历史及保存讲解列表，目前共 11 个 OpenAPI 路径；页面与新增接口见 [Web 说明](WEB_GUIDE.md)。上段为此前阶段的历史状态。

同日 0.4.1 补充：最新后端 202 项、前端 18 项测试通过。助教新增 insufficient_evidence 本地反馈、原问题来源检查、长问题处理与可空 retrieval_policy，路径数量仍为 11；旧记录不补造该策略字段。详细边界见前述 Agent 与 Web 说明。

后续离线教学决策配对比较完成，完整后端测试增至 225 项；未改 HTTP 接口、前端或数据库。对比方法及限制见 [教学决策对比](POLICY_EVALUATION.md)，上段 202 项为此前检索修复时的记录。

## 安装与启动

项目已在 `D:\ZZUAgent\.venv` 中安装。当前电脑直接从项目根目录运行：

```powershell
Set-Location D:\ZZUAgent
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

启动后访问 [交互接口文档](http://127.0.0.1:8000/docs)、[OpenAPI JSON](http://127.0.0.1:8000/openapi.json) 或 [健康检查](http://127.0.0.1:8000/health)。按 Ctrl+C 停止。交互文档的 Swagger UI 静态资源来自 CDN，离线时仍可直接调用 HTTP 接口或读取 OpenAPI JSON。

若出现 `ERR_CONNECTION_REFUSED`，通常表示该地址没有后端进程监听。打开链接不会自动启动 Python 服务；请先在项目根目录执行启动命令，看到 `Application startup complete` 后再刷新，并保持进程运行。页面能够连接但文档内容空白时，再检查 Swagger UI 的静态资源是否加载。

新环境安装命令如下，本轮已实际执行并通过可编辑构建：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[api,dev,agent]'
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
```

只需要规则 HTTP 运行环境时，可安装 `./backend[api]` 并关闭 Agent。仅命令行核心仍不需要第三方运行依赖；HTTP 与模型依赖同核心分离。下表为 HTTP 与测试部分依赖，模型部分见 Agent 说明。

| 用途 | 固定直接依赖 |
| --- | --- |
| HTTP 接口与服务 | FastAPI 0.148.0、Uvicorn 0.54.0、Pydantic 2.12.5、Starlette 1.9.0 |
| 开发测试 | pytest 7.4.4、httpx2 2.14.0 |
| 构建 | setuptools 75.1.0 |

本次使用 Python 3.12.8，包声明 Python >=3.11，其他 Python 版本尚未测试。传递依赖由 pip 解析，尚未制作包含全部传递依赖的跨平台锁文件。

## 配置

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `EDUAGENT_DATA_DIR` | 当前目录下 `data` | 知识点与题库 JSON 目录 |
| `EDUAGENT_DB_PATH` | `data/local/eduagent.sqlite3` | SQLite 文件，可与命令行共用 |

例如使用单独的 HTTP 演示数据库：

```powershell
$env:EDUAGENT_DB_PATH = 'D:\ZZUAgent\data\local\http-demo.sqlite3'
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

路径在应用工厂创建时解析。启动阶段校验课程资料与数据库配置；存在先修环、题库错误或历史配置不一致时直接启动失败。题库/BKT/策略更改后仍需使用新数据库，目前没有历史迁移。HTTP 使用独立连接，禁止使用 `:memory:` 数据库。

当前应用工厂会读取根目录 `.env` 的允许字段，环境变量优先。Agent 开关、模型与密钥配置见 [Agent 说明](AGENT_GUIDE.md)；密钥不作为 HTTP 请求参数或响应字段。关闭 Agent 时保留原有规则 API。

## 接口契约

| 方法与路径 | 输入 | 输出及行为 |
| --- | --- | --- |
| `GET /health` | 无 | 进程存活、应用版本、规则模式、题目数与待校验数；不是持续数据库可用性探测 |
| `GET /api/v1/knowledge-points` | 无 | 五个知识点、先修关系及本地复习提示，不返回题库答案 |
| `POST /api/v1/students` | `student_id`，可选 `goals` 列表 | 创建或恢复记录，返回目标与掌握度；同一标识已有不同目标时返回 409 |
| `GET /api/v1/students/{student_id}/mastery` | 路径学生标识 | 一致快照：目标、状态版本、五知识点掌握度、答题数及是否有答题证据 |
| `POST /api/v1/students/{student_id}/next` | 无请求体 | 分配题目并保存行动依据；相同状态版本复用同一分配 |
| `POST /api/v1/students/{student_id}/answers` | `decision_id`、`event_id`、`answer` | 评分与 BKT 更新后返回正确选项、解析和三种概率；同事件重试返回原回执 |

取题会保存分配记录，因此使用 POST。客户端在评分成功后再调用 `/next`；提交接口不暗中推进到另一题，重试旧事件也不会改变当前分配或学习状态。

`student_id`、`decision_id` 和 `event_id` 为不带首尾空格、1～128 字符的字符串。建议演示学生标识使用简短 ASCII 名称；路径标识有特殊字符时需要 URL 编码。`event_id` 在数据库中全局唯一，建议使用 UUID，不要为不同学生复用固定的 `event-1`。

创建时省略 `goals` 表示全部知识点；恢复时省略则保留已存目标。API 最多接收五个目标，并自动包含先修知识点。空列表与未知知识点会被拒绝。

请求体禁止未声明字段，不能提交 `correct`、分数或 `next_mastery`。未完成合法作答前，取题响应中的 `question` 不含答案和解析；显式响应模型再次限定可输出字段。评分成功后回执包含 `correct_answer` 与 `explanation`。

掌握度响应中，`has_evidence=false` 表示尚无答题证据，此时 `probability=0.20` 为先验假设。`revision` 只随合法新答题递增，不随查询、退出或提交重试增加。

## 一次可复制的 HTTP 流程

服务启动后，在另一个 PowerShell 窗口运行：

```powershell
$base = 'http://127.0.0.1:8000/api/v1'
$learner = 'api-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$startBody = @{ student_id = $learner; goals = @('logistic_regression') } | ConvertTo-Json
$snapshot = Invoke-RestMethod -Method Post -Uri "$base/students" -ContentType 'application/json' -Body $startBody

$next = Invoke-RestMethod -Method Post -Uri "$base/students/$learner/next"
$next.question | Format-List

# 自行选择答案；下面 B 仅用于首次 lr_01 的工程演示
$answerBody = @{
    decision_id = $next.decision_id
    event_id = [guid]::NewGuid().ToString()
    answer = 'B'
} | ConvertTo-Json
$feedback = Invoke-RestMethod -Method Post -Uri "$base/students/$learner/answers" -ContentType 'application/json' -Body $answerBody
$feedback | Format-List

# 重试时必须复用整个请求体，不能重新生成 event_id
$retry = Invoke-RestMethod -Method Post -Uri "$base/students/$learner/answers" -ContentType 'application/json' -Body $answerBody
$retry.replayed  # True

Invoke-RestMethod -Uri "$base/students/$learner/mastery"
Invoke-RestMethod -Method Post -Uri "$base/students/$learner/next"
```

上面的演示答案来自待校验草稿，不属于真实学生测试。一般客户端应展示题目并接收用户输入。

## 错误与恢复

业务错误使用 `{"error":{"code":"...","message":"..."}}`；请求模型错误还包含字段位置、错误类型和消息，不回显原始输入值。

| HTTP 状态 | 常见 code | 处理方式 |
| --- | --- | --- |
| 404 | `student_not_found` | 先创建或恢复学习记录 |
| 409 | `goal_conflict` | 同一标识不能静默更改目标，改用新演示标识 |
| 409 | `submission_conflict` | 检查是否消费过分配、事件内容是否变化或分配归属是否错误 |
| 422 | `validation_error` / `invalid_input` | 修正类型、字段、知识点或答案；该提交未更新学情 |
| 503 | `storage_unavailable` | 修复或等待存储恢复，然后用相同事件 ID 与内容重试 |

`finish` 和 `stopped` 是合法流程响应，HTTP 为 200。`stopped` 的原因包括题目不足和达到累计轮数上限；客户端不应继续对无题目决策提交答案。

## 实现与测试说明

入口为 [app.py](../backend/src/eduagent/api/app.py)，请求/响应约束在 [schemas.py](../backend/src/eduagent/api/schemas.py)，路径配置在 [settings.py](../backend/src/eduagent/api/settings.py)。路由复用 `LearningService`，没有另一套评分或概率更新逻辑。

应用在 [lifespan](https://fastapi.tiangolo.com/advanced/events/) 阶段加载并校验资料。每个同步路由在同一个工作线程内创建、使用、关闭 SQLite 连接；不在不同线程间共享第一阶段连接，提交事务与事件幂等规则继续生效。掌握度查询新增一致快照读取，不产生学习更新。

测试采用 FastAPI 的 TestClient，使用当前 [Starlette 推荐的 httpx2](https://starlette.dev/testclient/)；首轮普通 httpx 的弃用警告已通过调整测试依赖解决。测试代码见 [test_api.py](../backend/tests/test_api.py)。

第二阶段当时通过 **94 项测试**，其中新增 HTTP/配置测试 29 项；在临时 `127.0.0.1:8765` 服务通过真实 HTTP 完成创建、取题、两次作答、旧事件重试、查状态和推进，观察到 `revision=2`、掌握度约 0.82、下一知识点为梯度下降。该临时服务已停止。第三阶段完整测试增至 138 项，并另行启动 8000 端口服务，模型验证见 [实际记录](LIVE_MODEL_REPORT.md)。

当前仅用于本地演示，没有账号认证、跨域配置或学校系统接入。默认仅监听 127.0.0.1；学生标识是演示记录分区，不构成身份认证。题库与自建课程资料仍待人工校验。
