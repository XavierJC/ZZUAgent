# 智学郑大 EduAgent

面向高校《机器学习》课程的个性化学习辅助系统，采用BKT知识追踪和受控Agent，服务于郑州大学AI智能体创新应用大赛A2任务。

**读课程资料 → 提问并查看出处 → 练习 → 查看学习进度与下一步建议。**

## 当前状态

已交付课程学习空间与前端模块重构第一阶段。[唯一当前状态](docs/CURRENT_STATUS.md) · [重构指南](docs/REFACTOR_STAGE1_GUIDE.md) · [实际验收](docs/REFACTOR_STAGE1_REPORT.md)。

学生主入口为资料学习、练习、学习进度；笔记与正式学习保留辅助入口，课程构建独立。页面按需加载，模块草稿跨页保留，资料目录独立于题库。

本轮615项后端、210项前端、29组隔离HTTP和构建通过，助手完成14组浏览器检查；schema13/45表摘要保持，真实模型0次。入口JS约179kB，大型渲染依赖单独加载；内容精度和真实教学效果仍待验证。

现有能力包括来源受控RAG、Markdown/LaTeX笔记、资料解析与页码引用、原题整理和普通练习、正式BKT闭环、自评与学习指南。正式仍原5知识点/10道演示题，40候选未自动启用；普通练习不更新BKT。仅本机演示，学习标识不是身份认证。

## 启动

在项目根目录打开PowerShell：

```powershell
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

打开[课程学习空间](http://127.0.0.1:8000/#/study)，选择新建或恢复学习标识。服务终端需保持运行；若连接被拒绝，先检查服务是否仍在运行。

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
- frontend/src/features：materials、chat、practice、notes、learning、authoring。
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
