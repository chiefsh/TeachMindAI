"""知识图谱异步任务：知识点抽取、课件知识点回填、跨学科关联发现。"""
from app.tasks.celery_app import celery_app
from app.services.knowledge_extract_service import (
    extract_and_store_for_chapter,
    extract_and_store_for_textbook,
    persist_courseware_points,
    persist_analysis_points,
    suggest_cross_subject_relations,
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


@celery_app.task(name="app.tasks.knowledge_tasks.persist_courseware_kps_task", bind=True, max_retries=1)
def persist_courseware_kps_task(self, courseware_id: int):
    try:
        return _run(persist_courseware_points(courseware_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


@celery_app.task(name="app.tasks.knowledge_tasks.persist_analysis_kps_task", bind=True, max_retries=1)
def persist_analysis_kps_task(self, set_id: int):
    try:
        return _run(persist_analysis_points(set_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


@celery_app.task(name="app.tasks.knowledge_tasks.extract_chapter_task", bind=True, max_retries=1)
def extract_chapter_task(self, chapter_id: int, teacher_id: int):
    try:
        return _run(extract_and_store_for_chapter(chapter_id, teacher_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


@celery_app.task(name="app.tasks.knowledge_tasks.extract_textbook_task", bind=True, max_retries=1)
def extract_textbook_task(self, textbook_id: int, teacher_id: int):
    try:
        return _run(extract_and_store_for_textbook(textbook_id, teacher_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.knowledge_tasks.suggest_cross_subject_task", bind=True)
def suggest_cross_subject_task(self, teacher_id: int):
    return _run(suggest_cross_subject_relations(teacher_id))
