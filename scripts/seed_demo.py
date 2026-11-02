"""Seed de demonstracao da ProSync.

Cria uma comunidade fictícia (profissionais, matches, mensagens, desafios,
mentorias e oportunidades) para que o app pareça vivo em demos e testes manuais.

Uso:
    python scripts/seed_demo.py            # adiciona (idempotente por email)
    python scripts/seed_demo.py --reset    # apaga apenas os dados de demo e recria

Todos os perfis de demo usam o dominio @demo.prosync e senha "demo1234".
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.database import (  # noqa: E402
    ProfissionalDB,
    MatchDB,
    MensagemDB,
    DesafioDB,
    ParticipanteDesafioDB,
    MentoriaDB,
    OportunidadeDB,
    NotificacaoDB,
)

DOMINIO_DEMO = "@demo.prosync"
SENHA_DEMO = "demo1234"

PERFIS = [
    {
        "nome": "Ana Paula Ribeiro",
        "email": "ana" + DOMINIO_DEMO,
        "headline": "Engenheira de Dados | Python & Airflow",
        "bio": "Construo pipelines de dados que escalam. Apaixonada por open source e por ensinar quem está começando.",
        "cidade": "Recife", "estado": "PE", "senioridade": "senior",
        "skills": ["Python", "Airflow", "SQL", "AWS", "dbt"],
        "objetivos": ["mentorar", "colaborar"],
        "areas_interesse": ["Dados", "IA"],
        "github": "https://github.com/anapribeiro",
        "score_contribuicao": 85,
    },
    {
        "nome": "Bruno Carvalho",
        "email": "bruno" + DOMINIO_DEMO,
        "headline": "Frontend Engineer | React, TypeScript e Design Systems",
        "bio": "Transformo protótipos em interfaces rápidas e acessíveis. Curto colaborar com gente de produto.",
        "cidade": "São Paulo", "estado": "SP", "senioridade": "pleno",
        "skills": ["React", "TypeScript", "Design System", "Acessibilidade", "Next.js"],
        "objetivos": ["colaborar", "aprender"],
        "areas_interesse": ["Frontend", "Produto"],
        "linkedin": "https://linkedin.com/in/brunocarvalho",
        "score_contribuicao": 55,
    },
    {
        "nome": "Carla Mendes",
        "email": "carla" + DOMINIO_DEMO,
        "headline": "Product Designer | UX Research",
        "bio": "Desenho produtos que as pessoas realmente usam. Faço pesquisa, prototipo e testo rápido.",
        "cidade": "Florianópolis", "estado": "SC", "senioridade": "pleno",
        "skills": ["Figma", "UX Research", "Design System", "Prototipagem", "Testes de usabilidade"],
        "objetivos": ["colaborar", "mentorar"],
        "areas_interesse": ["Produto", "Design"],
        "portfolio": "https://carlamendes.design",
        "score_contribuicao": 62,
    },
    {
        "nome": "Diego Santos",
        "email": "diego" + DOMINIO_DEMO,
        "headline": "Backend Developer | FastAPI & Go",
        "bio": "Gosto de API bem desenhada, testes de verdade e deploy sem drama. Júnior buscando um mentor.",
        "cidade": "Salvador", "estado": "BA", "senioridade": "junior",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "objetivos": ["aprender", "colaborar"],
        "areas_interesse": ["Backend", "DevOps"],
        "score_contribuicao": 15,
    },
    {
        "nome": "Eduarda Lima",
        "email": "eduarda" + DOMINIO_DEMO,
        "headline": "SRE | Kubernetes, Observabilidade e Cultura de Confiabilidade",
        "bio": "Reduzo incidents e durmo melhor. Organizo plantões e escrevo runbooks que ajudam de verdade.",
        "cidade": "Belo Horizonte", "estado": "MG", "senioridade": "senior",
        "skills": ["Kubernetes", "Terraform", "Go", "Prometheus", "AWS"],
        "objetivos": ["colaborar", "mentorar"],
        "areas_interesse": ["Infra", "DevOps"],
        "score_contribuicao": 120,
    },
    {
        "nome": "Felipe Nogueira",
        "email": "felipe" + DOMINIO_DEMO,
        "headline": "Mobile Developer | Flutter",
        "bio": "Apps que rodam liso em Android antigo. Sonho em montar uma squad de mobile open source.",
        "cidade": "Porto Alegre", "estado": "RS", "senioridade": "pleno",
        "skills": ["Flutter", "Dart", "Firebase", "Mobile UX"],
        "objetivos": ["colaborar"],
        "areas_interesse": ["Mobile"],
        "score_contribuicao": 30,
    },
    {
        "nome": "Gabriela Souza",
        "email": "gabriela" + DOMINIO_DEMO,
        "headline": "Growth & Marketing de Produto",
        "bio": "Levo produto técnico até quem precisa dele. Métricas, conteúdo e experimentos.",
        "cidade": "Rio de Janeiro", "estado": "RJ", "senioridade": "senior",
        "skills": ["Growth", "SEO", "Analytics", "Copywriting", "Product Marketing"],
        "objetivos": ["colaborar", "mentorar"],
        "areas_interesse": ["Marketing", "Produto"],
        "score_contribuicao": 78,
    },
    {
        "nome": "Henrique Alves",
        "email": "henrique" + DOMINIO_DEMO,
        "headline": "Analista de Dados Pleno",
        "bio": "SQL no café da manhã. Quero migrar para engenharia de dados, buscando mentoria.",
        "cidade": "Recife", "estado": "PE", "senioridade": "pleno",
        "skills": ["SQL", "Power BI", "Python", "Estatística"],
        "objetivos": ["aprender", "colaborar"],
        "areas_interesse": ["Dados"],
        "score_contribuicao": 22,
    },
    {
        "nome": "Isabela Rocha",
        "email": "isabela" + DOMINIO_DEMO,
        "headline": "Engineering Manager | Liderança técnica",
        "bio": "18 anos de carreira, 6 liderando times remotos. Adoro ajudar devs a crescerem sem virar gestores no susto.",
        "cidade": "Curitiba", "estado": "PR", "senioridade": "senior",
        "skills": ["Liderança", "Agile", "Mentoria", "Arquitetura", "Python"],
        "objetivos": ["mentorar"],
        "areas_interesse": ["Carreira", "Backend"],
        "score_contribuicao": 160,
    },
    {
        "nome": "João Pedro Martins",
        "email": "joao" + DOMINIO_DEMO,
        "headline": "QA Engineer | Automação de testes",
        "bio": "Testes que encontram bugs antes do cliente. Estudando Cypress e Playwright.",
        "cidade": "São Paulo", "estado": "SP", "senioridade": "junior",
        "skills": ["Cypress", "Playwright", "Python", "API Testing"],
        "objetivos": ["aprender", "colaborar"],
        "areas_interesse": ["Qualidade"],
        "score_contribuicao": 10,
    },
    {
        "nome": "Larissa Fontes",
        "email": "larissa" + DOMINIO_DEMO,
        "headline": "Data Scientist | NLP e LLMs",
        "bio": "Transformo texto não estruturado em produto. Interessada em IA aplicada e responsável.",
        "cidade": "Campinas", "estado": "SP", "senioridade": "pleno",
        "skills": ["Python", "NLP", "LLM", "PyTorch", "MLOps"],
        "objetivos": ["colaborar", "mentorar"],
        "areas_interesse": ["IA", "Dados"],
        "score_contribuicao": 95,
    },
    {
        "nome": "Marcos Vinícius",
        "email": "marcos" + DOMINIO_DEMO,
        "headline": "Dev Full Stack | Freelancer",
        "bio": "Toco projetos de ponta a ponta para pequenos negócios. Sempre aberto a parcerias.",
        "cidade": "Goiânia", "estado": "GO", "senioridade": "pleno",
        "skills": ["Vue.js", "Node.js", "PostgreSQL", "Docker"],
        "objetivos": ["colaborar", "trabalhar"],
        "areas_interesse": ["Full Stack", "Freelance"],
        "score_contribuicao": 40,
    },
]

DESAFIOS = [
    {
        "titulo": "Plataforma de doação de sangue",
        "descricao": "Criar um MVP que conecta doadores a hemocentros com aviso de urgência. Time de 4 pessoas, 6 semanas.",
        "skills": ["React", "FastAPI", "Design", "SQL"],
        "tipo": "grupo",
    },
    {
        "titulo": "Dashboard open source de acessibilidade",
        "descricao": "Ferramenta para auditar acessibilidade de sites com relatório automatizado.",
        "skills": ["Acessibilidade", "TypeScript", "Python"],
        "tipo": "dupla",
    },
    {
        "titulo": "Bot de mentoria para comunidades",
        "descricao": "Algoritmo que pareia mentor e mentorado em comunidades de tecnologia.",
        "skills": ["Python", "NLP", "Design"],
        "tipo": "grupo",
    },
]

OPORTUNIDADES = [
    {
        "titulo": "Vaga: Backend Python (remoto, PJ)",
        "descricao": "Startup de logística procura dev Python pleno com experiência em FastAPI e filas. R$ 12k-15k/mês.",
        "tipo": "vaga",
        "skills": ["Python", "FastAPI", "Docker"],
        "contato": "talentos@logtech.demo",
    },
    {
        "titulo": "Parceria: squad para app de saúde",
        "descricao": "Preciso de designer e dev mobile para projeto de 3 meses, contrato de parceria.",
        "tipo": "parceria",
        "skills": ["Flutter", "Figma", "UX Research"],
        "contato": "contato@squadsaude.demo",
    },
    {
        "titulo": "Freela: auditoria de acessibilidade",
        "descricao": "Auditoria WCAG 2.2 de e-commerce, entrega em 3 semanas.",
        "tipo": "projeto",
        "skills": ["Acessibilidade", "React"],
        "contato": "acessibilidade@empresa.demo",
    },
]


def _limpar_orfaos(db) -> None:
    """Remove registros que apontam para profissionais inexistentes (dados de demo antigos)."""
    vivos = {p.id for p in db.query(ProfissionalDB.id).all()}

    for m in db.query(MatchDB).all():
        if m.profissional_a_id not in vivos or m.profissional_b_id not in vivos:
            db.query(MensagemDB).filter(MensagemDB.match_id == m.id).delete(synchronize_session=False)
            db.delete(m)

    for db_obj, campos in (
        (MentoriaDB, ("mentor_id", "mentorado_id")),
        (ParticipanteDesafioDB, ("profissional_id",)),
        (NotificacaoDB, ("profissional_id",)),
        (DesafioDB, ("criador_id",)),
        (OportunidadeDB, ("criador_id",)),
    ):
        for obj in db.query(db_obj).all():
            if any(getattr(obj, c) not in vivos for c in campos):
                db.delete(obj)

    db.commit()


def _limpar_demo(db) -> None:
    ids = [p.id for p in db.query(ProfissionalDB).filter(ProfissionalDB.email.like(f"%{DOMINIO_DEMO}")).all()]
    if not ids:
        return
    db.query(MensagemDB).filter(MensagemDB.remetente_id.in_(ids)).delete(synchronize_session=False)
    db.query(MatchDB).filter(
        (MatchDB.profissional_a_id.in_(ids)) | (MatchDB.profissional_b_id.in_(ids))
    ).delete(synchronize_session=False)
    db.query(ParticipanteDesafioDB).filter(ParticipanteDesafioDB.profissional_id.in_(ids)).delete(synchronize_session=False)
    db.query(DesafioDB).filter(DesafioDB.criador_id.in_(ids)).delete(synchronize_session=False)
    db.query(MentoriaDB).filter(
        (MentoriaDB.mentor_id.in_(ids)) | (MentoriaDB.mentorado_id.in_(ids))
    ).delete(synchronize_session=False)
    db.query(OportunidadeDB).filter(OportunidadeDB.criador_id.in_(ids)).delete(synchronize_session=False)
    db.query(NotificacaoDB).filter(NotificacaoDB.profissional_id.in_(ids)).delete(synchronize_session=False)
    db.query(ProfissionalDB).filter(ProfissionalDB.id.in_(ids)).delete(synchronize_session=False)
    db.commit()


def seed(reset: bool = False) -> None:
    init_db()
    db = SessionLocal()
    random.seed(42)

    try:
        if reset:
            _limpar_demo(db)
            _limpar_orfaos(db)
            print("Dados de demo removidos.")

        criados: dict[str, ProfissionalDB] = {}
        for dados in PERFIS:
            existente = (
                db.query(ProfissionalDB)
                .filter(ProfissionalDB.email == dados["email"])
                .first()
            )
            if existente:
                criados[dados["nome"]] = existente
                continue

            p = ProfissionalDB(
                nome=dados["nome"],
                email=dados["email"],
                senha_hash=hash_password(SENHA_DEMO),
                foto_url="",
                bio=dados.get("bio", ""),
                headline=dados.get("headline", ""),
                cidade=dados.get("cidade", ""),
                estado=dados.get("estado", ""),
                skills=json.dumps(dados["skills"], ensure_ascii=False),
                objetivos=json.dumps(dados["objetivos"], ensure_ascii=False),
                senioridade=dados["senioridade"],
                disponibilidade=json.dumps(["noite"], ensure_ascii=False),
                areas_interesse=json.dumps(dados.get("areas_interesse", []), ensure_ascii=False),
                github=dados.get("github", ""),
                linkedin=dados.get("linkedin", ""),
                portfolio=dados.get("portfolio", ""),
                score_contribuicao=dados.get("score_contribuicao", 0),
                onboarding_concluido=True,
            )
            db.add(p)
            criados[dados["nome"]] = p

        db.flush()
        nomes = list(criados)

        # Matches: alguns aceitos, alguns pendentes
        pares_aceitos = [
            ("Ana Paula Ribeiro", "Bruno Carvalho"),
            ("Carla Mendes", "Bruno Carvalho"),
            ("Eduarda Lima", "Diego Santos"),
            ("Isabela Rocha", "Diego Santos"),
            ("Larissa Fontes", "Henrique Alves"),
            ("Gabriela Souza", "Marcos Vinícius"),
        ]
        pares_pendentes = [
            ("Felipe Nogueira", "Carla Mendes"),
            ("João Pedro Martins", "Eduarda Lima"),
            ("Henrique Alves", "Ana Paula Ribeiro"),
        ]

        from app.services.ai import analisar_local

        for nome_a, nome_b in pares_aceitos + pares_pendentes:
            a, b = criados[nome_a], criados[nome_b]
            ja = (
                db.query(MatchDB)
                .filter(
                    ((MatchDB.profissional_a_id == a.id) & (MatchDB.profissional_b_id == b.id))
                    | ((MatchDB.profissional_a_id == b.id) & (MatchDB.profissional_b_id == a.id))
                )
                .first()
            )
            if ja:
                continue
            resultado = analisar_local(a, b)
            status = "match" if (nome_a, nome_b) in pares_aceitos else "pendente"
            db.add(
                MatchDB(
                    profissional_a_id=a.id,
                    profissional_b_id=b.id,
                    status=status,
                    score_ia=resultado.score,
                    skills_match=json.dumps(resultado.skills_complementares, ensure_ascii=False),
                    motivo_ia=resultado.motivo,
                    forcas_ia=json.dumps(resultado.forcas or [], ensure_ascii=False),
                    fonte_ia=resultado.fonte,
                    iniciado_por=a.id,
                )
            )

        db.flush()

        # Conversas com historico
        conversas = [
            ("Ana Paula Ribeiro", "Bruno Carvalho", [
                ("Ana Paula Ribeiro", "Oi Bruno! Vi que você curte design system. Quer trocar ideia?", 12),
                ("Bruno Carvalho", "Oi Ana! Claro, seria ótimo. Tô montando um do zero numa fintech.", 11),
                ("Ana Paula Ribeiro", "Perfeito. Posso contribuir com a parte de dados/eventos.", 10),
                ("Bruno Carvalho", "Fechado! Te mando o repositório hoje à noite.", 9),
            ]),
            ("Carla Mendes", "Bruno Carvalho", [
                ("Carla Mendes", "Bruno, quero testar com usuários o novo fluxo de login. Topa ajudar?", 30),
                ("Bruno Carvalho", "Topo sim. Manda o protótipo que reviso hoje.", 28),
            ]),
            ("Isabela Rocha", "Diego Santos", [
                ("Diego Santos", "Isabela, obrigado por aceitar! Tô perdido em como estruturar testes de integração.", 48),
                ("Isabela Rocha", "Vamos começar pelo caminho crítico. Marca um horário essa semana.", 47),
            ]),
        ]
        for nome_a, nome_b, msgs in conversas:
            a, b = criados[nome_a], criados[nome_b]
            m = (
                db.query(MatchDB)
                .filter(
                    ((MatchDB.profissional_a_id == a.id) & (MatchDB.profissional_b_id == b.id))
                    | ((MatchDB.profissional_a_id == b.id) & (MatchDB.profissional_b_id == a.id)),
                    MatchDB.status == "match",
                )
                .first()
            )
            if not m:
                continue
            ja_tem_msg = db.query(MensagemDB).filter(MensagemDB.match_id == m.id).count()
            if ja_tem_msg:
                continue
            for remetente, texto, horas in msgs:
                db.add(
                    MensagemDB(
                        match_id=m.id,
                        remetente_id=criados[remetente].id,
                        conteudo=texto,
                        lida=(remetente == nome_b),
                        criado_em=datetime.now(timezone.utc) - timedelta(hours=horas),
                    )
                )

        # Desafios
        for dados in DESAFIOS:
            if db.query(DesafioDB).filter(DesafioDB.titulo == dados["titulo"]).first():
                continue
            d = DesafioDB(
                criador_id=criados[nomes[0]].id,
                titulo=dados["titulo"],
                descricao=dados["descricao"],
                skills_necessarias=json.dumps(dados["skills"], ensure_ascii=False),
                tipo=dados["tipo"],
                status="aberto",
                prazo=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(d)
            db.flush()
            for nome in random.sample(nomes, k=2):
                db.add(ParticipanteDesafioDB(desafio_id=d.id, profissional_id=criados[nome].id))

        # Mentorias
        mentorias = [
            ("Isabela Rocha", "Diego Santos", "Arquitetura", "Quero consolidar fundamentos de backend e testes.", "ativa"),
            ("Ana Paula Ribeiro", "Henrique Alves", "Dados", "Transição de análise para engenharia de dados.", "ativa"),
            ("Larissa Fontes", "João Pedro Martins", "Carreira", "Como entrar em IA aplicada vindo de QA.", "pendente"),
        ]
        for mentor_nome, mentorado_nome, area, objetivos, status in mentorias:
            mentor, mentorado = criados[mentor_nome], criados[mentorado_nome]
            ja = (
                db.query(MentoriaDB)
                .filter(MentoriaDB.mentor_id == mentor.id, MentoriaDB.mentorado_id == mentorado.id)
                .first()
            )
            if ja:
                continue
            db.add(
                MentoriaDB(
                    mentor_id=mentor.id,
                    mentorado_id=mentorado.id,
                    area=area,
                    objetivos=objetivos,
                    status=status,
                )
            )

        # Oportunidades
        for dados in OPORTUNIDADES:
            if db.query(OportunidadeDB).filter(OportunidadeDB.titulo == dados["titulo"]).first():
                continue
            db.add(
                OportunidadeDB(
                    criador_id=criados["Gabriela Souza"].id,
                    titulo=dados["titulo"],
                    descricao=dados["descricao"],
                    tipo=dados["tipo"],
                    skills_necessarias=json.dumps(dados["skills"], ensure_ascii=False),
                    contato=dados["contato"],
                    status="aberta",
                )
            )

        # Notificacoes de exemplo (para o painel do dashboard nao ficar vazio)
        notificacoes = [
            (
                "Ana Paula Ribeiro",
                "convite",
                "Henrique Alves quer se conectar",
                "Vocês se complementam em airflow, aws e dbt. Responda ao convite.",
                "#dashboard",
                False,
                2,
            ),
            (
                "Ana Paula Ribeiro",
                "mensagem",
                "Nova mensagem de Bruno Carvalho",
                "Fechado! Te mando o repositório hoje à noite.",
                "#conversas",
                False,
                9,
            ),
            (
                "Ana Paula Ribeiro",
                "mentoria",
                "Mentoria ativa com Henrique Alves",
                "Sua mentoria em Dados foi confirmada. Combine o primeiro encontro.",
                "#mentorias",
                True,
                30,
            ),
            (
                "Carla Mendes",
                "mensagem",
                "Nova mensagem de Bruno Carvalho",
                "Topo sim. Manda o protótipo que reviso hoje.",
                "#conversas",
                False,
                28,
            ),
            (
                "Bruno Carvalho",
                "convite",
                "Ana Paula Ribeiro aceitou seu convite",
                "Agora vocês podem conversar e trocar experiências.",
                "#conversas",
                True,
                60,
            ),
        ]
        for nome, tipo, titulo, mensagem, link, lida, horas in notificacoes:
            dono = criados[nome]
            ja = (
                db.query(NotificacaoDB)
                .filter(NotificacaoDB.profissional_id == dono.id, NotificacaoDB.titulo == titulo)
                .first()
            )
            if ja:
                continue
            db.add(
                NotificacaoDB(
                    profissional_id=dono.id,
                    tipo=tipo,
                    titulo=titulo,
                    mensagem=mensagem,
                    link=link,
                    lida=lida,
                    criado_em=datetime.now(timezone.utc) - timedelta(hours=horas),
                )
            )

        db.commit()

        total = db.query(ProfissionalDB).filter(ProfissionalDB.email.like(f"%{DOMINIO_DEMO}")).count()
        print(f"Seed concluido: {total} perfis de demo disponiveis.")
        print(f"Login de exemplo: ana{DOMINIO_DEMO} / senha: {SENHA_DEMO}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed de demonstracao da ProSync")
    parser.add_argument("--reset", action="store_true", help="apaga e recria os dados de demo")
    args = parser.parse_args()
    seed(reset=args.reset)
