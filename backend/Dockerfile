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
    && rm -rf /var/lib/apt/lists/*

# liteparse 的 OCR 走 tesseract，指定中文语言包所在目录（python:3.11-slim 为 tesseract 5）
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.cloud.tencent.com/pypi/simple/

COPY . .

EXPOSE 8000
