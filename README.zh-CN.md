# ClawResearch（InsightEngine）

[English](./README.md) · 中文

一个面向“长任务深度调研”的、基于文件系统的工作流引擎。

它提供：
- **标准化 Topic 目录结构**（原始材料 → 蒸馏笔记 → 综合 → 最终报告）
- **分步生成研报**（先大纲 → 再分章 → 最后组装），避免 one-shot 过短
- **Notion 交付工具**：将 Markdown “尽力”转换为 Notion Blocks，并以覆盖模式写入
- **任务级 Watchdog**：当流程卡住时唤醒（带 cooldown + lock，防刷屏/多实例）

> 状态：持续迭代中。本仓库为公共可复用引擎，不包含私有数据。

## 快速开始

### 1）配置
编辑 `config.json`：
- `root_path`：工作区路径（一般就是本仓库目录）
- `notion_database_id`：你的 Notion 数据库 ID

设置环境变量：
- `NOTION_API_KEY`（Notion integration token）

### 2）创建一个 Topic
```bash
python3 tools/init_topic.py "我的主题"
```
然后把素材放进：
```
Topics/YYYYMMDD_我的主题/01_RawMaterials/
```
（建议保存为 `.md`）

### 3）一键跑完全流程
```bash
python3 tools/orchestrator.py "我的主题"
```
该命令会：
- 加“单实例运行锁”
- 启动任务级 watchdog
- 生成大纲 → 分章生成 → 组装 `report.md`
- 写入 Notion（覆盖写 + 重试 + 写后校验）
- `git commit` + `git push origin main`（带重试）

## 目录结构

```
.
├── tools/
│   ├── init_topic.py        # 初始化 Topic 工作区
│   ├── orchestrator.py      # run lock + watchdog + pipeline + 交付
│   ├── pipeline.py          # 大纲/分章/组装（分步生成）
│   ├── notion_sync.py       # Markdown → Notion Blocks（覆盖写 + 重试）
│   ├── moltbook_client.py   # Moltbook API helper（可选，仅主题相关时使用）
│   └── llm.py               # headless LLM runner（claude/gemini）
├── watchdog.py              # 卡死检测（cooldown + lock）
├── config.json              # 本地配置
└── Topics/YYYYMMDD_TopicName/      # 每个 Topic 的工作区
    ├── 00_Brief/
    ├── 01_RawMaterials/
    ├── 02_Distilled/
    ├── 03_Synthesis/
    └── report.md
```

## 说明 / 边界
- Notion 不会自动渲染 Markdown；我们是把 Markdown 解析成 Notion Blocks。
- Markdown 渲染目前是“够用优先”：标题/列表/代码块/引用 + 部分行内格式；表格暂时降级。
- **Topics/ 是否版本化**：默认会把 `Topics/` 下的 Topic 工作区提交到 git（便于复现：raw → distilled → report）。如果你希望仓库更轻量，可以在 `.gitignore` 中忽略 `Topics/` 的部分目录（例如只忽略 `01_RawMaterials/` 或忽略整个 `Topics/`）。
- 仓库中不要提交任何密钥。API Key 放在环境变量/本地配置。

## License
MIT（如需更换许可，可提 issue）。
