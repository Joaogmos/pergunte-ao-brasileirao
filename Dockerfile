FROM python:3.13-slim

# git: a dependencia `brasileirao` e instalada direto do GitHub, travada num commit
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY data ./data
RUN pip install --no-cache-dir -e .

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "pergunte.api:app", "--host", "0.0.0.0", "--port", "8000"]