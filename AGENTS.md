# 智课星 · Agent 导航

教师端 Web 应用：用 AI 辅助备课、出题、阅卷分析和知识图谱。  
**不要全仓扫描。** 先对照下方模块索引，只打开该功能列出的文件。

## 栈与入口

| 层 | 路径 | 技术 |
|---|---|---|
| 前端 | `frontend/` | Vue 3 + TS + Vite + Pinia + Element Plus + Tailwind |
| 后端 | `backend/app/` | FastAPI + SQLAlchemy 2.0 async + Celery |
| 编排 | `docker-compose.yml` | MySQL / Redis / RabbitMQ / MinIO / Neo4j / Qdrant |

- 前端 dev：`frontend/` → Vite `:3000`，`/api` 代理到后端 `:8000`
- 后端入口：`backend/app/main.py`，API 前缀 `/api/v1`
- 鉴权：JWT，依赖 `backend/app/api/deps.py` 的 `get_current_teacher`；写接口另加 `require_perm`
- 前端 HTTP：`frontend/src/api/index.ts`（axios），接口按业务写在 `frontend/src/api/modules.ts`
- 类型：`frontend/src/types/index.ts`
- 路由：`frontend/src/router/index.ts`（登录守卫）；侧栏：`frontend/src/components/layout/MainLayout.vue`
- 全局上下文：`frontend/src/stores/auth.ts`、`frontend/src/stores/education.ts`（学段/年级/科目）、`stores/appearance.ts`（外壳主题 paper/tech）

重活走 Celery（`backend/app/tasks/`）：`celery_worker_fast` 消费 `fast_tasks`，`celery_worker_slow` 消费 `slow_tasks`，默认并发各 2。进度经 Redis pubsub → `GET/WS /api/v1/ws/task/{task_id}`。

**不要读：** `frontend/dist/`、`**/__pycache__/`、`**/*.pyc`、`package-lock.json`。  
**不要改：** `.env` 里的密钥；`backend/app/core/proxy.py` 必须保持为 `main.py` / Celery 的最先导入。

## 数据存储（按职责）

| 存储 | 用途 |
|---|---|
| MySQL | 教师、课本、题库、课件、作业、学生成绩等业务表 |
| MinIO | 课本/题库/课件等文件（bucket 见 `backend/app/core/config.py`） |
| Redis | 会话黑名单、Celery 结果、任务进度 pubsub |
| RabbitMQ | Celery broker；快队列 `fast_tasks`、慢队列 `slow_tasks` |
| Neo4j | 知识点与关系 |
| Qdrant | 知识点向量去重（`KG_COLLECTION`） |

启动建表用 `Base.metadata.create_all`（`main.py`），Alembic 已接入但 `versions/` 目前为空。

## 后端分层（改功能时按此打开）

```
api/v1/<模块>.py     → HTTP 路由、鉴权、参数
schemas/<模块>.py    → Pydantic
models/<模块>.py     → SQLAlchemy
services/<职责>.py   → 业务 / AI / 解析 / 导出
tasks/<队列>.py      → Celery 包装（薄，真正逻辑在 service）
```

共享基础设施只在真正碰到时打开：`backend/app/core/`（config、database、security、redis、minio、neo4j、qdrant、seed）。

## 模块索引（按功能只读这些文件）

### 认证 / 教师

- 后端：`api/v1/auth.py`、`schemas/auth.py`、`models/teacher.py`、`core/security.py`、`api/deps.py`
- 前端：`views/LoginView.vue`、`stores/auth.ts`；个人信息在侧栏头像（`components/layout/ProfileDrawer.vue`），不在系统设置

### 用户 / 角色

- 后端：`api/v1/rbac.py`、`schemas/rbac.py`、`models/rbac.py`、`core/permissions.py`、`core/access.py`（共享/私有 ACL）、`services/rbac_service.py`、`core/seed.py`（`seed_rbac`）
- 前端：`views/org/`（用户、角色）；侧栏「用户管理」；协作者弹窗 `components/CollaboratorsDialog.vue`
- 约定：`.cursor/rules/rbac-org.mdc`。超管环境变量写在仓库根目录 `.env`（`SUPER_ADMIN_USERNAME` / `PASSWORD` / `EMAIL` / `REAL_NAME`），只初始化一次
- 无组织；权限 = 用户绑定角色的并集；超管 `is_super` 唯一
- 私有资源协作：点「批量设置协作者」后在弹窗里多选资源与人员；`GET /colleagues`，`PUT /resources/{type}/collaborators/batch`（type = courseware|homework|analysis|grading）
- 顶栏学段/年级/科目：非管理员且已绑定 `TeacherAssignment` 时，选项来自绑定（`stores/education.ts`）

### 学段 / 年级 / 科目

- 后端：`api/v1/education.py`、`schemas/education.py`、`models/education.py`、`core/seed.py`
- 前端：`stores/education.ts`；顶栏筛选在 `MainLayout.vue`。非超管/管理员且已绑定工作范围时，学段/年级/科目选项来自 `TeacherAssignment`。

### 工作台

- 后端：`api/v1/dashboard.py`
- 前端：`views/dashboard/DashboardView.vue`

### 课本

- 后端：`api/v1/textbook.py`、`schemas/textbook.py`、`models/textbook.py`、`services/file_service.py`（`parse_textbook_file`）、`tasks/file_tasks.py`、`services/liteparse_service.py`
- 前端：`views/textbook/TextbookView.vue`
- PDF 插图（`file_service.sync_pdf_images`）：内嵌位图（≥120px，不设总数上限）+ 有图注但由小贴图/矢量线条拼成的插图（`_figure_region` 按区域渲染，存 `images/{tb}/fig_*`）；图注按「图x-y」且字号小于正文识别，写入 `TextbookImage.caption`。可重复执行：按位图哈希 / 页码+图注去重，只补不删。老课本用 `POST /textbooks/{id}/refresh-images`（页面「补提插图」）升级，不动章节、不改已有图片 id；「重新解析」会清空章节与图片。

### 班级 / 学生

- 后端：`api/v1/classroom.py`、`api/v1/student.py`（花名册增删改）、`models/student.py`（`SchoolClass` + `Student.class_id`）、`services/classroom_service.py`
- 前端：`views/students/StudentsView.vue`；侧栏「班级/学生」
- 班级全站公共（同年级班名唯一）；学生花名册跟班走。仅超管/管理员可录入编辑（`classroom.manage`）；制作者与阅览者只读。学号在同年级全局唯一。批改布置选班级后用该班花名册。成绩模块只负责分数，不负责建班。

### 题库

- 后端：`api/v1/question.py`、`schemas/question.py`、`models/question.py`、`file_service.parse_question_file`、`ai_service.parse_questions_from_text/image`、`question_bank_service.py`（去重入库、`PATCH` 改题）
- 前端：`views/question-bank/QuestionBankView.vue`

### 课件 + 课堂互动

- 后端：`api/v1/courseware.py`、`api/v1/interaction.py`、`models/courseware.py`、`models/interaction.py`、`models/subject_prompt.py`、`services/ai_service.py`（`do_generate_courseware`）、`services/courseware_components.py`、`services/skill_service.py`、`tasks/ai_tasks.py`、`services/export_service.py`；`POST /coursewares/{id}/regenerate` 可改配置后重出；历史版本表 `courseware_versions`（可分享、可应用为当前）
- 前端：`views/courseware/`、`views/public/SessionPlay.vue`、`utils/coursewareFrame.ts`、`utils/revealDeck.ts`、`utils/lessonPage.ts`、`utils/coursewareTheme.ts`
- 呈现样式 `render_style`：`ppt` 走 `revealDeck.ts`，`html` 走 `lessonPage.ts`（单页滚动网页，可下载）
- 拼课课序：封面 → 导入 → 互动/实验 → 新知命名 → 对照 → 例题 → 小结 → 练习 → 作业（先探究再命名）；可检测目标只进 `meta.objectives`，不给学生放学习目标页
- 视觉主题 `theme`：调色板在 `services/courseware_theme.py` 与 `utils/coursewareTheme.ts`，两份必须同步；在线预览与导出的 PPT/Word/PDF 共用
- 理科确定性互动页：见下方「Skills」，失败回退 LLM HTML

### 互动动画库

- 后端：`api/v1/animation.py`、`schemas/animation.py`、`models/animation.py`、`services/animation_service.py`
- 前端：`views/animation/AnimationsView.vue`；侧栏「AI 生成 → 互动动画」
- 系统预置来自 `animation_service.system_catalog`（化学 `LAB_CATALOG` + 数学探究台 + 分子 3D + 生物 `BIO_CATALOG` + 物理 `PHYSICS_CATALOG`；启动 `ensure_system_labs` 补缺失行并同步系统元数据，不覆盖标题/HTML）；教师可从模板另存。
- 统一外壳（NOBOOK 式）：`backend/skills/_shell/nb-shell.{css,js}`，由 `animation_service.decorate_html` / `served_html` 在出 HTML 时注入（库内存的是原始 HTML）。教师预览与分享带顶栏（简介 / 画笔 / 重置 / 全屏），课件引用 `chrome=False` 只保留协议。协议：宿主 postMessage `{nb:'call', id, method}`（`config` / `getData` / `setData` / `reset` / `info`），页面回 `{nb:'reply'}` 与事件 `{nb:'event', type:'onload'|'onChange'}`；页面引擎用 `NB.register({...})` 接入。
- 可搭建类型（`SCENE_KINDS`，目前 `physics_lab` 物理实验台：电学、光学）：预览里「保存搭建」写 `spec.scene`（`PATCH /animations/{id}` 带 `scene`，系统行须先另存），「另存为我的（含搭建）」走 `POST /animations` 带 `scene`。出课勾选后写 `animation_keys`，生成时引用库 HTML，不要每次重跑 CLI。自动匹配须标签打中知识点或关键词足够强，至多 1 个实验台 + 1 个动画；对不上本课核心点不要塞实验台，化学不再兜底制氧。

### 作业 / 试卷

- 后端：`api/v1/homework.py`、`schemas/homework.py`、`models/homework.py`、`services/homework_service.py`、`export_service.build_homework_*`；`POST /homework/{id}/regenerate` 可改配置后重出卷；导出/打印默认不含参考答案，`include_answers` 可附上
- 前端：`views/homework/HomeworkView.vue`

### 批改作业 / 试卷（纸质原卷）

- 后端：`api/v1/grading.py`、`schemas/grading.py`、`models/grading.py`、`services/grading_service.py`
- 前端：`views/grading/`（布置列表、学生原卷看图手批、错题本）；手机录入公开页 `views/public/CollectPages.vue`（`/c/:token`）
- 卷面来自已生成的 `HomeworkPaper`；答卷是按学生上传的页图，不是答题卡
- 错题流水 `WrongQuestionLog`：单次布置各题错次、学生错题本、题库 `Question.wrong_count`
- 考试批完回写 `ExamResult`；作业只记对错不分到成绩模块

### 试题分析

- 后端：`api/v1/question_analysis.py`、`schemas/question_analysis.py`、`models/question_analysis.py`、`file_service.parse_analysis_file`、`ai_service.do_analyze_questions`、`export_service.build_analysis_*`
- 前端：`views/question-analysis/`

### 学生成绩

- 后端：`api/v1/student.py`、`schemas/student.py`、`models/student.py`、`services/grade_stats.py`、`ai_service.do_analyze_grades` / `do_ocr_grades`、`file_service.import_grades_from_file`
- 前端：`views/grades/GradesView.vue`

### 知识图谱

- 后端：`api/v1/knowledge.py`、`schemas/knowledge.py`、`services/knowledge_graph_service.py`、`services/knowledge_extract_service.py`、`services/embedding_service.py`、`tasks/knowledge_tasks.py`、`core/neo4j_client.py`、`core/qdrant_client.py`
- 前端：`views/knowledge/KnowledgeGraphView.vue`
- 知识点在 Neo4j，不在 MySQL；图谱全站共用，不按教师隔离

### 系统设置（LLM / 科目提示词）

- 后端：`api/v1/settings.py`、`schemas/llm_config.py`、`models/llm_config.py`、`models/teacher_setting.py`、`models/subject_prompt.py`
- 前端：`views/settings/SettingsView.vue`
- 对话大模型为系统级（`llm_configs.teacher_id IS NULL`），全站共用；LLM 调用统一走 `ai_service.build_litellm_kwargs` / `_call_llm`；API Key 加密存库

### Skills（理科课件互动页）

根目录 `backend/skills/<name>/`，接入 `services/skill_service.py` + `services/skill_runners/`。  
原则：LLM 只判题型；数值与 HTML 由 sympy + 模板确定性生成；失败返回空串，上层回退 LLM。

| skill | 学科 | 内核 |
|---|---|---|
| `edu-solid-geometry` | 数学 | `lib/geometry_kernel.py` |
| `edu-analytic-geometry` | 数学 | `lib/analytic_kernel.py` |
| `edu-chem-reaction` | 化学/生物 | `lib/reaction_kernel.py` |
| `edu-chem-lab` | 化学/科学 | 宏观实验台 `template/lab.html` + `lab2d.js` / `lab3d.js`（试剂架、2D/3D、讲解演示；制气、电解水、中和、金属与酸、氧化铜与酸、铵盐分解、铁丝燃烧、过滤、蒸发、配制溶液） |
| `edu-bio` | 生物 | 探究页 `template/explore.html`（点击细胞器/器官看功能，或分阶段播放有丝分裂；细胞、人体系统、光合作用、DNA） |
| `edu-physics` | 物理 | 实验台 `template/bench.html` + 引擎（NOBOOK 式，`kind=physics_lab`）：`circuit.js` 电学（器材库自由搭建、接线柱连线、节点电压法求解、实物图/电路图、数据记录）、`optics.js` 光学（激光/透镜/平面镜/玻璃砖光线追迹、光具座凸透镜成像）；探究页 `template/explore.html`（PhET 风格：拖动物体、滑条改 U/R/力/密度/角度，仪表即时反馈；力学含抛体/单摆/碰撞/圆周/斜面/杠杆/压强/机械能/弹簧/滑轮/万有引力，电磁含磁场/感应/安培力/库仑/电容/变压器，光学含反射折射/凸透镜，另有物态/理想气体/机械波/多普勒/光电效应） |

除各 skill 的固定解题题型外，两个数学 skill 还有**通用兜底题型**，供没有具体题面的概念课出 3D / 画板：
`solid_explore`（可旋转多面体：cube / cuboid / quad_pyramid / tetrahedron / tri_prism，讲底面与高、
体积表面积）与 `curve_explore`（圆锥曲线画板：ellipse / hyperbola / parabola / circle，拖动动点演示
定义定值、渐近线、准线、切线）。两者都在 `services/skill_runners/` 的 runner 里构造数据，模板不改。

接入计划：`docs/skill-integration-plan.md`。改某个 skill 时只读该目录 + `skill_service.py`，不要扫另外两个 skill。

## 前端页面 ↔ 路由

| 路由 | 视图 |
|---|---|
| `/login` | `LoginView.vue` |
| `/s/:token` | `public/SessionPlay.vue`（免登录） |
| `/dashboard` | `dashboard/DashboardView.vue` |
| `/textbook` | `textbook/TextbookView.vue` |
| `/question-bank` | `question-bank/QuestionBankView.vue` |
| `/students` | `students/StudentsView.vue` |
| `/courseware`、`/courseware/:id` | `courseware/*` |
| `/animations` | `animation/AnimationsView.vue`（互动动画库） |
| `/homework` | `homework/HomeworkView.vue` |
| `/grading`、`/grading/:id`、`/grading/:id/student/:studentId` | `grading/*` |
| `/c/:token` | `public/CollectPages.vue`（免登录，手机录入原卷） |
| `/wrong-questions` | `grading/WrongQuestionsView.vue` |
| `/question-analysis`、`/:id` | `question-analysis/*` |
| `/grades` | `grades/GradesView.vue` |
| `/knowledge` | `knowledge/KnowledgeGraphView.vue` |
| `/users`、`/roles` | `org/*`（用户 / 角色，需相应权限） |
| `/settings`、`/settings/:tab` | `settings/SettingsView.vue`（`models` / `prompts`） |

## 改代码约定

- 新接口：同时改 `api/v1/<模块>.py`、`frontend/src/api/modules.ts`、必要时 `types/index.ts` 与对应 View。
- 耗时任务：API 只投递 Celery，状态写模型字段（如 `parse_status` / `gen_status`），进度走 Redis+WS。
- 可见范围：共享资产全站可见；私有资源按创建人 + 协作者 + 管理员（见 `rbac-org.mdc`），不要只按当前教师过滤。
- 课件互动 HTML：优先走 skill；不要把确定性计算改回「LLM 直接写 HTML」。
- 公式渲染：前端 `utils/mathText.ts`、`utils/markdown.ts`。
