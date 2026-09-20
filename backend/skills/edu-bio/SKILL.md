---
name: edu-bio
description: >-
  中学生物知识点探究页：点击细胞器/器官看功能，或按阶段播放有丝分裂。
  覆盖动物/植物细胞、有丝分裂、消化/循环/呼吸/神经系统、神经元、光合作用、DNA 双螺旋。
  失败不得编造未登记场景。不要让模型现写 HTML。
---

# 生物探究

产出一份自包含 HTML：中间示意图，右侧结构列表与说明，可选检测题。
数据由 `scripts/generate.py` 注入 `template/explore.html`，并内联 `template/explore.js`。

```bash
python3 scripts/generate.py list
python3 scripts/generate.py animal_cell ./cell.html
```

加场景：在 `generate.py` 增加 `build_*` 并登记 `REGISTRY`，同步 `skill_service.BIO_CATALOG`。
