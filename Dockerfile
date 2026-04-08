FROM python:3.11-slim-bookworm AS wheel-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY dflowp-packages /build/dflowp-packages

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip setuptools wheel build \
    && python -m build /build/dflowp-packages/dflowp-core \
    && python -m build /build/dflowp-packages/dflowp-processruntime


FROM python:3.11-slim-bookworm AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY dflowp /app/dflowp
COPY examples /app/examples
COPY tests /app/tests

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir \
      /tmp/wheels/dflowp-core/dflowp_core-*.whl \
      "fastapi>=0.109.0" \
      "uvicorn[standard]>=0.27.0" \
      "httpx>=0.26.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["uvicorn", "dflowp.api.app:app", "--host", "0.0.0.0", "--port", "8000"]


FROM python:3.11-slim-bookworm AS eventsystem

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY dflowp /app/dflowp
COPY tests /app/tests

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir \
      /tmp/wheels/dflowp-core/dflowp_core-*.whl \
      "fastapi>=0.109.0" \
      "uvicorn[standard]>=0.27.0" \
      "httpx>=0.26.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["uvicorn", "dflowp.eventsystem.app:app", "--host", "0.0.0.0", "--port", "8001"]


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY --from=wheel-builder /build/dflowp-packages/dflowp-processruntime/dist /tmp/wheels/dflowp-processruntime
COPY dflowp /app/dflowp
COPY examples /app/examples
COPY tests /app/tests
COPY main.py /app/main.py

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /tmp/wheels/dflowp-core/dflowp_core-*.whl \
    && python -m pip install --no-cache-dir --no-deps /tmp/wheels/dflowp-processruntime/dflowp_processruntime-*.whl \
    && python -m pip install --no-cache-dir \
      "fastapi>=0.109.0" \
      "uvicorn[standard]>=0.27.0" \
      "typing-extensions>=4.8.0" \
      "httpx>=0.26.0" \
      "feedparser>=6.0.11" \
      "openai>=1.12.0" \
      "numpy>=1.26.0" \
      "scikit-learn>=1.4.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["python", "-m", "dflowp_processruntime.engine.engine_worker"]


FROM python:3.11-slim-bookworm AS event-broker

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY dflowp /app/dflowp
COPY tests /app/tests

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir \
      /tmp/wheels/dflowp-core/dflowp_core-*.whl \
      "httpx>=0.26.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["python", "-m", "dflowp.event_broker.app"]


FROM python:3.11-slim-bookworm AS plugin-fetchfeeditems

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY --from=wheel-builder /build/dflowp-packages/dflowp-processruntime/dist /tmp/wheels/dflowp-processruntime
COPY dflowp /app/dflowp
COPY tests /app/tests

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /tmp/wheels/dflowp-core/dflowp_core-*.whl \
    && python -m pip install --no-cache-dir --no-deps /tmp/wheels/dflowp-processruntime/dflowp_processruntime-*.whl \
    && python -m pip install --no-cache-dir \
      "fastapi>=0.109.0" \
      "uvicorn[standard]>=0.27.0" \
      "httpx>=0.26.0" \
      "feedparser>=6.0.11" \
      "openai>=1.12.0" \
      "typing-extensions>=4.8.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["python", "-m", "dflowp.plugin_fetchfeeditems.app"]


FROM python:3.11-slim-bookworm AS plugin-embeddata

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY --from=wheel-builder /build/dflowp-packages/dflowp-processruntime/dist /tmp/wheels/dflowp-processruntime
COPY dflowp /app/dflowp
COPY tests /app/tests

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /tmp/wheels/dflowp-core/dflowp_core-*.whl \
    && python -m pip install --no-cache-dir --no-deps /tmp/wheels/dflowp-processruntime/dflowp_processruntime-*.whl \
    && python -m pip install --no-cache-dir \
      "fastapi>=0.109.0" \
      "uvicorn[standard]>=0.27.0" \
      "httpx>=0.26.0" \
      "feedparser>=6.0.11" \
      "openai>=1.12.0" \
      "typing-extensions>=4.8.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["python", "-m", "dflowp.plugin_embeddata.app"]


FROM python:3.11-slim-bookworm AS plugin-clustering-dbscan

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=wheel-builder /build/dflowp-packages/dflowp-core/dist /tmp/wheels/dflowp-core
COPY --from=wheel-builder /build/dflowp-packages/dflowp-processruntime/dist /tmp/wheels/dflowp-processruntime
COPY dflowp /app/dflowp
COPY tests /app/tests

RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /tmp/wheels/dflowp-core/dflowp_core-*.whl \
    && python -m pip install --no-cache-dir --no-deps /tmp/wheels/dflowp-processruntime/dflowp_processruntime-*.whl \
    && python -m pip install --no-cache-dir \
      "fastapi>=0.109.0" \
      "uvicorn[standard]>=0.27.0" \
      "httpx>=0.26.0" \
      "numpy>=1.26.0" \
      "scikit-learn>=1.4.0" \
      "typing-extensions>=4.8.0" \
      "pytest>=7.4.0" \
      "pytest-asyncio>=0.23.0" \
      "pytest-cov>=4.1.0"

CMD ["python", "-m", "dflowp.plugin_clustering_dbscan.app"]

