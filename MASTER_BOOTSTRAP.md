# MASTER BOOTSTRAP — ProSync

> **"Conectar profissionais remotos através de serendipidade, desafios e mentoria."**
> Versão: 0.1 — 08/10/2026
> Status: 🚀 INICIANDO

---

## 1. PROPÓSITO

**O que é?**
Plataforma que conecta profissionais remotos brasileiros usando IA para criar conexões significativas — não é mais um "LinkedIn de currículo", é uma engine de **serendipidade profissional** onde as pessoas certas se encontram no momento certo.

**Problema que resolve:**
Profissionais remotos trabalham isolados — não têm network natural, não encontram colaboradores com habilidades complementares, e perdem oportunidades por falta de conexão.

**Como resolve:**
- IA analisa perfis e habilidades pra sugerir **matches inteligentes**
- Desafios colaborativos aproximam pessoas com interesses comuns
- Mentoria conecta iniciantes a profissionais experientes
- Eventos remotos (cafés virtuais, workshops) geram conexões orgânicas

---

## 2. PRINCÍPIOS (imutáveis)

1. **Sem "curtir currículo"** — O foco é conexão genuína, não validação superficial
2. **Qualidade > quantidade** — Melhor 10 conexões boas que 1000 contatos vazios
3. **IA como facilitadora** — A IA sugere, o humano decide
4. **Brasileiro primeiro** — Foco total no mercado BR, português, cultura local
5. **Gratuito pra profissionais** — Monetização opcional (destaques, créditos)

---

## 3. MVP — ESCOPO INICIAL

### Fase 1 — Perfil + Descoberta
| # | Entrega | Descrição |
|---|---------|-----------|
| 1.1 | Cadastro e Perfil | Profissional cria perfil com habilidades, experiência, objetivos |
| 1.2 | Descoberta IA | Algoritmo sugere pessoas com habilidades complementares |
| 1.3 | Match Inteligente | Sistema de "match" similar ao Tinder profissional — duas pessoas demonstram interesse → conexão |
| 1.4 | Feed de Profissionais | Busca/filtro por skill, região, senioridade |

### Fase 2 — Conexão e Interação
| # | Entrega | Descrição |
|---|---------|-----------|
| 2.1 | Chat entre profissionais | Mensagens diretas após match |
| 2.2 | Desafios Colaborativos | Problemas lançados pra duplas/grupos resolverem juntos |
| 2.3 | Agenda de "Café Virtual" | Sugestão de encontro de 30min baseado em disponibilidade |

### Fase 3 — Mentoria e Comunidade
| # | Entrega | Descrição |
|---|---------|-----------|
| 3.1 | Programa de Mentoria | Conectar júniores com seniores por objetivos |
| 3.2 | Mural de Oportunidades | Vagas, projetos, parcerias entre os membros |
| 3.3 | Reputação | Score de contribuição com base em participação |

---

## 4. STACK TÉCNICA

| Componente | Tecnologia |
|------------|-----------|
| **API** | FastAPI (Python) — mesmo padrão do Synapse Hub |
| **DB** | SQLite (dev) → PostgreSQL (prod) |
| **Frontend** | HTML + CSS + JS vanilla (sem framework, responsivo) |
| **IA** | Gemini API (gratuita) pra análise de perfis e sugestão de matches |
| **Auth** | JWT simples |
| **Deploy** | Servidor 143.95.172.107 (porta a definir) |

---

## 5. MODELO DE DADOS (v0.1)

### Profissional
```
id, nome, email, senha_hash, foto_url, bio, cidade, estado
skills: ["Python", "Design", "Marketing"]
objetivos: ["aprender", "mentorar", "colaborar", "trabalhar"]
senioridade: "junior" | "pleno" | "senior"
disponibilidade: ["weekday_evening", "weekend"]
areas_interesse: ["tech", "design", "negocios", "marketing"]
criado_em, ultimo_acesso
```

### Match
```
id, profissional_a_id, profissional_b_id, status: "pendente" | "match" | "recusado"
score_ia (0-100), skills_match: [...], criado_em, atualizado_em
```

### Desafio
```
id, criador_id, titulo, descricao, skills_necessarias: [...]
tipo: "dupla" | "grupo", status: "aberto" | "em_andamento" | "concluido"
prazo, criado_em
```

### Mensagem
```
id, remetente_id, destinatario_id, conteudo, lida: bool, criado_em
```

---

## 6. ENTREGAS INICIAIS

1. ✅ **MASTER BOOTSTRAP** — Este documento
2. 🔸 **Estrutura do projeto** — Diretórios, pyproject.toml, config
3. 🔸 **API de cadastro** — POST /api/profissionais (registro)
4. 🔸 **API de perfil** — GET/PATCH /api/profissionais/{id}
5. 🔸 **API de busca** — GET /api/profissionais?skill=...&cidade=...
6. 🔸 **API de matches** — POST /api/matches (sugerir/aceitar/recusar)
7. 🔸 **Frontend** — Página inicial + feed de profissionais
8. 🔸 **Frontend** — Perfil do profissional + sistema de match

---

## 7. PÚBLICO-ALVO

- Profissionais remotos brasileiros (tech, design, marketing, negócios)
- Freelancers que buscam parcerias
- Profissionais em transição de carreira buscando mentoria
- Júniores querendo aprender com seniores

---

*Documento gerado em 08/10/2026. Princípios congelados — qualquer mudança precisa de aprovação do Willians.*