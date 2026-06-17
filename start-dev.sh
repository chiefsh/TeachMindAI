#!/bin/bash
# 本地开发快速启动脚本

echo "=== AI 教育平台 - 开发环境启动 ==="

# 1. 启动基础设施（MySQL / Redis / RabbitMQ / MinIO）
echo "[1/3] 启动基础设施..."
docker compose up -d mysql redis rabbitmq minio
echo "等待数据库就绪..."
sleep 10

# 2. 启动后端
echo "[2/3] 启动后端..."
cd backend
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt -q -i https://mirrors.cloud.tencent.com/pypi/simple/
# 执行 Alembic 迁移
python -m alembic upgrade head 2>/dev/null || true
# 后台启动 Celery
# celery -A app.tasks.celery_app worker --loglevel=info -Q ai_tasks,file_tasks &
# 启动 FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
cd ..

# 3. 启动前端
echo "[3/3] 启动前端..."
cd frontend
npm install -q
npm run dev &
cd ..

echo ""
echo "=== 启动完成 ==="
echo "  前端:     http://localhost:3000"
echo "  后端API:  http://localhost:8000/docs"
echo "  MinIO:    http://localhost:9001"
echo "  RabbitMQ: http://localhost:15672"
echo ""
echo "按 Ctrl+C 停止..."
wait
