# ProSync — guia de deploy

Guia curto para colocar o ProSync em produção. Para o panorama do produto e da
API, veja [`DOCUMENTACAO.md`](DOCUMENTACAO.md).

## 1. Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # gere a SECRET_KEY
```

| Variável | Obrigatória em prod | Default | Descrição |
|---|---|---|---|
| `PRODUCTION` | sim (`true`) | `false` | Liga checagens de segurança no startup |
| `SECRET_KEY` | **sim** | chave de dev | Assina os JWTs. Chave padrão gera warning |
| `DATABASE_URL` | sim | `sqlite:///./prosync.db` | `postgresql://user:pass@host:5432/db` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | não | `5` / `10` | Pool (só quando não é SQLite) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | não | `1440` | Validade do token |
| `CORS_ORIGINS` | sim | `*` | Domínios do frontend, separados por vírgula |
| `GEMINI_API_KEY` | não | vazio | Sem chave → motor heurístico + cache |
| `AI_ENABLED` | não | `true` | `false` desliga qualquer chamada externa de IA |

URLs `postgres://` (formato Heroku/Railway/Render) são normalizadas
automaticamente para `postgresql://`.

## 2. Local com Docker + Postgres

```powershell
docker compose up --build
```

- App: <http://localhost:8000> (frontend estático em `/`, API em `/docs`)
- Healthcheck: <http://localhost:8000/api/health/detalhado>
- Dados do Postgres persistem no volume `pgdata`
- As tabelas são criadas/migradas no startup (`init_db()`)

Para resetar o banco: `docker compose down -v`.

## 3. Local sem Docker

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m uvicorn app.main:app --reload
```

Sem `DATABASE_URL`, usa SQLite (`prosync.db`) — nada a instalar além do Python 3.10+.

## 4. Testes

```powershell
python -m pytest -q
```

O `tests/conftest.py` força um SQLite temporário, então a suíte nunca toca no
banco de desenvolvimento nem precisa de Postgres.

## 5. Migrações de schema

O projeto não usa Alembic. `create_all` cria tabelas novas e
`app/core/migracoes.py` aplica `ALTER TABLE ... ADD COLUMN` idempotente para as
colunas da v2 — funciona igual em SQLite e Postgres.

**Ressalva:** é suficiente para evolução incremental simples (adicionar coluna,
criar índice). Para mudanças destrutivas (renomear/remover coluna, alterar tipo
com dados existentes), migre para Alembic antes.

## 6. Check-list antes de publicar

- [ ] `SECRET_KEY` aleatória e fora do versionamento
- [ ] `PRODUCTION=true`
- [ ] `DATABASE_URL` apontando para Postgres gerenciado (não SQLite)
- [ ] `CORS_ORIGINS` com os domínios reais (nunca `*`)
- [ ] `GEMINI_API_KEY` configurada (ou `AI_ENABLED=false` consciente)
- [ ] HTTPS terminando em proxy reverso/plataforma (`--proxy-headers` já ativo)
- [ ] Backup automático do banco configurado
- [ ] `GET /api/health/detalhado` retornando `"status": "ok"` e `database.ok = true`

## 7. Deploy em PaaS (Railway / Render / Fly.io)

1. Crie o serviço Postgres e copie a connection string para `DATABASE_URL`.
2. Aponte o build para o `Dockerfile` do repositório.
3. Defina as env vars da seção 1 no painel.
4. Health check path: `/api/health`.
5. Release/start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
   (o `CMD` do Dockerfile já é equivalente).
