# ProSync — Deploy na VPS (passo a passo)

Guia para colocar o ProSync no ar em uma VPS Linux com **HTTPS automatico**.
Escrito para quem vai executar pela primeira vez. Todos os comandos sao
copiados e colados **no terminal da VPS**, na ordem em que aparecem.

- Dominio: `prosync.mindnexo.com.br`
- Repositorio: `https://github.com/williansdelimasantos-alt/prosync-completo.git`
- Portas abertas na VPS: `22` (SSH), `80` e `443` (web)

---

## Antes de comecar — checklist

Tenha em maos:

1. **IP da VPS** (ex.: `203.0.113.45`).
2. **Acesso SSH** — usuario e forma de login (chave ou senha).
3. **Acesso ao painel do DNS** do dominio `mindnexo.com.br`.
4. **Uma SECRET_KEY gerada** (o comando esta no passo 4).

> Ja existe um erro muito comum: fazer o DNS antes do servidor. Se o
> certificado falhar, quase sempre e DNS ainda propagando ou porta 80 fechada.

---

## Passo 1 — Apontar o DNS

No painel do seu provedor de DNS, crie um registro:

| Tipo | Nome | Valor | TTL |
|------|------|-------|-----|
| A | `prosync` | `IP_DA_VPS` | 300 |

Isso faz `prosync.mindnexo.com.br` apontar para a VPS.

Confirme a propagacao **do seu computador local** (Windows PowerShell):

```powershell
nslookup prosync.mindnexo.com.br
```

Quando o resultado mostrar o IP da VPS, siga. Pode levar de 1 a 30 minutos.

---

## Passo 2 — Entrar na VPS e atualizar o sistema

```bash
ssh seu-usuario@IP_DA_VPS
```

Dentro da VPS:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ufw
```

---

## Passo 3 — Instalar o Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

**Feche e abra a conexao SSH novamente** (`exit` e `ssh` de novo). Isso aplica
a permissao de Docker. Depois confirme:

```bash
docker --version
docker compose version
```

Os dois devem responder sem erro. Se aparecer "permission denied", o
`usermod` ainda nao foi aplicado — saia e entre de novo.

---

## Passo 4 — Liberar o firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

Deve mostrar `22`, `80` e `443` como `ALLOW`.

> Atencao: libere o `22` **antes** de ativar o firewall, ou voce perde o acesso.

---

## Passo 5 — Baixar o projeto

```bash
cd ~
git clone https://github.com/williansdelimasantos-alt/prosync-completo.git
cd prosync-completo
```

---

## Passo 6 — Criar o arquivo de configuracao (.env)

```bash
cp .env.example .env
```

Gere uma chave secreta e uma senha de banco:

```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
```

Abra o editor e preencha:

```bash
nano .env
```

Altere **estas quatro linhas** (as demais podem ficar como estao):

```ini
PRODUCTION=true
SECRET_KEY=coloque-a-chave-gerada-acima
POSTGRES_PASSWORD=coloque-a-senha-gerada-acima
CORS_ORIGINS=https://prosync.mindnexo.com.br
```

Salve com `Ctrl+O`, `Enter`, e saia com `Ctrl+X`.

> Com `PRODUCTION=true` a aplicacao **se recusa a subir** se a SECRET_KEY
> estiver no valor de exemplo ou se `CORS_ORIGINS=*`. Se o container reiniciar
> em loop, veja o passo 7.

---

## Passo 7 — Subir a aplicacao

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

A primeira execucao baixa imagens e compila — pode levar alguns minutos.

Acompanhe os logs:

```bash
docker compose -f docker-compose.prod.yml logs -f app
```

Procure a linha `ProSync ... iniciado`. Se houver `Configuracao invalida`,
a mensagem diz qual variavel corrigir. Saia dos logs com `Ctrl+C`.

Confira o estado dos tres servicos (`db`, `app`, `caddy`):

```bash
docker compose -f docker-compose.prod.yml ps
```

---

## Passo 8 — Testar

Pelo navegador: <https://prosync.mindnexo.com.br>

O cadeado deve aparecer. Na primeira visita o Caddy obtem o certificado; se
der erro de certificado, aguarde 1 minuto e recarregue.

Teste a API:

```bash
curl -i https://prosync.mindnexo.com.br/api/health
```

Resposta esperada: `HTTP/2 200` com um JSON de status.

---

## Se algo der errado

Veja os logs do servico que falhou:

```bash
docker compose -f docker-compose.prod.yml logs --tail 50 app
docker compose -f docker-compose.prod.yml logs --tail 50 caddy
```

| Sintoma | Causa provavel | Solucao |
|---|---|---|
| `Configuracao insegura em producao` | SECRET_KEY curta/padrao ou `CORS_ORIGINS=*` | Corrija o `.env` e rode `up -d` de novo |
| `POSTGRES_PASSWORD obrigatoria` | Variavel ausente no `.env` | Preencha e suba de novo |
| Certificado nao emitido | DNS ainda propagando, porta 80 fechada | `nslookup` do seu PC; `sudo ufw status` |
| Container em loop de reinicio | Erro no startup | `logs app` mostra o motivo |
| `permission denied` no docker | Grupo nao aplicado | Saia e entre no SSH de novo |

Reiniciar tudo do zero, mantendo os dados:

```bash
docker compose -f docker-compose.prod.yml restart
```

---

## Atualizar o sistema depois de mudancas no codigo

```bash
cd ~/prosync-completo
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

O banco (volume `pgdata`) e os certificados (volume `caddy_data`) **nao** sao
afetados por esse comando.

---

## Comandos uteis

```bash
# Ver logs em tempo real
docker compose -f docker-compose.prod.yml logs -f app

# Parar tudo (sem apagar dados)
docker compose -f docker-compose.prod.yml down

# Ver uso de disco
docker system df
```

> **Nunca** rode `docker compose down -v` na VPS: o `-v` apaga o volume do
> banco e voce perde todos os dados.

---

## Limitacoes conhecidas desta configuracao

- **Sem backup automatico do banco.** Recomendado configurar depois um
  `pg_dump` diario via cron.
- **Sem monitoramento externo** de disponibilidade.
- O banco nao e acessivel de fora da VPS (proposital).
