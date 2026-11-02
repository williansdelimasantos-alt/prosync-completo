/* ═══════════════════════════════════════════════════════════════════════
   ProSync v2 — sessão JWT, feed inteligente e dashboard
   Carregado DEPOIS do script.js: reaproveita helpers (toast, apiFetch...)
   e adiciona as telas novas.
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Estado de sessão ────────────────────────────────────────────────── */
const Sessao = {
  CHAVE_TOKEN: 'prosync_token',
  CHAVE_USER: 'prosync_user_id', // compat com o script.js v1

  get token() {
    return localStorage.getItem(this.CHAVE_TOKEN) || '';
  },
  get logado() {
    return !!this.token && !!this.id;
  },
  get id() {
    return this.usuario?.id || localStorage.getItem(this.CHAVE_USER) || null;
  },
  salvar(resposta) {
    localStorage.setItem(this.CHAVE_TOKEN, resposta.access_token);
    localStorage.setItem(this.CHAVE_USER, resposta.profissional_id);
    // login ja devolve o perfil completo: guardamos para nao depender de /auth/me
    this.usuario = resposta.profissional || this.usuario;
    // mantem o script.js v1 coerente
    profissionalLogadoId = resposta.profissional_id;
    atualizarHeader();
  },
  async restaurar() {
    if (!this.token) {
      // sem token nao existe sessao: limpa id orfao gravado pelo cadastro do v1
      if (localStorage.getItem(this.CHAVE_USER) || profissionalLogadoId) {
        this.limpar();
      }
      return false;
    }
    try {
      const perfil = await fetchV2('/api/auth/me');
      this.usuario = perfil;
      // banco recriado/seed trocado: o id antigo do localStorage pode nao existir mais
      localStorage.setItem(this.CHAVE_USER, perfil.id);
      profissionalLogadoId = perfil.id;
      return true;
    } catch (_) {
      // token expirado/invalido: limpa e volta ao modo visitante
      this.limpar();
      return false;
    }
  },
  limpar() {
    localStorage.removeItem(this.CHAVE_TOKEN);
    localStorage.removeItem(this.CHAVE_USER);
    this.usuario = null;
    profissionalLogadoId = null;
    atualizarHeader();
  },
  usuario: null,
};

/* ── fetch com JWT ───────────────────────────────────────────────────── */
async function fetchV2(url, options = {}) {
  const { headers: customHeaders, ...rest } = options;
  const headers = { 'Content-Type': 'application/json', ...customHeaders };
  if (Sessao.token) headers['Authorization'] = `Bearer ${Sessao.token}`;

  const resp = await fetch(url, { ...rest, headers });
  if (!resp.ok) {
    let detalhe = resp.statusText;
    try {
      const corpo = await resp.json();
      detalhe = typeof corpo.detail === 'string' ? corpo.detail : JSON.stringify(corpo.detail);
    } catch (_) {}
    if (resp.status === 401) {
      Sessao.limpar();
    }
    const erro = new Error(detalhe || `Erro ${resp.status}`);
    erro.status = resp.status;
    throw erro;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

/* ── Modal de autenticação ───────────────────────────────────────────── */
function abrirAuth(aba = 'login') {
  trocarAbaAuth(aba);
  document.getElementById('authErro').style.display = 'none';
  document.getElementById('authModal').classList.add('active');
  setTimeout(() => document.getElementById('loginEmail')?.focus(), 100);
}

function trocarAbaAuth(aba) {
  document.querySelectorAll('#authModal .auth-tabs button').forEach(b => {
    b.classList.toggle('active', b.dataset.auth === aba);
  });
  document.getElementById('formLogin').style.display = aba === 'login' ? 'block' : 'none';
  document.getElementById('formCadastro').style.display = aba === 'cadastro' ? 'block' : 'none';
  document.getElementById('authErro').style.display = 'none';
}

function mostrarErroAuth(msg) {
  const el = document.getElementById('authErro');
  el.textContent = msg;
  el.style.display = 'block';
}

async function fazerLogin(e) {
  e.preventDefault();
  const form = e.target;
  const btn = form.querySelector('button[type="submit"]');
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Entrando...';

  try {
    const resposta = await fetchV2('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: form.email.value.trim(),
        senha: form.senha.value,
      }),
    });
    Sessao.salvar(resposta);
    closeModal('authModal');
    toast(`Bem-vindo(a) de volta, ${resposta.profissional?.nome?.split(' ')[0] || ''}!`, 'success');
    irPara('dashboard');
    carregarProfissionais();
  } catch (err) {
    mostrarErroAuth(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

async function fazerCadastro(e) {
  e.preventDefault();
  const form = e.target;
  const btn = form.querySelector('button[type="submit"]');
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Criando conta...';

  const objetivos = [...form.querySelectorAll('input[name="objetivos"]:checked')].map(el => el.value);

  try {
    await fetchV2('/api/profissionais', {
      method: 'POST',
      body: JSON.stringify({
        nome: form.nome.value.trim(),
        email: form.email.value.trim(),
        senha: form.senha.value,
        cidade: form.cidade.value.trim(),
        estado: form.estado.value,
        bio: form.bio.value.trim(),
        headline: form.headline?.value.trim() || '',
        senioridade: form.senioridade.value || 'junior',
        skills: parseSkills(form.skills.value),
        objetivos: objetivos.length ? objetivos : ['colaborar'],
      }),
    });

    // login automatico para o usuario nao cair numa segunda tela
    const resposta = await fetchV2('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: form.email.value.trim(), senha: form.senha.value }),
    });
    Sessao.salvar(resposta);
    closeModal('authModal');
    toast('Conta criada! Vamos completar seu perfil 🎉', 'success');
    irPara('dashboard');
    carregarProfissionais();
  } catch (err) {
    mostrarErroAuth(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

function parseSkills(valor) {
  return (valor || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 20);
}

function sair() {
  Sessao.limpar();
  toast('Você saiu da sua conta.', 'info');
  irPara('descobrir');
}

async function loginDemo() {
  try {
    const resposta = await fetchV2('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: 'ana@demo.prosync', senha: 'demo1234' }),
    });
    Sessao.salvar(resposta);
    toast(`Entrando como ${resposta.profissional.nome} (demo)`, 'success');
    irPara('dashboard');
  } catch (_) {
    toast('Não consegui entrar na conta demo. Rode: python scripts/seed_demo.py', 'error');
  }
}

/* ── Header (v2) ─────────────────────────────────────────────────────── */
function atualizarHeaderV2() {
  const area = document.getElementById('headerUser');
  if (!area) return;

  if (Sessao.logado && Sessao.usuario) {
    const u = Sessao.usuario;
    const iniciais = (u.nome || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    const avatar = u.foto_url
      ? `<img src="${u.foto_url}" alt="${escapeHtml(u.nome)}" />`
      : `<div class="avatar-placeholder" style="width:100%;height:100%">${iniciais}</div>`;
    area.innerHTML = `
      <button class="btn-ghost" onclick="irPara('conversas')">💬 Conversas</button>
      <button class="user-chip" onclick="irPara('dashboard')" title="Meu painel">
        <span class="avatar-sm">${avatar}</span>
        <span class="nome-user">${escapeHtml((u.nome || '').split(' ')[0])}</span>
        <span class="score-mini">🏆 ${u.score_contribuicao || 0}</span>
      </button>
      <button class="btn-ghost" onclick="sair()" title="Sair">Sair</button>
    `;
  } else {
    area.innerHTML = `
      <button class="btn-ghost" onclick="abrirAuth('login')">Entrar</button>
      <button class="btn-primary-solid" onclick="abrirAuth('cadastro')">Criar conta</button>
    `;
  }
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/* ── Navegação ───────────────────────────────────────────────────────── */
function irPara(aba) {
  // delega para a navegação existente quando a aba já existe
  const todasAba = ['profissionais', 'mentoria', 'oportunidades', 'desafios', 'conversas'];
  document.querySelectorAll('.aba-v2').forEach(sec => { sec.style.display = 'none'; });

  if (aba === 'descobrir') {
    document.getElementById('abaDescobrir').style.display = 'block';
    document.getElementById('heroSection').style.display = 'block';
    document.getElementById('abaProfissionais').style.display = 'none';
    document.querySelectorAll('.header-nav [data-aba]').forEach(a => a.classList.remove('active'));
    document.querySelector('[data-aba="descobrir"]')?.classList.add('active');
    carregarFeed();
  } else if (aba === 'dashboard') {
    if (!Sessao.logado) { abrirAuth('login'); return; }
    document.getElementById('abaDashboard').style.display = 'block';
    document.getElementById('heroSection').style.display = 'none';
    ['abaProfissionais', 'abaDesafios', 'abaConversas', 'abaMentoria', 'abaOportunidades']
      .forEach(id => { document.getElementById(id).style.display = 'none'; });
    document.querySelectorAll('.header-nav [data-aba]').forEach(a => a.classList.remove('active'));
    document.querySelector('[data-aba="dashboard"]')?.classList.add('active');
    carregarDashboard();
  } else if (todasAba.includes(aba)) {
    document.querySelectorAll('.aba-v2').forEach(sec => { sec.style.display = 'none'; });
    mudarAba(aba);
  }
}

/* ── Feed inteligente ────────────────────────────────────────────────── */
async function carregarFeed() {
  const grid = document.getElementById('sugestoesGrid');
  const chip = document.getElementById('feedModoIa');
  if (!grid) return;

  if (!Sessao.logado) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="icon">✨</div>
        <h3>Descubra conexões com IA</h3>
        <p>Entre na sua conta para receber sugestões de profissionais compatíveis com você.</p>
        <div style="display:flex;gap:10px;justify-content:center;margin-top:14px;flex-wrap:wrap">
          <button class="btn-primary-solid" onclick="abrirAuth('cadastro')">Criar conta grátis</button>
          <button class="btn-ghost" onclick="abrirAuth('login')">Já tenho conta</button>
        </div>
      </div>`;
    if (chip) chip.style.display = 'none';
    return;
  }

  grid.innerHTML = Array.from({ length: 3 }, () => '<div class="skeleton-card"></div>').join('');

  try {
    const feed = await fetchV2(`/api/feed?profissional_id=${Sessao.id}&limit=9`);
    if (chip) {
      chip.style.display = 'inline-flex';
      chip.className = `ai-chip ${feed.modo === 'gemini' ? 'gemini' : ''}`;
      chip.innerHTML = `<span class="dot"></span>${feed.modo === 'gemini' ? 'IA Gemini ativa' : 'Modo heurístico'}`;
      chip.title = feed.modo === 'gemini'
        ? 'As sugestões são geradas pelo Gemini e refinadas com heurística local.'
        : 'Sem chave GEMINI_API_KEY: as sugestões usam nossa heurística local. Funciona offline!';
    }

    if (!feed.sugestoes.length) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="icon">🌱</div>
          <h3>Você já conheceu todo mundo por aqui</h3>
          <p>Convide colegas para a ProSync ou explore outras áreas.</p>
        </div>`;
      return;
    }

    grid.innerHTML = feed.sugestoes.map(s => cardSugestao(s)).join('');
  } catch (err) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="icon">⚠</div><h3>Erro</h3><p>${escapeHtml(err.message)}</p></div>`;
  }
}

function cardSugestao(s) {
  const p = s.profissional;
  const iniciais = (p.nome || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  const avatar = p.foto_url
    ? `<img src="${p.foto_url}" alt="${escapeHtml(p.nome)}" />`
    : iniciais;

  const classeScore = s.score >= 70 ? 'alto' : (s.score >= 45 ? 'medio' : '');
  const local = [p.cidade, p.estado].filter(Boolean).join(', ');
  const skills = (p.skills || []).slice(0, 4)
    .map(x => `<span class="skill-tag">${escapeHtml(x)}</span>`).join('');
  const extras = (p.skills || []).length > 4 ? `<span class="skill-tag more">+${p.skills.length - 4}</span>` : '';
  const forcas = (s.forcas || []).slice(0, 3)
    .map(f => `<span class="forca-tag">✓ ${escapeHtml(f)}</span>`).join('');

  const jaConectado = s.match_status === 'match';
  const botaoPrincipal = jaConectado
    ? `<button class="btn-connect connected" onclick="abrirChatPorPessoa('${p.id}')">💬 Abrir conversa</button>`
    : (s.match_status === 'pendente'
      ? `<button class="btn-connect" disabled>⏳ Convite enviado</button>`
      : `<button class="btn-connect" onclick="conectarV2('${p.id}', this)">🤝 Conectar</button>`);

  return `
    <div class="sugestao-card">
      <div class="score-ring ${classeScore}" style="--p:${Math.round(s.score)}" title="Compatibilidade">
        <span>${Math.round(s.score)}%</span>
      </div>
      <div class="sugestao-top">
        <div class="avatar-lg">${avatar}</div>
        <div style="min-width:0;padding-right:44px">
          <div class="sugestao-nome">${escapeHtml(p.nome)}</div>
          ${p.headline ? `<div class="sugestao-headline">${escapeHtml(p.headline)}</div>` : ''}
          ${local ? `<div class="sugestao-loc">📍 ${escapeHtml(local)}</div>` : ''}
        </div>
      </div>
      <div class="card-skills">${skills}${extras}</div>
      <div class="motivo-ia">
        ${escapeHtml(s.motivo || 'Boa combinação de perfil.')}
        <span class="fonte">${s.fonte === 'gemini' ? '✦ analisado pela IA' : '◆ heurística local'}</span>
      </div>
      ${forcas ? `<div class="forcas-list">${forcas}</div>` : ''}
      <div class="sugestao-actions">
        ${botaoPrincipal}
        <button class="btn-salvar" onclick="salvarPerfil('${p.id}', this)" title="Salvar para depois">☆</button>
      </div>
    </div>`;
}

async function conectarV2(profissionalBId, btn) {
  if (!Sessao.logado) { abrirAuth('login'); return; }
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = '⏳ Analisando com IA...';
  try {
    const match = await fetchV2('/api/matches', {
      method: 'POST',
      body: JSON.stringify({ profissional_a_id: Sessao.id, profissional_b_id: profissionalBId }),
    });
    toast(`Convite enviado! Compatibilidade ${Math.round(match.score_ia)}% — ${match.motivo_ia}`, 'success');
    btn.className = 'btn-connect';
    btn.disabled = true;
    btn.textContent = '⏳ Convite enviado';
    // atualiza o contador de notificações do header
    if (typeof carregarMatchesPendentes === 'function') carregarMatchesPendentes();
  } catch (err) {
    toast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

async function salvarPerfil(alvoId, btn) {
  if (!Sessao.logado) { abrirAuth('login'); return; }
  try {
    await fetchV2(`/api/profissionais/${Sessao.id}/salvos/${alvoId}`, { method: 'POST' });
    btn.classList.add('ativo');
    btn.textContent = '★';
    toast('Perfil salvo para depois.', 'success');
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function abrirChatPorPessoa(outroId) {
  if (!Sessao.logado) { abrirAuth('login'); return; }
  try {
    const conversas = await fetchV2(`/api/profissionais/${Sessao.id}/conversas`);
    const c = conversas.find(x => x.profissional_id === outroId);
    if (c) {
      abrirChat(c.match_id, c.profissional_id, c.profissional_nome, c.profissional_foto);
    } else {
      toast('Conversa não encontrada — aceite o convite primeiro.', 'info');
    }
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ── Dashboard ───────────────────────────────────────────────────────── */
async function carregarDashboard() {
  const wrap = document.getElementById('dashboardConteudo');
  if (!wrap || !Sessao.logado) return;
  wrap.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const [dash, notifs, pendentes] = await Promise.all([
      fetchV2(`/api/dashboard/${Sessao.id}`),
      fetchV2(`/api/notificacoes?profissional_id=${Sessao.id}&limit=6`).catch(() => ({ itens: [], nao_lidas: 0 })),
      fetchV2(`/api/profissionais/${Sessao.id}/matches?status=pendente`).catch(() => []),
    ]);

    const primeiroNome = (dash.profissional.nome || '').split(' ')[0];
    const metrica = (icone, valor, rotulo, destaque = false) => `
      <div class="metric-card ${destaque ? 'destaque' : ''}">
        <span class="metric-icon">${icone}</span>
        <span class="metric-value">${valor}</span>
        <span class="metric-label">${rotulo}</span>
      </div>`;

    const passos = (dash.proximos_passos || [])
      .map((t, i) => `<div class="passo-item"><span class="num">${i + 1}</span><span>${escapeHtml(t)}</span></div>`)
      .join('');

    const pendentesHtml = pendentes.length
      ? pendentes.map(m => {
        const outroId = m.profissional_a_id === Sessao.id ? m.profissional_b_id : m.profissional_a_id;
        return `
          <div class="pendente-item" data-outro="${outroId}">
            <div class="avatar-sm pend-avatar">?</div>
            <div class="info">
              <h4 class="pend-nome">Carregando...</h4>
              <p>${escapeHtml(m.motivo_ia || 'Quer se conectar com você')} · ${Math.round(m.score_ia)}%</p>
            </div>
            <div class="acoes">
              <button class="icon-btn aceitar" onclick="responderMatch('${m.id}','aceitar',this)" title="Aceitar">✓</button>
              <button class="icon-btn recusar" onclick="responderMatch('${m.id}','recusar',this)" title="Recusar">✕</button>
            </div>
          </div>`;
      }).join('')
      : `<p style="color:var(--text-muted);font-size:13px">Nenhum convite pendente. 🎉</p>`;

    const notifHtml = notifs.itens?.length
      ? notifs.itens.map(n => `
          <div class="notif-item ${n.lida ? '' : 'nao-lida'}" onclick="marcarNotifLida('${n.id}', this)">
            <div>
              <div class="notif-titulo">${escapeHtml(n.titulo)}</div>
              ${n.mensagem ? `<div class="notif-msg">${escapeHtml(n.mensagem)}</div>` : ''}
              <div class="notif-data">${formatarData(n.criado_em)}</div>
            </div>
          </div>`).join('')
      : `<p style="color:var(--text-muted);font-size:13px">Sem notificações por aqui.</p>`;

    const sugestoesHtml = (dash.sugestoes || []).map(s => `
      <div class="pendente-item">
        <div class="avatar-sm">${(s.profissional.nome || '?')[0]}</div>
        <div class="info">
          <h4>${escapeHtml(s.profissional.nome)}</h4>
          <p>${escapeHtml(s.motivo)} · ${Math.round(s.score)}%</p>
        </div>
        <button class="btn-ghost" style="font-size:12px;padding:5px 12px"
          onclick="conectarV2('${s.profissional.id}', this)">Conectar</button>
      </div>`).join('');

    wrap.innerHTML = `
      <div class="dash-greeting">
        <h1>Olá, ${escapeHtml(primeiroNome)} 👋</h1>
        <p>${escapeHtml(dash.profissional.headline || 'Vamos construir suas próximas conexões.')}</p>
      </div>

      <div class="dash-metrics">
        ${metrica('🏆', dash.score_contribuicao, 'Score de contribuição', true)}
        ${metrica('🤝', dash.matches_pendentes, 'Convites pendentes')}
        ${metrica('💬', dash.conversas_ativas, 'Conversas ativas')}
        ${metrica('📥', dash.mensagens_nao_lidas, 'Mensagens não lidas')}
        ${metrica('🧠', dash.mentorias_ativas, 'Mentorias')}
        ${metrica('🏁', dash.desafios_participando, 'Desafios')}
        ${metrica('☆', dash.salvos, 'Perfis salvos')}
      </div>

      <div class="dash-cols">
        <div>
          <div class="passos-card">
            <h3>🚀 Próximos passos</h3>
            ${passos}
          </div>

          <div class="passos-card">
            <h3>🤝 Convites para responder
              <span style="margin-left:auto;font-size:12px;color:var(--text-muted)">${pendentes.length}</span>
            </h3>
            ${pendentesHtml}
          </div>

          <div class="passos-card">
            <h3>✨ Sugestões para você</h3>
            ${sugestoesHtml || '<p style="color:var(--text-muted);font-size:13px">Sem sugestões no momento.</p>'}
          </div>
        </div>

        <div>
          <div class="notif-panel">
            <h3>
              🔔 Notificações
              ${notifs.nao_lidas ? `<button onclick="marcarTodasNotif()">marcar todas como lidas</button>` : ''}
            </h3>
            ${notifHtml}
          </div>
        </div>
      </div>`;

    // Preenche nome/avatar dos convites pendentes (o /matches nao traz o perfil do outro lado)
    pendentes.forEach(m => {
      const outroId = m.profissional_a_id === Sessao.id ? m.profissional_b_id : m.profissional_a_id;
      const card = wrap.querySelector(`.pendente-item[data-outro="${outroId}"]`);
      if (!card) return;
      fetchV2(`/api/profissionais/${outroId}/card`).then(p => {
        card.querySelector('.pend-nome').textContent = p.nome;
        const av = card.querySelector('.pend-avatar');
        av.textContent = (p.nome || '?')[0].toUpperCase();
        av.title = p.headline || '';
      }).catch(() => {
        // perfil removido (ou dado legado): esconde o convite em vez de mostrar "Profissional"
        card.style.display = 'none';
      });
    });
  } catch (err) {
    wrap.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro ao carregar painel</h3><p>${escapeHtml(err.message)}</p></div>`;
  }
}

async function responderMatch(matchId, acao, btn) {
  btn.disabled = true;
  try {
    await fetchV2(`/api/matches/${matchId}/${acao}`, { method: 'POST' });
    toast(acao === 'aceitar'
      ? 'Conexão aceita! +10 pontos de contribuição 🎉'
      : 'Convite recusado.', acao === 'aceitar' ? 'success' : 'info');
    carregarDashboard();
    if (acao === 'aceitar' && typeof carregarMatchesPendentes === 'function') carregarMatchesPendentes();
  } catch (err) {
    toast(err.message, 'error');
    btn.disabled = false;
  }
}

async function marcarNotifLida(id, el) {
  try {
    await fetchV2(`/api/notificacoes/${id}/lida`, { method: 'PATCH' });
    el.classList.remove('nao-lida');
  } catch (_) {}
}

async function marcarTodasNotif() {
  try {
    await fetchV2(`/api/notificacoes/marcar-todas-lidas?profissional_id=${Sessao.id}`, { method: 'POST' });
    carregarDashboard();
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ── Estatísticas da landing ─────────────────────────────────────────── */
async function carregarStatsV2() {
  try {
    const s = await fetchV2('/api/stats');
    const el = (id, v) => { const n = document.getElementById(id); if (n) n.textContent = v; };
    el('totalProfissionais', s.profissionais);
    el('totalMatches', s.matches_ativos);
    el('statCidades', s.cidades);
    el('statDesafios', s.desafios_abertos);

    const chip = document.getElementById('statsModoIa');
    if (chip) {
      chip.className = `ai-chip ${s.modo_ia === 'gemini' ? 'gemini' : ''}`;
      chip.innerHTML = `<span class="dot"></span>${s.modo_ia === 'gemini' ? 'IA Gemini ativa' : 'Modo heurístico'}`;
    }
  } catch (_) {}
}

/* ── Init ────────────────────────────────────────────────────────────── */
(function initV2() {
  // substitui o header de usuário antigo
  const headerAhual = document.getElementById('headerProfile');
  if (headerAhual) headerAhual.style.display = 'none';

  document.addEventListener('DOMContentLoaded', async () => {
    atualizarHeaderV2();
    carregarStatsV2();

    let estavaLogado = !!Sessao.token;
    await Sessao.restaurar();
    atualizarHeaderV2();

    const demoBanner = document.getElementById('demoBanner');
    if (demoBanner) demoBanner.style.display = Sessao.logado ? 'none' : 'flex';

    if (Sessao.logado) {
      irPara('dashboard');
    } else {
      irPara('descobrir');
      // token existia mas expirou/ficou invalido: avisa em vez de falhar em silencio
      if (estavaLogado) {
        toast('Sua sessão expirou. Entre novamente.', 'error');
        abrirAuth('login');
      }
    }
  });
})();
