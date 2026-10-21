# DeepSeek 实际验证记录

日期：2026-10-19。以下为项目本机实际 API 请求结果，所有学情由合成演示标识创建，未使用真实学生数据。测试只证明下列场景中的接口与工具流程可执行。

## 场景一：解释梯度下降并获取练习

- 模型：`deepseek-flash`，非思考模式。
- 入口：`python -m eduagent.agent.smoke`。
- 问题：读取演示学情，检索资料解释负梯度方向，并安排下一道合适练习。
- 运行 ID：`f295a8da-c18e-4ff5-8733-6546753c92a6`。
- 实际模式：`deepseek`，无降级原因。
- 实际工具：`get_learning_state`、`retrieve_course_material`、`get_next_exercise`，均成功。
- 来源：`gradient:1`、`gradient:2`、`gradient:3`，对应 [梯度下降资料](../data/materials/gradient_descent.md) 的参数更新、学习率与批量/随机梯度章节。
- 下一行动：`diagnose`，先诊断薄弱先修知识，而非直接越过先修安排目标练习。
- 模型请求数：3；上游返回 prompt tokens 3798、completion tokens 460。
- 原始本地记录：`data/local/live-agent-smoke.sqlite3` 的 `tutor_runs`。

回答说明了梯度指向局部上升方向、采用负梯度进行局部下降，以及有限步长不保证每一步都下降的限制；引用均来自本次检索。该场景尚未作答，不存在测量学习提升的结果。

首次命令在模型完成且记录保存之后，打印 Unicode 数学符号时遇到 Windows GBK 编码异常，因此该次命令退出码为 1。已从保存记录确认模型与工具执行成功，并把报告输出改为 ASCII JSON 转义，避免重复付费请求。此处不将终端打印失败描述为模型调用失败，也不隐去该问题。

## 场景二：通过 HTTP 解释过拟合并获取练习

- 服务：本地 `127.0.0.1:8000`，版本 `0.3.0`；Agent 与检索均启用。
- 入口：创建演示记录后调用 `POST /api/v1/students/{student_id}/tutor`。
- 学生演示标识：`agent-http-demo-8737c7c2`，目标为过拟合与正则化。
- 运行 ID：`adef165b-9891-4377-89d9-b90cd17e36ca`。
- 实际模式：`deepseek`，无降级原因。
- 实际工具：读取学情、检索课程、获取下一练习，均成功。
- 来源：`regularization:1`、`regularization:2`、`regularization:3`，对应 [过拟合与正则化资料](../data/materials/regularization.md) 的三个章节。
- 下一行动：`diagnose`，返回合法先修练习分配，公开题目对象不含答案。
- 模型请求数：3；上游返回 prompt tokens 3598、completion tokens 550。
- 记录查询接口返回内容与生成回执一致；查询学情版本仍为 0，提问没有产生评分或掌握度更新。
- 实际 HTTP 验证命令退出码 0，摘要保存在 `data/local/live-api-report.json`，完整结果保存在主数据库 `tutor_runs`。

第二次验证时，模型只收到练习分配元信息，不收到题干或选项；客户端单独收到可展示的题目。该限制及更新学情读取另有离线测试覆盖。

## 解释范围

两组真实场景共 6 次模型请求，上游返回合计 prompt tokens 7396、completion tokens 1010。这里记录用量，不据此推算费用或泛化成功率。

全部资料与题目仍待人工审阅。引用 ID 校验只能证明出处属于已检索章节，不能替代事实与教学质量审查。没有真实用户试用、学习成绩改善或真实 BKT 参数拟合结果。

程序测试和环境记录见 [开发计划](DEVELOPMENT_PLAN.md)，配置与接口见 [Agent 说明](AGENT_GUIDE.md)。文档不包含 API 密钥。
