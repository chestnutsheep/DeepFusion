FROM python:3.14-slim

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY DeepFusion/deep_fusion/ deep_fusion/
RUN uv pip install --no-deps --no-cache .

ENV DEEP_FUSION_CACHE_DIR=/data/cache
VOLUME /data/cache

ENTRYPOINT ["uv", "run", "deep-fusion"]
