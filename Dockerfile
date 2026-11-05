FROM python:3.12-slim

WORKDIR /app

# 用官方 uv 镜像带二进制进来,避免在镜像里再装 pip 依赖
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PYTHONPATH=/app \
    PYTHONUTF8=1

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

