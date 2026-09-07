"""互动课件 HTML 组件规范。

这里只维护「给大模型看的说明」：告诉模型在 html 字段里可以使用哪些已注入的
样式 class、可用的库（KaTeX、Chart.js）以及一份组件目录（按需选用）。
真正的设计系统 CSS / 库注入发生在前端 iframe 包装器里（src/utils/coursewareFrame.ts），
两边的 class 命名保持一致。
"""

# 已注入的设计系统 class（前端包装器提供，模型直接使用即可，不要重写基础样式）
DESIGN_SYSTEM_SPEC = """【已注入的统一样式，请直接使用这些 class，不要重写基础样式/字体/配色】
- 根容器：<div class="stage">…</div>（已含内边距与字体）
- 文本：.title（标题）/.subtitle（副标题）/.muted（次要文字）
- 卡片：.card（圆角白底卡片）/.panel（浅灰分区）
- 按钮：.btn、.btn.primary（主色按钮）
- 布局：.row（横向flex）/.grid（自适应网格，配 style="--cols:3"）/.center（居中）
- 标记：.badge、.chip（可拖拽的小色块/标签）
- 反馈：给元素加 .correct（绿）/.wrong（红）表示对错；.hint 提示条
- 动画：.fade-in（淡入）/.pop（弹入）/.float（轻微浮动）
- 配色变量：var(--c-primary) 主色、var(--c-accent) 强调、var(--c-ok) 正确、var(--c-bad) 错误、var(--c-line) 描边
"""

# 可用库说明
LIBS_SPEC = """【页面已加载的库，可直接调用】
- KaTeX：数学/理科公式请用 \\( ... \\) 或 \\[ ... \\] 书写，会自动渲染（无需手动调用）。
- Chart.js：需要柱状/折线/饼图时，写 <canvas id="..."></canvas> 后用 new Chart(...) 渲染。
- 其余动画/交互用原生 JS + CSS/SVG 实现，禁止引入未声明的外部脚本。
"""

# 组件目录：模型按本页教学目的与科目特点，挑选 1 个最合适的来实现
COMPONENT_CATALOG = """【互动组件目录】（每个互动页选 1 个最贴合本页知识点的来做，参数/内容必须与课本一致）
1. number_line 数轴动画：在数轴上动态标点/比较大小/演示加减；适合小学数学、有理数。
2. function_plot 函数图像：用 canvas 画坐标系与函数曲线，可拖动参数观察变化；适合代数、物理。
3. geometry_svg 几何作图：用 SVG 画几何图形并高亮边/角/辅助线，可点击显示性质；适合几何。
4. drag_match 拖拽配对：左右两列，把概念与释义/图文拖拽连线，配对正确给绿色反馈；适合各科。
5. click_quiz 点选练习：单/多选题，点选后即时判定对错并给出解析；适合随堂练习。
6. flip_cards 翻牌卡片：点击卡片翻面显示答案/释义；适合字词、单词、概念记忆。
7. sortable 排序题：把打乱的步骤/事件/句子拖拽成正确顺序；适合流程、时间线、语文排序。
8. timeline 时间轴：横向时间轴展示事件节点，点击展开详情；适合历史、过程类。
9. labeled_diagram 图示标注：在示意图上点击热点显示名称/功能；适合生物结构、地理、物理装置。
10. step_reveal 分步揭示：按钮逐步展开解题/推导/实验步骤，配公式与高亮；适合例题精讲。
11. chart_viz 数据图表：用 Chart.js 呈现数据并配解读；适合数据分析、统计。
12. simulation 过程模拟：用 CSS/JS 动画演示一个动态过程（如电路、化学反应、物理运动）。
"""

# 教学法约束：避免“为互动而互动”，把互动用在刀刃上
PEDAGOGY_RULES = """【互动节点克制原则（重要）】
1. 一节课只在 1~3 个关键节点安排互动页（通常是：情境导入 / 例题精讲 / 随堂练习其中的若干处），其余环节用讲解正文、板书式小结、教师讲稿承载，不要每页都做互动。
2. 互动要服务教学主线：让学生“真正动手做”（点击/拖拽/输入并获得即时反馈），而不是装饰性动画。能用一句话讲清的知识点，不要硬做成互动。
3. 互动总时长建议控制在 10~15 分钟，单个互动聚焦一个明确的学习目标。
4. 把互动放在 type 为 process / example / interactive / activity 的幻灯片上；cover / objectives / summary / homework 等页不要放互动。"""

# 学生作答数据回收：互动页通过 window.CW 把作答结果回传给上层页面
REPORT_SPEC = """【作答数据回收（必须接入）】
页面已注入全局对象 window.CW，当学生完成一次作答/判断对错时，调用它把结果回传，便于教师看板统计：
- window.CW.report({ component:'组件类型', question:'题目或操作描述', answer:'学生的回答', correct:true/false, duration_ms:用时毫秒 })
- 便捷写法：判对时 window.CW.correct('题目', '学生答案')；判错时 window.CW.wrong('题目', '学生答案')。
要求：每个可判定对错的互动，在给出即时反馈的同时调用一次上报；若组件不涉及对错（如纯演示/拖拽探索），可只上报 {component, question, answer} 不传 correct。调用要做容错（window.CW 可能不存在时忽略）。"""

INTERACTIVE_RULES = """【互动 HTML 硬性要求】
1. 每个 html 字段是一个自包含片段：以 <div class="stage"> 开头，可含 <style> 与 <script>，不要写 <html>/<head>/<body>。
2. 只用原生 HTML/CSS/JS + 已声明的 KaTeX/Chart.js，代码必须完整可运行、无语法错误。
3. 互动要真实可操作（可点击/拖拽/输入并有即时反馈），不要只是静态图。
4. 文案、数据、题目必须紧扣本页课本知识点，使用中文。
5. 视觉上沿用注入的 .card/.btn 等 class，风格简洁现代、留白充足。
6. 按【作答数据回收】要求调用 window.CW 上报学生作答结果。"""


def build_interactive_prompt(subject_interactive_hint: str = "") -> str:
    """组装互动课件部分的提示词。subject_interactive_hint 为科目级的互动建议。"""
    parts = [
        "\n\n========== 互动课件设计规范 ==========",
        PEDAGOGY_RULES,
        DESIGN_SYSTEM_SPEC,
        LIBS_SPEC,
        COMPONENT_CATALOG,
    ]
    if subject_interactive_hint:
        parts.append(f"【本科目优先采用的互动形式】\n{subject_interactive_hint}")
    parts.append(REPORT_SPEC)
    parts.append(INTERACTIVE_RULES)
    return "\n\n".join(parts)
