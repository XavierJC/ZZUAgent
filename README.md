# 智学郑大 EduAgent

面向高校《机器学习》课程的个性化学习辅助系统，采用BKT知识追踪和受控Agent，服务于郑州大学AI智能体创新应用大赛A2任务。

**建立学习笔记本 → 添加资料 → 提问并查看出处 → 练习与记录理解。**

## 当前状态

已交付前端UI/UX全面优化。[唯一当前状态](docs/CURRENT_STATUS.md) · [新版界面、截图与验收](docs/UI_UX_REFACTOR_REPORT.md) · [设计系统](docs/FRONTEND_DESIGN_SYSTEM.md) · [笔记本指南与API](docs/NOTEBOOK_REBUILD_GUIDE.md)。

默认主页显示真实学习目标、待诊断状态和继续学习，再按主题组织笔记本；笔记本内有问答、练习、笔记三个任务，原文按需对照。题库与学习进度保留主入口，手机菜单可访问全部辅助工具。管理采用资料、知识、习题和发布的准备流程。五个项目的参考与代码归属见[开源参考](docs/OPEN_SOURCE_UI_REFERENCES.md)。

最新测试、四种尺寸的浏览器检查及数据摘要结果见CURRENT_STATUS。本轮只改前端和验收文档，没有变更后端业务或schema，没有新增依赖或真实付费模型调用。上轮Notebook迁移记录保留于原报告；内容人工审核与真实教学效果仍待验证。

现有能力包括来源受控RAG、Markdown/LaTeX笔记、资料解析与页码引用、原题整理和普通练习、正式BKT闭环、自评与学习指南。正式仍原5知识点/10道演示题，40候选未自动启用；普通练习不更新BKT。仅本机演示，学习标识不是身份认证。

## 启动

在项目根目录打开PowerShell：

```powershell
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

打开[学习笔记本](http://127.0.0.1:8000/#/notebooks)，新建或恢复学习标识，再创建学习主题。已有资料可从“添加或管理资料”选择，不需重复上传。服务终端需保持运行；若连接被拒绝，先检查服务是否仍在运行。

修改前端后重新构建：

```powershell
Set-Location frontend
npm.cmd run build
Set-Location ..
```

## 新环境与测试

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[api,dev,agent,documents]'
Set-Location frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
```

前端使用Node22.12及以上受支持版本，具体范围见package.json。模型密钥只配置于本机忽略的.env，参考.env.example；不在源码或报告中保存密钥。没有密钥仍可本地解析、检索和执行规则指南。本轮重构不进行真实付费模型调用。

默认数据库为data/local/eduagent.sqlite3。当前schema与数据验证见CURRENT_STATUS，不重复执行旧迁移；不得让不兼容旧程序连接新库。

## 代码结构

- frontend/src/app：课程布局、路由、模块生命周期与导航协调。
- frontend/src/features：notebooks、materials、chat、practice、notes、learning、authoring。
- frontend/src/shared：通用请求能力；现有Markdown与基础组件继续复用。
- backend/src/eduagent：API、domain、services、storage、documents、retrieval、agent。
- docs/CURRENT_STATUS.md：当前实际能力；docs/history：旧阶段原件和报告索引。

技术栈：Vue3/Vite、Python/FastAPI、SQLite、LangGraph单一Agent、BKT、TF-IDF/FAISS、DeepSeek。当前本地检索是词项基线，不宣称已升级语义检索。

## 数据与使用边界

AI整理不等于人工核验；无法提取的页面和公式明确提示。普通练习、自评和笔记不改变客观掌握度，BKT先验不当作诊断。

所选来源由后端再次校验；空选择不查全库。个人笔记和上传/教师资料的模型外发逐轮同意，和视觉识别、指南分别管理。历史引用保留当时快照，软删除不等于物理清除。

## 文档入口

[项目上下文](docs/PROJECT_CONTEXT.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [历史索引](docs/history/README.md) · [API基础](docs/API_GUIDE.md) · [工作台](docs/WORKBENCH_GUIDE.md) · [笔记](docs/NOTES_GUIDE.md) · [个人RAG](docs/PERSONAL_RAG_GUIDE.md)。

旧阶段的schema、测试数字和“当前”记录属于历史。真实内容审核和教学效果与工程测试分别记录。
