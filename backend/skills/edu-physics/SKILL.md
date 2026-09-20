---
name: edu-physics
description: >-
  中学物理知识点仿真页（PhET 风格）：拖动物体、滑条改参量、仪表即时反馈。
  覆盖磁场、电磁感应、串并联、欧姆定律、力的合成、牛顿定律、物态变化、光的反射/折射、凸透镜、浮力、抛体、单摆、碰撞、圆周、斜面摩擦、库仑定律、杠杆、压强、机械能、弹簧振子、滑轮组、安培力、电容器、变压器、理想气体、机械波、多普勒、万有引力、光电效应。
  失败不得编造未登记场景。不要让模型现写 HTML。
---

# 物理探究

产出一份自包含 HTML。数据由 `scripts/generate.py` 注入 `template/explore.html`，仿真逻辑在 `template/explore.js`。

```bash
python3 scripts/generate.py list
python3 scripts/generate.py magnetic_field ./mag.html
```

布局对标 PhET：大操作台、底部滑条 + 黄色「全部重置」、右侧实时读数。加场景：在 `generate.py` 增加 `build_*`（`sim` + `controls` / `toggles` / `quiz`）并登记 `REGISTRY`，同步 `skill_service.PHYSICS_CATALOG`，必要时在 `explore.js` 增加引擎。
