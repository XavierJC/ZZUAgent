# PDF 局部容错与决策树课件恢复

日期：2026-10-26（Asia/Shanghai）。用户在确认解析失败原因后明确要求：“解析错误的部分直接跳过，保留可解析的部分”。本轮按此授权实施 PDF 解析器的局部容错，并仅重试当前未删除的决策树课件一次。[当前状态](CURRENT_STATUS.md) · [此前诊断提案](PDF_ENCODING_COMPATIBILITY_PROPOSAL.md)。

## 已实现的行为

- PDF 提取结果中的合法 UTF-16 高低代理对合并回原 Unicode 字符；无法恢复的孤立代理字符和 NUL 用可见的 `�` 标出缺失位置，正文继续保留。不会静默删除整段文字或伪造公式。
- 单页读取/文字解析异常时，该页保存为空正文并记录“本页文字解析失败，已跳过”，继续解析后续页。物理页码不压缩、不重新编号；空正文不会进入检索。
- 图片资源信息检查失败时保留已经提取的文字；页码标签异常时回退到实际物理页码。相关提示保存到原有 warnings 字段，不改 schema。
- 文件整体损坏、加密、页数/文本/解压限额、内存和进程资源限制仍按原规则拒绝或失败。TXT/Markdown 严格 UTF-8 规则不放宽。
- 资料详情、原文抽屉和资源目录将新增提示转为中文。部分提取不等于人工核验或完整识别，用户仍可查看原件。

没有更换 PDF 解析引擎，没有新增 OCR/模型调用、依赖、API、数据库契约或正式评分行为。已有失败文件不批量自动重试；已经删除的两个旧副本保持删除状态。

## 这份决策树 PDF 的实际结果

原件大小 4,557,193 字节，SHA256 与上传记录一致。先在隔离临时目录运行原有受限 worker，验证结果可完整编码为 UTF-8；临时含正文输出随目录退出清理，不把课件正文写入报告。

随后通过既有 `POST /documents/{id}/parse`，携带原 expected_revision 与预先持久化的 request_id，仅重试当前未删除文件一次。请求编号保存在忽略目录；若执行结果未确认，脚本后续只 GET 原回执，不重复 POST。

| 项目 | 实际结果 |
| --- | --- |
| 解析状态 | `failed / parse_failed` → `partial` |
| 保存的页面单位 | 69，原物理页码保持 |
| 可用于检索的页面 | 53 / 69，依据原有正文长度条件，没有降低准入阈值 |
| 整页解析异常而跳过 | 本文件为0页；原失败由字符序列导致，修复后无需丢弃整页 |
| 编码处理/需核对的页面 | 7、8、11、12、13、21、23、24、25、30、52、57、58、65 |
| 不足以检索的其余页面 | 原页仍保留供对照；不能用这些缺失正文支持回答，不宣称全部图像或公式已识别 |
| 来源目录 | `index_status=ready`，可选择加入主题，不需要重新上传 |
| 原件/历史 | 原件不变，原失败解析记录保留，新增独立解析记录 |
| 模型与外发 | 隔离 worker 和现用本地解析均为0次模型调用，无资料外发 |

“编码兼容处理”包含可恢复字符与可见缺失标记；上述14页仍需要对照原页核对，不能将工程恢复宣称为公式内容已准确还原。没有替用户确认内容审核，也没有自动改变 Notebook 资料范围或外发授权。

## 数据保护

操作前在线备份：`data/local/pdf-partial-20261026-124324/`，包含 `before.sqlite3`、源码 ZIP、50 表摘要、8 个既有原件指纹及195个既有内容/评估文件指纹。完整性与外键检查通过。

现用 schema14 / 50 表保持。本轮现用数据库仅改变四张既有资料表：`course_documents`、`document_parse_runs`、`document_units`、`document_operations`，且只属于当前目标资料。新增一次本地解析、69个页面单位和一个操作回执；原资料 revision/parse_generation 各加1，文件版本保持。

其余46表摘要完全保持，包括学生 revision、正式作答、BKT、自评、笔记、题库、Notebook 及发布事实。四张资料表中原有记录除目标文档当前解析指针外也保持，其他文档不变，原失败历史不覆盖。8个原件和195个既有内容/评估文件指纹全部保持；依赖清单不变。

证据：[隔离 worker](../data/evaluation/pdf-partial-worker-v1.json)、[现用恢复、API与数据验证](../data/evaluation/pdf-partial-recovery-v1.json)。这些报告只有状态、计数、页号、指纹与文件清单，不含课件正文或真实学习标识。

## 测试与验证

| 验证类别 | 结果与实际范围 |
| --- | --- |
| 后端全量 | 648 / 648，新增9项；页失败保留前后页、数学代理对与孤立字符、异常页码、图片元信息异常、全空页面、资源限制不被吞掉、真实 worker UTF-8 保存、失败页不进入检索 |
| 前端全量 | 256 / 256，22文件；新增中文局部失败提示和无自动视觉调用断言 |
| 生产构建 | 通过，164模块；新增共享提示映射，无新增依赖 |
| 真实课件隔离 worker | 69页面/53可检索页面，UTF-8保存通过；原件和现用库不改 |
| 现用真实本机 HTTP | 一次原接口重试完成；GET资料详情与来源目录均通过，来源可用，模型调用0 |
| 现用数据核验 | schema、完整性、外键、其他46表、旧历史、全部既有原件与内容指纹保持 |
| 浏览器 / 人工内容 | 本轮没有重新进行助手浏览器或负责人逐页内容审核；不把单元测试当作浏览器体验或教学效果验收 |

受限环境中两个 pytest 进程在本机 HTTP 初始化阶段停滞，按实际命令和PID仅停止本轮测试进程后，在正常本机权限下完成全量648项。只读API核验初次受 WinError10013 套接字限制，正常本机权限复核通过。没有删除测试、放宽断言或关闭资源/来源校验。

本轮未运行真实收费模型；测试中的模型行为使用原有模拟夹具，不能当作真实模型质量或费用验证。

## 使用与回退

刷新现有页面后，从主题资料窗口选择“机器学习-第7讲-决策树”并加入主题即可，无需重传。部分正文不足的页面需查看原件；提示中的 `�` 表示字符缺失，不能把它当作正确公式。

本地 worker 每次解析均启动新进程，已直接加载更新后的 PDF 代码；无需为此重启或停止现用8000服务。新前端已构建，旧浏览器标签需要刷新。读取/刷新不重新解析或调用模型。

验证命令（项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q --basetemp data/local/pdf-partial-native
Set-Location frontend
npm.cmd test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe scripts/verify_pdf_partial_recovery.py --verify
```

恢复脚本 `--snapshot DOCUMENT_ID` 用于新的明确目标；`--isolated` 只跑受限 worker；`--retry` 首次提交一次本地解析，编号存在时只核对原回执；`--verify` 为只读核验。不要把这些命令用于未经授权的全部失败资料。

回退只恢复备份中匹配的解析器/前端源码并重新构建，保留本次新解析和后续学习数据。输出字段与既有 schema/API兼容，不需要用旧数据库覆盖现库。未来如需再次解析仍应明确操作，不在回退、挂载或刷新时自动发起。

## 实际修改文件

- `backend/src/eduagent/documents/parsers/pdf.py`
- `backend/tests/document_fixtures.py`
- `backend/tests/test_document_parsers.py`
- `backend/tests/test_documents.py`
- `frontend/src/shared/documentWarnings.js`
- `frontend/src/components/DocumentManager.vue`
- `frontend/src/components/SourceDrawer.vue`
- `frontend/src/features/materials/ResourceLibrary.vue`
- `frontend/src/__tests__/documents.test.js`
- `scripts/verify_pdf_partial_recovery.py`（建立基线前新增，之后补充只读API核验）
- `docs/PDF_PARTIAL_RECOVERY_REPORT.md`、原诊断提案及当前状态/计划/上下文/README/第一阶段指南和报告入口。

本轮完成后停止。没有自动进入其他资料重试、识别引擎升级、检索排序、新题生成、正式题库扩充、BKT扩点或收费模型调用。
