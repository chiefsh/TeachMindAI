"""文件解析异步任务"""
from app.tasks.celery_app import celery_app
from app.services.file_service import (
    parse_textbook_file,
    refresh_textbook_images,
    parse_question_file,
    parse_analysis_file,
    import_grades_from_file,
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


@celery_app.task(name="app.tasks.file_tasks.parse_textbook_task", bind=True, max_retries=3)
def parse_textbook_task(self, textbook_id: int):
    try:
        _run(parse_textbook_file(textbook_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(name="app.tasks.file_tasks.refresh_textbook_images_task")
def refresh_textbook_images_task(textbook_id: int):
    return _run(refresh_textbook_images(textbook_id))


@celery_app.task(name="app.tasks.file_tasks.parse_question_file_task", bind=True, max_retries=3)
def parse_question_file_task(
    self,
    teacher_id: int,
    subject_id: int,
    grade_id: int,
    bucket: str,
    object_name: str,
    file_type: str,
    import_id: int | None = None,
):
    try:
        _run(parse_question_file(
            teacher_id, subject_id, grade_id, bucket, object_name, file_type, import_id,
        ))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(name="app.tasks.file_tasks.parse_analysis_file_task", bind=True, max_retries=3)
def parse_analysis_file_task(self, set_id: int):
    try:
        _run(parse_analysis_file(set_id, self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(name="app.tasks.file_tasks.import_grades_task", bind=True)
def import_grades_task(self, teacher_id: int, filename: str, file_data: bytes):
    _run(import_grades_from_file(teacher_id, filename, file_data))
