# ProSync - imagem de produção
# Build:  docker build -t prosync .
# Run:    docker run -p 8000:8000 -e DATABASE_URL=... prosync
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PRODUCTION=true

WORKDIR /app

# Dependências primeiro (melhor cache de camadas)
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install \
        "fastapi>=0.104.0" \
        "uvicorn[standard]>=0.24.0" \
        "sqlalchemy>=2.0.0" \
        "python-jose[cryptography]>=3.3.0" \
        "pydantic>=2.0.0" \
        "httpx>=0.25.0" \
        "passlib[bcrypt]>=1.7.2" \
        "bcrypt>=4.0,<4.1" \
        "python-multipart>=0.0.6" \
        "psycopg[binary]>=3.1.0"

COPY app ./app
COPY static ./static

# Usuário não-root
RUN useradd --create-home --uid 1000 prosync \
    && chown -R prosync:prosync /app
USER prosync

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
