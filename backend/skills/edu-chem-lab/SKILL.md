---
name: edu-chem-lab
description: >-
  中学化学宏观虚拟实验台：学生把器材拖到台面工位、把药品拖进容器，再按步骤加热/滴加、观察现象并处理安全操作。
  剧本驱动，支持制氧气、制氢气、制二氧化碳、电解水、酸碱中和、金属与酸、碳酸氢铵分解、铁丝燃烧、过滤、蒸发结晶、配制溶液。失败不得编造未登记实验。
  触发词：虚拟实验, 实验台, 制取氧气, 制氢气, 二氧化碳, 电解水, 酸碱中和, 过滤, 蒸发, 酚酞, 验纯, 铁丝燃烧, 碳酸氢铵。
---

# 宏观化学实验台

产出一份自包含 HTML：左侧器材/药品柜，中间实验台场景，右侧步骤与观察记录。
数据由 `scripts/generate.py` 的剧本注入 `template/lab.html`，不要让模型现写 HTML。

```bash
python3 scripts/generate.py list
python3 scripts/generate.py prep_oxygen_kmno4 ./lab.html
python3 scripts/generate.py evaporation ./lab.html
```

加实验：在 `generate.py` 增加 `build_*` 并登记到 `REGISTRY`，同步 `skill_service.LAB_CATALOG`。场景不够时再改 `template/lab.html`。
