"""AI 生成异步任务"""
from app.tasks.celery_app import celery_app
from app.services.ai_service import (
    do_generate_courseware,
    do_generate_homework,
    do_ocr_grades,
    do_analyze_grades,
    do_analyze_questions,
    do_optimize_courseware_slide,
)
import asyncio


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.ai_tasks.generate_courseware_task", bind=True, max_retries=2)
def generate_courseware_task(self, courseware_id: int):
    try:
        _run(do_generate_courseware(courseware_id, self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.ai_tasks.optimize_courseware_slide_task", bind=True)
def optimize_courseware_slide_task(
    self, courseware_id: int, index: int, instruction: str, mode: str,
):
    # 不做自动重试：失败写 slide.edit_status，重试会覆盖教师中途改动
    return _run(do_optimize_courseware_slide(courseware_id, index, instruction, mode))


@celery_app.task(name="app.tasks.ai_tasks.generate_homework_task", bind=True, max_retries=2)
def generate_homework_task(self, paper_id: int, courseware_ids=None, use_question_bank=False):
    try:
        _run(do_generate_homework(paper_id, courseware_ids, use_question_bank))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.ai_tasks.ocr_grades_task", bind=True)
def ocr_grades_task(self, teacher_id: int, filename: str, file_data: bytes):
    return _run(do_ocr_grades(teacher_id, filename, file_data))


@celery_app.task(name="app.tasks.ai_tasks.analyze_grades_task", bind=True, max_retries=2)
def analyze_grades_task(self, report_id: int):
    try:
        _run(do_analyze_grades(report_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


@celery_app.task(name="app.tasks.ai_tasks.analyze_questions_task", bind=True)
def analyze_questions_task(self, set_id: int, question_ids: list[int], force=False):
    # 不做自动重试：解析为逐题幂等写库，重试会重复推送进度
    return _run(do_analyze_questions(set_id, question_ids, self.request.id, force=force))
