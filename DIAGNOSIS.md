# ClawResearch 现状诊断（紧急排查）

时间：2026-02-17
仓库：`/home/admin/clawd/research`（symlink → `VPS/repos/research`）

## 结论（最关键的 3 个根因）

1) **目录体系曾发生过迁移/重构**：早期 Topic 可能直接落在 repo 根目录；现在标准为 `Topics/<slug>/...`。历史残留会造成“工具假设不一致”。

2) **旧版中文标题 slug 生成失败导致目录碰撞**：曾把多种中文主题都落到 `Topics/topic`，造成混写/覆盖风险。

3) **Notion 交付绑定存在“跨 Topic 复用 page_id”的历史脏数据**：当前检测到至少一个 `notion_page_id` 被两个 Topic 同时引用，会导致覆盖写入（overwrite mode）。这是“写入混乱”的直接根因之一。

---

## 1) 当前目录结构（采样）

`Topics/` 下存在：
- `moltbook-mbc-20`
- `topic`  ⚠️（旧版碰撞产物）
- `t20260215-be1cbd69`
- `t20260217-34cce0dc`
- `notion-bug`（测试）
- `healthcheck`（测试）

`doctor --scan` 当前只剩两类问题：
- `Topics/healthcheck` rawmaterials_empty
- `Topics/notion-bug` rawmaterials_empty
（属于测试目录，不是引擎核心故障。）

---

## 2) 高风险项（必须立刻修）

### 2.1 目录碰撞：`Topics/topic`
- `Topics/topic/topic.json` 显示：
  - title：三四线城市粉刷师傅转型与新机会
  - slug：topic
- 这是旧 slugify 对中文失败导致的默认目录名，未来极易再次产生碰撞。

处理建议：
- 将该目录归档到 `_archive/`，并迁移到新 slug 目录（hash slug）。

### 2.2 Notion Page ID 冲突（覆盖写入风险）
检测结果：同一个 `notion_page_id` 被两个 Topic 同时引用：
- page_id: `3069db86-8c8b-8185-832d-cea5acd1945a`
  - `Topics/moltbook-mbc-20`
  - `Topics/topic`

这会导致：任意一次交付（overwrite）都有可能把另一个主题的 Notion 页面内容清空并覆盖。

处理建议（保守止血）：
- 先**解除冲突**：为其中一个 Topic 清空 `topic.json.notion_page_id`，让其下次交付自动创建新页面。
- 之后再人工确认哪个 page 是谁的，必要时做页面内容回填。

---

## 3) 稳定性问题（架构层）

### 3.1 watchdog 路径不统一（潜在监控错位）
`watchdog.py` 使用 `~/clawd/research/state.json` 与 `~/clawd/research/watchdog.lock`，
而 orchestrator/doctor 使用硬编码 ROOT `/home/admin/clawd/research`。

当运行用户、HOME、或工作目录变化时，会出现：
- watchdog 盯着另一个 state.json
- lock/state 互相不一致 → 频繁“stale_watchdog_lock”

处理建议：
- watchdog 统一使用与 orchestrator 相同的 ROOT（建议 `Path(__file__).resolve().parent` 推导）。

### 3.2 SIGKILL / Exec failed（外部强杀）
你在 16:34 收到：`Exec failed (tidy-atl, signal SIGKILL)`。
目前 `research.log` 没有对应时间点日志，说明被杀的可能是外层 runner/格式化/转换步骤，或还未写入日志。

处理建议：
- 后续将为关键步骤增加“开始/结束”落盘日志点，并把外层超时/资源限制记录进 log（如果能拿到 runner）。

---

## 4) 修复计划（你已确认“按方案修”）

### Phase A — 止血（立即）
1. 解除 Notion page_id 冲突（避免再覆盖）。
2. 归档/隔离碰撞目录 `Topics/topic`。

### Phase B — 目录重整（安全迁移，不删除）
1. 建立 `_archive/` 保存历史/测试/碰撞目录。
2. 迁移内容到新 slug 目录，并更新 topic.json。

### Phase C — 稳定性修复（代码层）
1. watchdog.py 路径统一。
2. 对 state.json 字段进行“最小稳定 schema”约束（避免遗留字段误导）。
3. doctor 增强：检测 `notion_page_id` 冲突并提示/可选自动修复。
