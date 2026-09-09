"""权限码目录与系统角色预设。系统角色每次启动与此对齐；自定义角色不覆盖。"""

# (code, module, name)
PERMISSION_CATALOG: list[tuple[str, str, str]] = [
    ("user.view", "用户管理", "查看用户"),
    ("user.manage", "用户管理", "增删改用户"),
    ("role.view", "角色管理", "查看角色"),
    ("role.manage", "角色管理", "配置角色权限"),
    ("settings.llm", "系统设置", "配置大模型"),
    ("settings.prompt", "系统设置", "配置系统提示词"),
    ("textbook.view", "课本", "查看"),
    ("textbook.manage", "课本", "上传与增删改"),
    ("question.view", "题库", "查看"),
    ("question.manage", "题库", "增删改"),
    ("classroom.view", "班级学生", "查看"),
    ("classroom.manage", "班级学生", "录入与编辑"),
    ("courseware.view", "课件", "查看"),
    ("courseware.create", "课件", "创建"),
    ("courseware.edit", "课件", "编辑"),
    ("homework.view", "作业试卷", "查看"),
    ("homework.create", "作业试卷", "创建"),
    ("homework.edit", "作业试卷", "编辑"),
    ("analysis.view", "试题分析", "查看"),
    ("analysis.create", "试题分析", "创建"),
    ("analysis.edit", "试题分析", "编辑"),
    ("grading.view", "批改", "查看"),
    ("grading.create", "批改", "创建"),
    ("grading.edit", "批改", "编辑"),
    ("wrong_question.view", "错题本", "查看"),
    ("grade.view", "学生成绩", "查看"),
    ("grade.manage", "学生成绩", "管理"),
    ("knowledge.view", "知识图谱", "查看"),
    ("knowledge.manage", "知识图谱", "管理"),
    ("resource.view_all", "资源范围", "查看全部资源"),
]

ALL_PERM_CODES: frozenset[str] = frozenset(c[0] for c in PERMISSION_CATALOG)

# 制作者：课件/作业/试题分析/批改可创建编辑；课本与班级只读；题库与学情分析全开
CREATOR_PERMS: frozenset[str] = frozenset({
    "textbook.view",
    "question.view", "question.manage",
    "classroom.view",
    "courseware.view", "courseware.create", "courseware.edit",
    "homework.view", "homework.create", "homework.edit",
    "analysis.view", "analysis.create", "analysis.edit",
    "grading.view", "grading.create", "grading.edit",
    "wrong_question.view",
    "grade.view", "grade.manage",
    "knowledge.view", "knowledge.manage",
})

# 阅览者：教学资源 / AI 生成 / 学情分析 仅查看
REVIEWER_PERMS: frozenset[str] = frozenset({
    "textbook.view",
    "question.view",
    "classroom.view",
    "courseware.view",
    "homework.view",
    "analysis.view",
    "grading.view",
    "wrong_question.view",
    "grade.view",
    "knowledge.view",
})

SYSTEM_ROLES: list[dict] = [
    {"code": "super_admin", "name": "超级管理员", "is_super": True, "perms": ALL_PERM_CODES},
    {"code": "admin", "name": "管理员", "is_super": False, "perms": ALL_PERM_CODES},
    {"code": "creator", "name": "制作者", "is_super": False, "perms": CREATOR_PERMS},
    {"code": "reviewer", "name": "阅览者", "is_super": False, "perms": REVIEWER_PERMS},
]

MENU_PERM: dict[str, str] = {
    "/dashboard": "",
    "/textbook": "textbook.view",
    "/question-bank": "question.view",
    "/students": "classroom.view",
    "/courseware": "courseware.view",
    "/homework": "homework.view",
    "/question-analysis": "analysis.view",
    "/grading": "grading.view",
    "/wrong-questions": "wrong_question.view",
    "/grades": "grade.view",
    "/knowledge": "knowledge.view",
    "/settings/models": "settings.llm",
    "/settings/prompts": "settings.prompt",
    "/users": "user.view",
    "/roles": "role.view",
}


def implies_view(code: str) -> str | None:
    """manage/create/edit 隐含同模块 view。"""
    for suffix in (".manage", ".create", ".edit"):
        if code.endswith(suffix):
            return code[: -len(suffix)] + ".view"
    return None
