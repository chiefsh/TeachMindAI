#!/usr/bin/env python3
"""把分享课件改写成可进课堂的「溶液的酸碱性」课时，并快照旧版。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pymysql

TOKEN = "UqgaGPSwto5U0zOD1_p0jQ"
LAB_HTML = Path(__file__).with_name("ph_lab.html").read_text(encoding="utf-8")
NEW_TITLE = "溶液的酸碱性（指示剂与pH）"


def slides() -> list[dict]:
    return [
        {
            "type": "cover",
            "index": 1,
            "title": "溶液的酸碱性",
            "subtitle": "指示剂与 pH · 给溶液做酸碱体检",
            "bullets": [],
            "content": "",
            "notes": "开场先摆三杯无色液体：白醋、矿泉水、肥皂水。问：看起来差不多，怎样拿出证据说明谁酸谁碱？今天只解决这件事，酸、碱、盐的通性和中和方程式留到后面课时。",
        },
        {
            "type": "objectives",
            "index": 2,
            "title": "这节课要会做的四件事",
            "subtitle": "目标可检测，不写空泛的“理解某某标题”",
            "bullets": [
                "能说出紫色石蕊、无色酚酞在酸性、中性、碱性溶液中的颜色；特别要记住：酚酞在酸性和中性都无色。",
                "会用 pH 判断：小于 7 酸性、等于 7 中性、大于 7 碱性；并且知道 pH 越小酸性越强，越大碱性越强。",
                "会描述 pH 试纸的规范操作：玻璃棒蘸取、点在干燥试纸上、对照比色卡、读出大约值。",
                "能对生活样品（食醋、石灰水、食盐水、肥皂水）说出“类别 + 依据”，而不是只猜味道。",
            ],
            "content": "本节是酸碱盐单元的第一课时：先学会给溶液做“酸碱体检”，不展开酸、碱、盐的通性，也不写中和反应方程式。",
            "notes": "把目标读成学生能做的事。课末用随堂四题回扣，不要只在开头展示一次。",
        },
        {
            "type": "process",
            "index": 3,
            "title": "三杯无色液体",
            "subtitle": "先观察、再猜想、后追问证据",
            "bullets": [],
            "steps": [
                {
                    "title": "看",
                    "detail": "白醋、矿泉水、肥皂水都近乎无色。单靠眼睛，分不出谁酸谁碱。",
                },
                {
                    "title": "猜",
                    "detail": "凭生活经验先说：哪一杯可能酸？哪一杯可能碱？允许猜错，但要说出理由。",
                },
                {
                    "title": "问",
                    "detail": "化学课不能停在“我觉得”。用什么试剂能把酸碱性变成看得见的颜色？怎样比较谁更酸？由此引出石蕊、酚酞和 pH 试纸。",
                },
            ],
            "content": "导入要定向：不是“从生活出发”这句空话，而是把学生逼到“必须做实验”这一步。",
            "notes": "学生若说“醋有酸味所以是酸”，先肯定生活经验，再追问：食盐水有咸味却接近中性，味道不能当证据。石灰水几乎没味道，却显碱性。",
        },
        {
            "type": "knowledge",
            "index": 4,
            "title": "指示剂：把酸碱性变成颜色",
            "subtitle": "先记实验事实，再防三个坑",
            "bullets": [
                "紫色石蕊试液：遇酸变红，遇中性仍为紫色，遇碱变蓝。",
                "无色酚酞试液：遇酸性、中性都无色，遇碱变红。",
                "指示剂只判断“酸、碱、中性”这一类，不能准确比较谁更酸、谁更碱。",
            ],
            "content": "### 先用一句话说清楚\n酸碱指示剂像会变色的信号灯，不是温度计。它告诉你溶液偏酸、偏碱还是中性，但不读出强弱的刻度。\n\n### 三个最容易错的地方\n- 酚酞遇酸不是“变成无色”，它本来就是无色；酸性、中性看起来一样，所以不能根据“酚酞不变红”就说一定是酸。\n- 石蕊遇蒸馏水仍是紫色。中性不是“没有颜色”，而是保持指示剂原来的紫色。\n- 白醋和柠檬水都显酸性，但酸性强弱要看 pH，不能靠指示剂的颜色深浅乱比。",
            "notes": "板书只留一张表：石蕊 红/紫/蓝，酚酞 无色/无色/红。口头强调“酚酞本来无色”这一句，课上至少重复两遍。",
        },
        {
            "type": "comparison",
            "index": 5,
            "title": "石蕊和酚酞，不要记混",
            "subtitle": "课堂最常见的一对对照",
            "left_title": "紫色石蕊试液",
            "right_title": "无色酚酞试液",
            "columns": [
                {
                    "title": "紫色石蕊试液",
                    "items": [
                        "本身是紫色",
                        "酸性：变红",
                        "中性：仍为紫色",
                        "碱性：变蓝",
                        "三种情况三种颜色，适合区分酸、碱、中性",
                    ],
                },
                {
                    "title": "无色酚酞试液",
                    "items": [
                        "本身无色",
                        "酸性：仍无色",
                        "中性：仍无色",
                        "碱性：变红",
                        "变红只能说明显碱性；不变红不能确定是酸还是中性",
                    ],
                },
            ],
            "bullets": [],
            "content": "记口诀可以，但口诀要完整：石蕊酸红碱蓝中性紫；酚酞遇碱红，酸和中性都无色。",
            "notes": "抽问：某无色溶液滴酚酞仍无色，能不能说一定是酸？标准答案：不能，可能是酸，也可能是中性。这就是下一页例题的埋伏。",
        },
        {
            "type": "process",
            "index": 6,
            "title": "pH 试纸：看出强弱",
            "subtitle": "课标要求会用，操作比背数字更重要",
            "bullets": [],
            "steps": [
                {
                    "title": "取液",
                    "detail": "用玻璃棒蘸取待测液。不要把试纸直接伸进试剂瓶，会污染整瓶药品。",
                },
                {
                    "title": "点纸",
                    "detail": "点在干燥的 pH 试纸上。不要先用水把试纸润湿，否则相当于稀释，读数会往 7 靠。",
                },
                {
                    "title": "比色",
                    "detail": "在约 30 秒内对照比色卡。试纸颜色是连续变化的，读的是大约值。",
                },
                {
                    "title": "读数",
                    "detail": "pH 小于 7 酸性，等于 7 中性，大于 7 碱性。pH 越小酸性越强，越大碱性越强。",
                },
            ],
            "content": "### 指示剂和 pH 试纸分工不同\n指示剂像信号灯，只报告类别；pH 试纸像体检单，能看出大致强弱。溶液本身不会因为测 pH 就变成彩虹色，变色的是试纸。\n\n### 常用大约值（帮助学生建立感觉）\n食醋大约 3，纯水、食盐水大约 7，肥皂水大约 10，澄清石灰水大约 11。胃液更酸，肥皂水偏碱，都不必要求背全表，但要会用试纸核实。",
            "notes": "演示时故意做一个反例：把试纸伸进瓶口，问学生为什么不行。再强调：pH=5 和 pH=3 都是酸，3 更酸。",
        },
        {
            "type": "interactive",
            "index": 7,
            "title": "动手：给溶液做酸碱体检",
            "subtitle": "先观察颜色，再下诊断，最后才公布 pH",
            "bullets": [
                "样品用白醋、汽水、蒸馏水、食盐水、肥皂水、石灰水；未知溶液可自己调。",
                "烧杯颜色跟所选试剂走：石蕊只有红/紫/蓝，酚酞只有无色/红，彩虹色只出现在 pH 试纸上。",
                "没滴试剂就判断，系统会拦住：化学课要实验证据。",
            ],
            "content": "建议课堂用法：先全班测白醋（石蕊变红），再测石灰水（酚酞变红），再测蒸馏水（石蕊仍紫）。最后放手让学生测未知溶液，并完成当堂快问。",
            "notes": "巡视时盯两件事：1）有没有把彩虹色当成石蕊；2）酚酞不变红时，有没有错误地写成“一定是酸”。讲评时揭开 pH，回扣“先观察后解释”。",
            "html": LAB_HTML,
        },
        {
            "type": "example",
            "index": 8,
            "title": "例题：酚酞不变红，能说一定是酸吗？",
            "subtitle": "中考高频陷阱，当堂拆开",
            "prompt": "向某无色溶液中滴入无色酚酞试液，溶液仍为无色。下列判断正确的是？（　　）\nA. 该溶液一定显酸性\nB. 该溶液一定显碱性\nC. 该溶液可能显酸性，也可能显中性\nD. 该溶液一定显中性",
            "solution": "选 C。\n酚酞只在碱性溶液中变红；在酸性、中性溶液中都保持无色。题目只告诉“仍为无色”，只能排除碱性，不能在酸性和中性之间做选择。\n若要进一步确定，应改用紫色石蕊（中性仍紫、酸性变红）或 pH 试纸。",
            "content": "选 **C**。\n\n酚酞只在碱性溶液中变红；在酸性、中性溶液中都保持无色。题目只告诉“仍为无色”，只能排除碱性，不能在酸性和中性之间做选择。\n\n若要进一步确定，应改用紫色石蕊（中性仍紫、酸性变红）或 pH 试纸。\n\n- A 错在把“可能是酸”说成“一定是酸”\n- B 错在忽略了酚酞遇碱必红，现在没红，不可能是碱\n- D 错在同样把“可能”说成“一定”",
            "bullets": [],
            "notes": "做完立刻追问：如果改成滴紫色石蕊后仍为紫色，结论是什么？——接近中性。让学生体会：换试剂，信息量不同。",
        },
        {
            "type": "exercise",
            "index": 9,
            "title": "随堂练习",
            "subtitle": "独立完成后，对照教师讲稿里的判断依据",
            "bullets": [
                "无色酚酞滴入某无色溶液后变红。该溶液一定显什么性？依据是什么？",
                "紫色石蕊滴入蒸馏水，颜色如何？这说明中性溶液有什么特点？",
                "甲溶液 pH=5，乙溶液 pH=3，谁的酸性更强？只滴石蕊，能不能比较出强弱？",
                "小明把 pH 试纸伸进汽水瓶口测酸碱性。指出两处不规范，并写出正确步骤。",
            ],
            "content": "先自己写判断依据，再看教师讲稿。对答案不是目的，能说出“因为……”才算过关。",
            "notes": "参考：1）一定显碱性，酚酞遇碱变红。2）仍为紫色；中性时石蕊不变成别的颜色。3）乙更强；石蕊遇酸都变红，看不出谁更酸，要用 pH。4）污染试剂、读数不准；正确：蘸取、点干燥试纸、比色、读数。润湿试纸也不对。",
        },
        {
            "type": "summary",
            "index": 10,
            "title": "今天带走这四句话",
            "subtitle": "让学生复述，不要老师再念一遍标题",
            "bullets": [
                "石蕊：酸红、中紫、碱蓝。",
                "酚酞：碱红；酸和中性都无色——不变红不能说一定是酸。",
                "pH：小于 7 酸，等于 7 中，大于 7 碱；越小酸性越强，越大碱性越强。",
                "pH 试纸：蘸取、点纸、比色、读数；试纸不能伸进瓶口，也不能先用水润湿。",
            ],
            "content": "### 下节预告，今天先不展开\n如果向已经变红的酚酞碱溶液里慢慢加酸，红色会褪去。那是酸碱中和，溶液从碱性转到中性或酸性。方程式和下节实验台留到下一课时，今天只要能解释：红色褪了，说明碱性减弱或消失。",
            "notes": "收课抽三名学生各说一句。中和实验台不要在本课主活动里做，避免还没建立酸碱概念就操作完整套中和。",
        },
        {
            "type": "homework",
            "index": 11,
            "title": "课后任务",
            "subtitle": "会说出理由，比只选对答案更重要",
            "bullets": [
                "基础：测或查阅家中 3 种无色液体（如食醋、矿泉水、肥皂水），填表：样品 / 估测 pH / 酸性中性还是碱性 / 判断依据。",
                "规范：用自己的话写出 pH 试纸四步，并说明为什么不能把试纸伸进瓶口、为什么不能先用水润湿。",
                "挑战：为什么不能只用酚酞比较“谁更酸”？请写三句话，举一个生活例子。",
            ],
            "content": "不要自拟题目。把家里的液体做成一张小体检单带回来，下节课用 3 分钟交流。没有试纸的同学可以看食品包装或查阅常见物质的大约 pH，但必须写清来源。",
            "notes": "收作业时只抽查“依据”一栏。出现“酚酞没变就是酸”的，下节课开头用 1 分钟再钉一遍。",
        },
    ]


def build_content() -> dict:
    s = slides()
    return {
        "meta": {
            "title": NEW_TITLE,
            "subject": "化学",
            "duration": "45分钟",
            "render_style": "html",
            "key_points": [
                "紫色石蕊、无色酚酞的变色规律",
                "用 pH 判断酸碱性与强弱",
                "pH 试纸的规范操作",
            ],
            "objectives": [
                "能说出石蕊、酚酞在酸、碱、中性中的颜色，并指出酚酞在酸性和中性都无色",
                "会用 pH 判断酸性、中性、碱性，并比较强弱",
                "会描述 pH 试纸：蘸取、点纸、比色、读数",
                "能对生活样品给出类别和依据",
            ],
            "difficulties": [
                "酚酞不变红 ≠ 一定是酸",
                "指示剂看类别，pH 看强弱",
                "试纸不伸进瓶口、不预先润湿",
            ],
            "knowledge_points": [
                {
                    "name": "溶液的酸碱性：指示剂与 pH",
                    "plain_explanation": "指示剂把酸碱性变成颜色：石蕊酸红碱蓝中性紫，酚酞只在碱性变红。pH 用来表示强弱。",
                    "core_concepts": [
                        "紫色石蕊遇酸变红、遇中性仍紫、遇碱变蓝",
                        "无色酚酞遇碱变红，遇酸和中性都无色",
                        "pH<7 酸性，=7 中性，>7 碱性；越小酸性越强",
                    ],
                    "life_example": "白醋、矿泉水、肥皂水看起来都近乎无色，要用指示剂和 pH 试纸才能做体检。",
                    "common_mistakes": [
                        "看见酚酞无色就判断一定是酸",
                        "把万能指示剂的彩虹色当成石蕊或酚酞的颜色",
                        "把 pH 试纸伸进瓶口或先用水润湿",
                    ],
                    "teacher_focus": "先观察后解释；本课不写中和方程式，不把中和实验台当主活动。",
                    "activity_goal": "用真实样品完成酸碱体检，并能说出判断依据。",
                    "deep_dive": "指示剂报告类别，pH 试纸报告大致强弱。酚酞变色区间在弱碱一侧，初中定性记：遇碱变红即可，但必须补上“酸和中性都无色”。",
                }
            ],
        },
        "slides": s,
    }


def main() -> None:
    content = build_content()
    conn = pymysql.connect(
        host="127.0.0.1",
        user="edu_user",
        password="edu_pass",
        database="edu_platform",
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT resource_type, resource_id FROM share_links WHERE token=%s",
                (TOKEN,),
            )
            row = cur.fetchone()
            if not row:
                raise SystemExit("找不到分享链接")
            rtype, rid = row
            if rtype != "courseware":
                raise SystemExit(f"分享类型是 {rtype}，不是课件")
            cur.execute(
                "SELECT id, teacher_id, title, content, render_style, theme, "
                "want_virtual_lab, animation_keys FROM coursewares WHERE id=%s",
                (rid,),
            )
            cw = cur.fetchone()
            if not cw:
                raise SystemExit("找不到课件")
            cw_id, teacher_id, old_title, old_content, render_style, theme, *_ = cw
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "INSERT INTO courseware_versions "
                "(courseware_id, teacher_id, title, content, render_style, theme, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    cw_id,
                    teacher_id,
                    old_title,
                    old_content if isinstance(old_content, str) else json.dumps(old_content, ensure_ascii=False),
                    render_style or "html",
                    theme or "lab",
                    now,
                    now,
                ),
            )
            payload = json.dumps(content, ensure_ascii=False)
            cur.execute(
                "UPDATE coursewares SET title=%s, content=%s, "
                "want_virtual_lab=0, animation_keys=%s, updated_at=%s WHERE id=%s",
                (NEW_TITLE, payload, json.dumps([]), now, cw_id),
            )
        conn.commit()
        print(f"updated courseware {cw_id}: {old_title} -> {NEW_TITLE}, slides={len(content['slides'])}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
