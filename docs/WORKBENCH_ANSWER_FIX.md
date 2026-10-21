# 工作台 RAG 空结果与模型输出接收修复

后续修复：[WORKBENCH_HYBRID_GUIDE.md](WORKBENCH_HYBRID_GUIDE.md)记录当前资料命中时也可补充模型知识、服务端时钟及391/104项回归；下文382/103为前次修复记录。

2026-10-21，用户明确授权修改两个问题。沿用“先检索所选资料，再把问题和片段交给DeepSeek”的同一问答流程，不新增模式、模型或学习入口。

## 实际行为

- 命中资料：仅发送本轮已选、有效版本、实际命中的片段与问题，回答保留原文引用。
- 检索无匹配片段：模型模式继续发送本轮问题，`untrusted_evidence=[]`；不提供检索/学情工具，不附学习状态或其他笔记。成功结果为`answer_basis=model_knowledge`，界面标明没有本地资料引用、来自模型自身知识、可能有误。
- 本地模式不调用模型；模型未启用仍本地返回。选中个人笔记但未同意本轮外发时仍整轮本地，不绕过原授权。
- 仍需明确选择1～55个有效来源。**没有命中片段**与**未选择来源**不同：空来源请求继续422，不扩大为全库。旧版本、跨学生、删除及索引不可用继续拒绝。
- 学习指南继续要求依据与保存学情；评分、BKT、自评、题库、旧tutor和学习历史规则不变。

没有本地依据不代表联网检索或事实校验；模型知识回答不能作为评分或教学事实。

## 返回解析与具体错误

新增`agent/workbench_answers.py`。接受完整JSON，以及整个JSON被单层`json`代码围栏包裹的格式，保留Markdown/LaTeX。不会从任意说明文字中截取花括号，或猜测修复JSON转义及公式。

引用列表必须属于本轮实际取得片段。若列表有效而正文未标编号，增加“参考片段”尾注；只恢复全局来源列表，不冒充句子级引用。已有内联引用与列表冲突、未知编号、缺失引用或越权字段仍拒绝。指南仍保留严格内联引用及链接约束。

提示明确要求使用`citation_id`，不能用`source_id`、`chunk_id`或自行简写数字。零片段回答要求`citation_ids=[]`，不提供工具；HTTP适配器省略空工具定义。

保留`reason=unverified_model_answer`，新增可空`validation_error`：

| 编号 | 含义 |
| --- | --- |
| `invalid_json` | 无法解析为JSON |
| `duplicate_json_fields` | JSON含重复字段 |
| `invalid_fields` | 回答字段缺失或多出未约定字段 |
| `invalid_answer` | 正文为空、类型或长度无效 |
| `invalid_citation_list` | 引用列表类型或数量无效 |
| `unknown_citation` | 引用不属于本轮取得片段 |
| `missing_citations` | 有片段的回答未提供引用 |
| `unexpected_citations` | 无资料却输出引用标记 |
| `citation_mismatch` | 正文引用与列表不一致 |
| `disallowed_links` | 指南包含不允许链接 |

界面显示对应原因。只存固定错误编号，不存被拒模型原文、密钥或完整请求日志。引用检查不证明句子级真实性，也不能保证完全防止提示注入。

## 接口、历史与兼容

继续使用`POST /api/v1/students/{student_id}/workbench/questions`及`local/model`两种方式。`WorkbenchRun`增加默认值字段`answer_basis`和`validation_error`。前者可为`selected_sources`、`model_knowledge`、`local_excerpts`、`none`。新元数据保存在原`result_json`；无新增路径、依赖或迁移，继续schema6。

旧记录只在读取时补兼容默认值，不改原文、不重新调用模型。相同request_id仍返回原结果，超时/执行待确认不重试。此前PCA失败没有保存具体项，不能倒推原始失败原因，也没有改写旧失败记录。刷新后新一轮使用新代码，可能产生模型费用。

无依据回答另存笔记时标明模型自身知识、无本地引用；继续幂等、可编辑、可索引，不改BKT。

## 验证与限制

- 后端：**382 passed in 18.94s**，原355加27项，覆盖围栏/公式/引用尾注、具体错误、空结果调用、工具边界、授权、旧记录、幂等及笔记来源。
- 前端：**103 passed in 4.82s**，8文件；无依据标记、具体错误、仍两个处理选项、历史只读和原交互通过。
- 构建成功：67模块，主JS599.71kB/gzip207.01kB，CSS70.30kB/gzip17.73kB。超过500kB的原有警告保留。
- [7组修复HTTP](../data/evaluation/workbench-answers-http-v1.json)：独立数据库、两次启动、6次模拟模型、0次真实模型，覆盖两种检索结果、围栏/尾注、授权/隔离、错误、另存来源及重启恢复。
- [18组4A HTTP回归](../data/evaluation/workbench-answers-phase4a-regression-v1.json)：独立数据库、9次模拟模型、0次真实模型，原阶段报告保留。
- 首次新增HTTP脚本误用`create_app`配置参数，服务未启动、验收失败；改为既有`APISettings.agent`后完整通过。
- 主库15表数量及摘要在修改前后相同，完整性及外键通过。代码快照保存在私有`data/local/rag-answer-fix-1887de43/before-code.zip`；没有迁移或覆盖数据库。

复现：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
Set-Location frontend
npm.cmd run test
npm.cmd run build -- --outDir dist-phase4a
Set-Location ..
.\.venv\Scripts\python.exe scripts/verify_workbench_answers.py
.\.venv\Scripts\python.exe scripts/verify_phase4a.py --output data/evaluation/workbench-answers-phase4a-regression-v1.json
```

部署、完整性与文件摘要见[修复交付报告](../data/evaluation/workbench-answers-validation-v1.json)。真实DeepSeek冒烟未执行，仍需单独预算确认；浏览器视觉/键盘人工验收未执行，jsdom/HTTP不能代替。模拟验证不能证明此前PCA真实输出具体触发哪条规则，新失败会返回具体编号。

人工检查：刷新本机页，用课程问题核对可点击引用；无匹配问题应标注模型自身知识；本地模式不调用模型；个人笔记逐轮同意；旧历史不重发；新校验失败显示具体原因。真实模型操作可能计费。
