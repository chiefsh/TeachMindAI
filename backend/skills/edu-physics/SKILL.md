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

## 物理实验台（NOBOOK 式自由搭建）

带 `engine` 字段的场景走通用实验台 `template/bench.html`（标记 `edu-bench:1`），按 `generate.BENCH_ENGINES`
内联对应引擎：`circuit` → `circuit.js`，`optics` → `optics.js`。布局统一：左侧实验指导（目的 / 步骤自动判定 /
数据记录 / 讨论题）、中间实验台（HUD 读数、底部工具条、撤销重做）、右侧器材库。

### 电学（`engine: "circuit"`）
右侧器材库（电池组 / 开关 / 小灯泡 / 定值电阻 / 滑动变阻器 / 电流表 / 电压表），拖到台上自由摆放、旋转、删除；
从接线柱拖出导线吸附到另一个接线柱；节点电压法实时求解（灯丝电阻随温度变化、电表量程与正负接线柱、短路 / 超量程 / 烧灯警示）；
实物图 ⇄ 电路图切换、电流方向流动点、撤销重做、数据记录与 I–U 图；左侧实验指导按 `steps[].check` 自动判定。

场景 JSON：`{parts: [{id, type, x, y, rot, props}], wires: [{a: [part_id, 接线柱], b: [...]}], mode, records}`，
通过外壳协议 `getData` / `setData` 读写，教师保存到动画 `spec.scene`。`check.type` 可选：
`closed_loop` / `lit` / `series` / `parallel` / `ammeter` / `voltmeter_across`(target) / `rheostat_in` / `records`(min) / `rated`。

### 光学（`engine: "optics"`）

器材：激光笔（颜色 / 开关）、蜡烛、凸透镜 / 凹透镜（焦距 cm）、平面镜、玻璃砖、半圆形玻璃砖（折射率 n）、光屏。
二维光线追迹：镜面反射、理想薄透镜、斯涅尔折射（含全反射与弱反射光）；蜡烛 + 透镜按成像公式求像，
光屏离像距越远像越模糊，旁边小窗显示光屏上的像；虚像画虚线。拖手柄旋转（Shift 吸附 15°）、`[` `]` 微调；
工具条可开关法线与角度、烛焰光线、焦点。长度单位 10 = 1 cm。`rail: {y, x0, len_cm}` 开启光具座
（蜡烛 / 透镜 / 光屏只能沿刻度尺左右移动，吸附 1 cm）。

场景 JSON：`{engine: "optics", parts, records, showNormal, showRays}`。`check.type`：
`hit`(target=器材类型) / `tir` / `image`(kind=reduced|equal|enlarged|virtual，成过一次即算) / `records`(min)。
`record.mode = "lens"` 时记录 u、v、像的性质，否则记录入射角与反射角 / 折射角。

在 `PHYSICS_CATALOG` 登记时写 `"kind": "physics_lab"`。
