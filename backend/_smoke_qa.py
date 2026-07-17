import app.api.v1.question_analysis as r
import app.tasks.ai_tasks, app.tasks.file_tasks  # noqa
from app.services.export_service import build_analysis_export, _analysis_lines  # noqa
from app.services.ai_service import (  # noqa
    do_analyze_questions, analyze_one_question, parse_questions_from_image,
)
from app.services.file_service import (  # noqa
    parse_analysis_file, _coerce_qtype, _coerce_difficulty, _fallback_split_dicts,
)

print("router prefix:", r.router.prefix)
print("routes:", sorted({str(rt.path) for rt in r.router.routes}))

qs = [
    {"content": "1+1=?", "options": None, "answer": "2", "selected": True,
     "analysis_content": {"思路": "加法", "steps": [{"title": "相加", "detail": "1加1", "formula": "$1+1=2$"}],
                          "知识点": ["加法"], "易错点": "无", "答案": "2"}},
    {"content": "2*3=?", "options": {"A": "5", "B": "6"}, "answer": "B", "selected": False,
     "analysis_content": None},
]
for fmt in ("docx", "pdf"):
    data, mt, ext = build_analysis_export(fmt, "测试试题", qs)
    print(fmt, len(data), "bytes", mt)
print("smoke ok")
