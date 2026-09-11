# Skill 接入课件生成 · 落地实施清单

> 目标：在理科可确定性求解的知识点上，用「LLM 判类别 + sympy 精确计算 + 模板确定性渲染」替换「LLM 现编互动 HTML」，根治空白/转义/答案不一致。
>
> 原则：纯增益、可独立验证、随时可停；不命中或失败一律回退现有 LLM 流程。

## 全局约定
- 后端根：`backend/`；skill 根：`backend/skills/<skill-name>/`
- 新增服务文件：`backend/app/services/skill_service.py`
- 新增 runner：`backend/app/services/skill_runners/`
- 接入点：`backend/app/services/ai_service.py` 的 `_generate_lesson_content`（互动页生成处）
- 前端：**全程零改动**（整页 HTML 走已有 `wrapInteractiveHtml`→`createIframeBlob`→iframe）

---

## 里程碑 M0 · 公共基础设施（所有 skill 的前置）
依赖：无。必须最先完成。

- [ ] M0-1 `requirements.txt` 增加 `sympy`
- [ ] M0-2 确认 `.dockerignore` 未排除 `skills/`；`Dockerfile` COPY 了 `skills/`
- [ ] M0-3 部署确认 iframe 可访问 CDN（Three.js/MathJax/KaTeX）；内网无外网则登记待办
- [ ] M0-4 新建 `skill_service.py` 骨架（能力表 + router/renderer 预留）
- [ ] M0-5 `_generate_lesson_content` ① 层插入分发骨架（routed 恒 None，不影响现有流程）

验收：`pip install` 成功；`import sympy` 通过；课件生成行为与改动前一致。

---

## 里程碑 M1 · 立体几何阶段 1（端到端闭环）
依赖：M0。

- [ ] M1-1 新建 `skill_runners/solid_geometry_runner.py`（line_plane_angle, volume）
- [ ] M1-2 能力表登记 `edu-solid-geometry`
- [ ] M1-3 `route_math_point()` 路由（仅线面角/体积）
- [ ] M1-4 `render_solid_geometry_html()` 子进程 + timeout + 失败返回空
- [ ] M1-5 接入点接线（数学学科 → 路由 → renderer）

验收：runner 独立跑通；端到端命中并渲染；非数学回退；容错降级。

---

## 里程碑 M2 · 立体几何阶段 2（题型扩展）
依赖：M1。三题型独立，可逐个加。

- [ ] M2-1/2 异面直线 `solve_cube_skew_lines` + `build_cube_skew_lines_data`（√3/3）
- [ ] M2-3/4 二面角 `solve_tetra_dihedral` + `build_tetra_dihedral_data`（1/3）
- [ ] M2-5/6 点面距 `solve_cube_point_plane_distance` + `build_...`（a√3/3）
- [ ] M2-7 runner 增 3 分支
- [ ] M2-8 能力表 + 路由 prompt 扩展

---

## 里程碑 M3 · 解析几何接入
依赖：M0（统一数学路由建议 M1 后）。skill 内部零改动。

- [x] M3-1 能力表登记 `edu-analytic-geometry`（6 题型）
- [x] M3-2 `route_math_point` 升级为统一数学路由（立体+解析）
- [x] M3-3 `render_analytic_geometry_html()`（通用 `_render_via_cli` 子进程调 CLI）
- [x] M3-4 按 skill 分发（`_RENDERERS` 表）

题型：ellipse_dot_range / ellipse_chord_range / ellipse_area_max / ellipse_slopeprod_const / parabola_dot_const / hyperbola_ecc_range

---

## 里程碑 M4 · 化学接入
依赖：M0（独立，可并行）。skill 内部零改动。

- [x] M4-1 能力表登记 `edu-chem-reaction`（subjects 含 化学、生物）
- [x] M4-2 `route_chem_point()` 独立化学路由
- [x] M4-3 `render_chem_reaction_html()`（复用 `_render_via_cli`）
- [x] M4-4 化学/生物学科分发（`maybe_generate_skill_html` 按学科选路由器）
- [x] M4-5 确认 RDKit 不装（化学 skill 仅依赖 sympy，未引入 RDKit）

题型：combustion_ch4 / combustion_h2 / electrolysis_water / redox_na_cl2 / esterification / glucose_combustion

---

## 里程碑 M5 · 宏观化学实验台
依赖：M0。与分子 3D（M4）并列，不改 `edu-chem-reaction` 模板。

- [x] 课件 `want_virtual_lab` / `virtual_lab_key` 落库，创建弹窗可指定
- [x] 新建 `edu-chem-lab`（写实器材实验台 + 11 个常见实验；`GET /coursewares/lab-experiments` 为目录数据源）
- [x] `route_chem_lab_point` + `render_chem_lab_html`；教师勾选时至少一页实验台

---

## 依赖顺序
```
M0（必须最先）
 ├─► M1 ─► M2   （立体几何：阶段1→阶段2）
 ├─► M3         （解析几何）
 └─► M4         （化学，可并行）
```
最短可演示：M0 → M1。

## 全局验收
- G-1 三学科各≥1 知识点端到端命中并渲染
- G-2 非理科/不匹配 100% 回退，无异常
- G-3 子进程超时/崩溃自动降级，任务不失败
- G-4 整页 HTML 在 iframe 正常显示
- G-5 关闭全部 skill 后行为与接入前一致

## 风险登记
| 风险 | 处置 |
|---|---|
| runner parents 层级错 | 部署前实跑核对 |
| 内网无 CDN | 库本地化/白名单 |
| spec 尺寸不规整 | 阶段2 用 is_clean 筛 |
| 子进程性能 | 仅命中时触发；必要时进程内优化 |
| 演示题≠课本原题 | 定位为概念演示，标题标注「以…为例」 |
| 三 skill 模块名冲突 | 统一走子进程隔离 |
