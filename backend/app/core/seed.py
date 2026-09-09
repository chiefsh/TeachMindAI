"""基础数据种子：学段 / 年级 / 科目
在建表后由 lifespan 调用，确保下拉选项有数据。
（不依赖 MySQL 的 init.sql，因为后者在 SQLAlchemy 建表之前执行会失败）
"""
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.education import SchoolLevel, Grade, Subject
from app.models.subject_prompt import SubjectPromptTemplate

SCHOOL_LEVELS = [
    {"id": 1, "name": "小学", "sort_order": 1},
    {"id": 2, "name": "初中", "sort_order": 2},
    {"id": 3, "name": "高中", "sort_order": 3},
]

GRADES = [
    {"id": 1,  "school_level_id": 1, "name": "一年级", "sort_order": 1},
    {"id": 2,  "school_level_id": 1, "name": "二年级", "sort_order": 2},
    {"id": 3,  "school_level_id": 1, "name": "三年级", "sort_order": 3},
    {"id": 4,  "school_level_id": 1, "name": "四年级", "sort_order": 4},
    {"id": 5,  "school_level_id": 1, "name": "五年级", "sort_order": 5},
    {"id": 6,  "school_level_id": 1, "name": "六年级", "sort_order": 6},
    {"id": 7,  "school_level_id": 2, "name": "初一",   "sort_order": 1},
    {"id": 8,  "school_level_id": 2, "name": "初二",   "sort_order": 2},
    {"id": 9,  "school_level_id": 2, "name": "初三",   "sort_order": 3},
    {"id": 10, "school_level_id": 3, "name": "高一",   "sort_order": 1},
    {"id": 11, "school_level_id": 3, "name": "高二",   "sort_order": 2},
    {"id": 12, "school_level_id": 3, "name": "高三",   "sort_order": 3},
]

SUBJECTS = [
    # 小学
    {"id": 1,  "school_level_id": 1, "name": "语文",     "sort_order": 1},
    {"id": 2,  "school_level_id": 1, "name": "数学",     "sort_order": 2},
    {"id": 3,  "school_level_id": 1, "name": "英语",     "sort_order": 3},
    {"id": 4,  "school_level_id": 1, "name": "道德与法治", "sort_order": 4},
    {"id": 5,  "school_level_id": 1, "name": "科学",     "sort_order": 5},
    {"id": 6,  "school_level_id": 1, "name": "音乐",     "sort_order": 6},
    {"id": 7,  "school_level_id": 1, "name": "美术",     "sort_order": 7},
    {"id": 8,  "school_level_id": 1, "name": "体育",     "sort_order": 8},
    # 初中
    {"id": 9,  "school_level_id": 2, "name": "语文",     "sort_order": 1},
    {"id": 10, "school_level_id": 2, "name": "数学",     "sort_order": 2},
    {"id": 11, "school_level_id": 2, "name": "英语",     "sort_order": 3},
    {"id": 12, "school_level_id": 2, "name": "物理",     "sort_order": 4},
    {"id": 13, "school_level_id": 2, "name": "化学",     "sort_order": 5},
    {"id": 14, "school_level_id": 2, "name": "生物",     "sort_order": 6},
    {"id": 15, "school_level_id": 2, "name": "历史",     "sort_order": 7},
    {"id": 16, "school_level_id": 2, "name": "地理",     "sort_order": 8},
    {"id": 17, "school_level_id": 2, "name": "道德与法治", "sort_order": 9},
    # 高中
    {"id": 18, "school_level_id": 3, "name": "语文",     "sort_order": 1},
    {"id": 19, "school_level_id": 3, "name": "数学",     "sort_order": 2},
    {"id": 20, "school_level_id": 3, "name": "英语",     "sort_order": 3},
    {"id": 21, "school_level_id": 3, "name": "物理",     "sort_order": 4},
    {"id": 22, "school_level_id": 3, "name": "化学",     "sort_order": 5},
    {"id": 23, "school_level_id": 3, "name": "生物",     "sort_order": 6},
    {"id": 24, "school_level_id": 3, "name": "历史",     "sort_order": 7},
    {"id": 25, "school_level_id": 3, "name": "地理",     "sort_order": 8},
    {"id": 26, "school_level_id": 3, "name": "政治",     "sort_order": 9},
    {"id": 27, "school_level_id": 3, "name": "信息技术", "sort_order": 10},
]


async def seed_education_data():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(SchoolLevel.id))
        if existing.scalars().first():
            return  # 已有数据，跳过

        db.add_all([SchoolLevel(**r) for r in SCHOOL_LEVELS])
        db.add_all([Grade(**r) for r in GRADES])
        db.add_all([Subject(**r) for r in SUBJECTS])
        await db.commit()


# 各科目课件生成的默认提示词（教学侧重 + 适合的互动形式）
SUBJECT_PROMPTS = {
    "语文": {
        "prompt": "突出朗读感悟与文本细读：梳理字词、句段、写作手法与情感主旨；多用情境导入和问题链引导学生品味语言；安排诵读、批注、仿写、讨论等环节，培养语感与表达。",
        "interactive_guidance": "适合：生字词卡片、重点句段批注高亮、朗读节奏标注、按情节排序的拖拽、根据情境填词的小练习。",
    },
    "数学": {
        "prompt": "强调概念的来龙去脉与逻辑推导，而非直接给结论；每个知识点配「概念—例题分步讲解—变式训练」；突出数形结合，鼓励学生动手算、动脑想，预设易错点并点拨。",
        "interactive_guidance": "适合：数轴/坐标系动画、函数图像动态演示、几何图形 SVG 作图与变换、分步揭示的例题、可输入作答的随堂演算小题。",
    },
    "英语": {
        "prompt": "围绕「词汇—句型—语篇—运用」展开，创设真实语境进行听说读写训练；新词配例句与搭配，句型做替换操练，安排情景对话与口语输出；全程可适当使用英文指令并配中文释义。",
        "interactive_guidance": "适合：单词翻卡记忆、句型替换填空、情景对话角色扮演、听力/选词拖拽配对、图文匹配小游戏。",
    },
    "物理": {
        "prompt": "从生活现象与实验出发建立物理概念，强调过程分析与受力/能量等模型；讲清公式的物理意义与适用条件；配例题演示规范解题步骤，重视科学探究与误差分析。",
        "interactive_guidance": "适合：实验过程模拟动画、受力分析图、运动/电路等可视化演示、参数可调的交互模型、图表数据分析。",
    },
    "化学": {
        "prompt": "以实验为核心建立微观—宏观联系，讲清反应原理、现象与化学方程式；强调规范实验操作与安全；通过对比与归纳帮助记忆元素、物质性质与变化规律。",
        "interactive_guidance": "适合：实验装置与反应过程动画、微观粒子运动示意、化学方程式配平练习、物质性质对比表、安全操作判断题。",
    },
    "生物": {
        "prompt": "围绕结构与功能相适应的主线，结合图示与实例讲解概念；强调观察、比较与归纳；联系生活与健康，培养科学思维与生命观念。",
        "interactive_guidance": "适合：细胞/器官结构标注图、生理过程动画、分类与配对、实验现象观察、概念图梳理。",
    },
    "历史": {
        "prompt": "以时间为轴、史料为据，讲清历史事件的背景—过程—影响与内在因果；引导论从史出、辩证看待；通过对比与归纳形成时空观念与历史解释。",
        "interactive_guidance": "适合：时间轴动画、历史地图标注、史料阅读与设问、事件因果连线、人物/事件配对。",
    },
    "地理": {
        "prompt": "突出地图与空间分析能力，结合自然与人文地理讲清「在哪里—为什么—怎么样」；联系区域案例与生活实际，培养综合思维与人地协调观。",
        "interactive_guidance": "适合：地图分层标注、气候/地形示意动画、数据图表分析、区域对比表、读图填空。",
    },
    "道德与法治": {
        "prompt": "贴近学生生活创设情境，围绕道德认知、法治意识与价值判断展开；通过案例辨析、讨论与角色体验引导明理践行，落实核心素养。",
        "interactive_guidance": "适合：情境案例辨析、观点投票、两难问题讨论、行为判断对错、角色扮演。",
    },
    "政治": {
        "prompt": "讲清基本概念与原理，联系时政热点与现实案例进行分析论证；引导运用辩证思维与学科术语规范作答，培养政治认同与公共参与意识。",
        "interactive_guidance": "适合：时政案例分析、观点辨析投票、概念关系图、材料设问、判断与论证小题。",
    },
    "科学": {
        "prompt": "以探究为中心，从问题与现象出发，经历「猜想—实验—观察—结论」的过程；鼓励动手与合作，培养好奇心与科学方法。",
        "interactive_guidance": "适合：实验模拟动画、现象观察记录、简单数据图表、分类配对、动手小实验指引。",
    },
    "信息技术": {
        "prompt": "理论与上机实践结合，讲清原理后给出清晰的操作步骤与示例；鼓励动手实践与作品创作，培养计算思维与信息素养。",
        "interactive_guidance": "适合：操作步骤分步演示、流程图、代码/命令示例、判断与排序练习、可交互的小演示。",
    },
    "音乐": {
        "prompt": "围绕聆听、感受与表现，讲解节奏、旋律、情感与文化背景；安排欣赏、视唱、律动等活动，激发审美体验与表现欲。",
        "interactive_guidance": "适合：节奏点击练习、旋律线可视化、乐器/曲目配对、聆听辨析、律动跟做。",
    },
    "美术": {
        "prompt": "围绕欣赏与创作，讲解造型、色彩、构图等要素与艺术风格；通过作品赏析与动手创作，培养审美感知与创意表达。",
        "interactive_guidance": "适合：作品赏析高亮标注、色彩/构图对比、风格配对、创作步骤演示、调色小练习。",
    },
    "体育": {
        "prompt": "围绕运动技能与健康知识，讲清动作要领、练习方法与安全注意；结合示范与分解步骤，强调循序渐进与运动习惯养成。",
        "interactive_guidance": "适合：动作分解示意、要领要点卡、安全判断、练习计划安排、动图演示。",
    },
}

# 没有专属模板时的通用兜底提示词
GENERIC_SUBJECT_PROMPT = (
    "结合本学科特点设计课件：讲解要具体充实、循序渐进，配合恰当的例子、图示与课堂活动，"
    "突出重点、突破难点，帮助学生理解并能运用所学。"
)


async def seed_subject_prompts():
    """写入各科目的系统默认提示词（teacher_id 为空）。仅在首次为空时写入。"""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(SubjectPromptTemplate.id).where(SubjectPromptTemplate.teacher_id.is_(None))
        )
        if existing.scalars().first():
            return
        db.add_all([
            SubjectPromptTemplate(
                teacher_id=None,
                subject_name=name,
                prompt=cfg["prompt"],
                interactive_guidance=cfg.get("interactive_guidance"),
            )
            for name, cfg in SUBJECT_PROMPTS.items()
        ])
        await db.commit()


async def seed_rbac_data():
    """权限目录、系统角色、超级管理员（只建一次）。"""
    from app.core.config import settings
    from app.services.rbac_service import seed_rbac
    async with AsyncSessionLocal() as db:
        await seed_rbac(db, settings)
