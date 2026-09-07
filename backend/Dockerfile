FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8

# liteparse 的 OCR 走 tesseract，指定中文语言包所在目录（python:3.11-slim 为 tesseract 5）
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

COPY requirements.txt .
# 腾讯云镜像没有 litellm==1.49.1 等个别版本，缺包时回落到官方 PyPI
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.cloud.tencent.com/pypi/simple/ \
    --extra-index-url https://pypi.org/simple \
    --trusted-host mirrors.cloud.tencent.com \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org

COPY . .

EXPOSE 8000
