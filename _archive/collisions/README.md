# collisions archive

这里存放历史目录碰撞/命名异常导致的 Topic 工作区（不删除，仅隔离）。

- `Topics_topic__20260215_slug-collision/`
  - 原路径：`Topics/topic`
  - 根因：旧版 slugify 对中文标题返回空串，最终落到默认 slug `topic`，导致潜在多 Topic 混写。
  - 该目录 **不应再被 orchestrator 作为正常 Topic 使用**。
