FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt /app/
COPY dflowp /app/dflowp
COPY packages /app/packages
COPY examples /app/examples
COPY tests /app/tests
COPY main.py /app/main.py

RUN pip install --upgrade pip setuptools wheel build \
    && pip install -r requirements.txt \
    && /app/scripts/build_and_install_libraries.sh \
    && pip install -e ".[dev]"

CMD ["python", "main.py"]

