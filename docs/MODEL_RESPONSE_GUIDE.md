# 模型未完整返回：诊断与修复

后续[聊天字段兼容修复](ANSWER_SCHEMA_GUIDE.md)记录当前428/107项、32组模拟HTTP及混合来源真实验证；下文403/106为响应终止原因修复时的历史。

2026-10-21。用户反馈工作台显示“模型服务异常”。本轮检查现有问答回执后，修复响应诊断、JSON输出与工作台预算，并经用户单独授权完成少量真实DeepSeek验证。没有改变RAG辅助、大模型综合生成的目标。

## 实际原因与证据边界

19:52:47和19:53:04两轮确实各调用了模型2次；最终保存`incomplete_model_response`，不是未调用模型。此前适配器把所有非`stop/tool_calls`终止情况合并，前端又没有对应提示，因此显示泛化异常。

旧记录没有保存具体`finish_reason`，不能断定当时一定是长度截断。旧用量只有成功返回的工具轮次，失败轮次的用量被丢弃，也不能当完整账单。当前原配置每次输出700 token，对复合问题与长引用可能偏紧，但这只是风险判断。

依据[DeepSeek官方接口说明](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/)，`length`可能表示输出或上下文长度限制；`content_filter`、`insufficient_system_resource`、`aborted`分别有其他终止含义。[JSON模式说明](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)也要求明确提示JSON并合理配置输出长度，不能保证长度不足时JSON仍完整。

## 修改

- 工作台聊天独立使用`EDUAGENT_WORKBENCH_MAX_TOKENS`，默认1500，允许100～1500。原`EDUAGENT_MODEL_MAX_TOKENS=700`继续用于旧助教和学习指南，不被覆盖。模型最大调用次数仍原配置3次；前端发送前显示两项限制。
- 仅工作台客户端启用`response_format={"type":"json_object"}`，提示要求简洁并减少重复长引用。旧助教和指南客户端不自动启用新JSON参数。
- 适配器区分`model_output_truncated/model_content_filtered/model_resource_exhausted/model_aborted`；其他不可识别终止保留`incomplete_model_response`。保存白名单终止编号及上游报告的用量，不记录被拒原文、密钥或完整私有请求。
- 新回执保存`finish_reason`及`max_output_tokens`。失败调用的已知token用量计入本轮累计；网络超时未知用量不猜测。统计不是收费账单。
- 前端显示明确原因，不再用泛化消息掩盖“未完整返回”；旧回执不猜测终止原因，不补写历史。
- 不展示或拼接截断的JSON为完整模型回答，不自动续写或重发付费请求。同request_id仍读取原结果。来源选择、外发同意、引用验证、BKT与评分规则保持。

配置示例仅见`.env.example`，本轮没有改写真实`.env`。增加聊天输出额度可能增加后续用户主动请求的费用，界面会展示配置；它不是保证所有回答不再截断。

## 实际验证

- 后端：**403 passed in 19.10s**；前端：**106 passed in 4.80s**，8文件。
- 构建成功：67模块，主JS601.51kB/gzip207.55kB，CSS70.30kB/gzip17.73kB，保留默认500kB警告。
- [12组问答HTTP](../data/evaluation/model-response-http-v1.json)：独立数据库、11次模拟模型；含截断/过滤、失败用量、输出额度、JSON模式、幂等/重启、综合生成。
- [18组4A HTTP回归](../data/evaluation/model-response-phase4a-regression-v1.json)：独立数据、9次模拟模型。最终两份HTTP报告合计20次模拟调用、0次真实调用；真实冒烟另列。
- [真实DeepSeek冒烟](../data/evaluation/model-response-live-v1.json)：用户明确授权最多2次上游请求、每次输出上限1500，不发个人笔记。实际只使用**1次**：`complete`，无异常/引用错误，`answer_basis=mixed`，3个课程引用，回答1093字符、模型补充543字符；上游报告输入1970、输出652 token。历史GET及同编号重放增加调用0，掌握度保持，主库写入0。剩余额度没有继续使用。
- 真实冒烟通过应用API的TestClient执行，**上游是实际DeepSeek**，与前两份模拟HTTP报告区分；只用独立库与自建课程片段。没有记录完整模型答案或密钥。652 token的成功不能反证或确定此前失败终止原因，也不能保证每次都成功。
- 首次烟测脚本误将学生注册响应限定为201，实际返回200，断言失败；发生在任何上游模型调用之前，真实调用0。修正为接受既有状态后再执行上述1次真实请求。不是重发了一个执行未知的模型请求。

部署、文件与完整性见[交付记录](../data/evaluation/model-response-validation-v1.json)。schema6、29条路径不变，无新增依赖、无迁移。只读部署核验初轮发现现用`study_guide_runs`在开发期间由0增至1，导致全库等值断言未通过；完整性/外键正常，其他14表摘要一致，保留新增历史，没有覆盖现库。该条指南为模型模式、1次调用、`unverified_model_answer`，不当作本次聊天冒烟成功证据，旧结果不能补造具体校验原因。验证程序没有向主库写入合成请求。私有代码快照在`data/local/model-response-fix-e7449827/before-code.zip`。

浏览器人工视觉/键盘验收和真实教学效果未验证。课程55例、5/15误检与40题待审保持，不扩展新阶段。旧失败问答仍保留原结果；刷新页面后，新一轮才使用修复后的限制及诊断。
