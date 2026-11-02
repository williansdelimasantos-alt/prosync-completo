/* ═══════════════════════════════════════════════════════════════════════
   ProSync — Frontend Logic
   ═══════════════════════════════════════════════════════════════════════ */

const API_BASE = '';

let profissionais = [];
let matchesPendentes = 0;
let profissionalLogadoId = null;
let abaAtiva = 'profissionais';
let chatMatchId = null;
let chatOutroId = null;

/* ── Helpers ────────────────────────────────────────────────────────── */
async function apiFetch(url, options = {}) {
  const { headers: customHeaders, ...rest } = options;
  const headers = { 'Content-Type': 'application/json', ...customHeaders };
  // v2: envia o JWT quando houver sessao (endpoints protegidos exigem)
  const token = localStorage.getItem('prosync_token');
  if (token && !headers['Authorization']) headers['Authorization'] = `Bearer ${token}`;

  const resp = await fetch(API_BASE + url, { ...rest, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    const detalhe = typeof err.detail === 'string' ? err.detail : `Erro ${resp.status}`;
    throw new Error(detalhe);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
}

function closeModal(id) {
  document.getElementById(id).classList.remove('active');
}

function formatarData(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('pt-BR', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatarHora(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function senioridadeLabel(s) {
  const map = { junior: 'Júnior', pleno: 'Pleno', senior: 'Sênior' };
  return map[s] || s;
}

/* ── Aba Navigation ─────────────────────────────────────────────────── */
function mudarAba(aba) {
  abaAtiva = aba;
  document.querySelectorAll('[data-aba]').forEach(a => a.classList.remove('active'));
  document.querySelector(`[data-aba="${aba}"]`)?.classList.add('active');

  // v2: esconde as telas novas (descobrir/painel) ao navegar pelas antigas
  document.querySelectorAll('.aba-v2').forEach(sec => { sec.style.display = 'none'; });

  document.getElementById('abaProfissionais').style.display = aba === 'profissionais' ? 'block' : 'none';
  document.getElementById('abaDesafios').style.display = aba === 'desafios' ? 'block' : 'none';
  document.getElementById('abaConversas').style.display = aba === 'conversas' ? 'block' : 'none';
  document.getElementById('abaMentoria').style.display = aba === 'mentoria' ? 'block' : 'none';
  document.getElementById('abaOportunidades').style.display = aba === 'oportunidades' ? 'block' : 'none';
  document.getElementById('heroSection').style.display = 'none';

  if (aba === 'profissionais' && !profissionais.length) carregarProfissionais();
  if (aba === 'desafios') carregarDesafios();
  if (aba === 'conversas') carregarConversas();
  if (aba === 'mentoria') carregarMinhasMentorias();
  if (aba === 'oportunidades') carregarOportunidades();
}

/* ── Load Profissionais ─────────────────────────────────────────────── */
async function carregarProfissionais() {
  const grid = document.getElementById('profissionaisGrid');
  grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const params = new URLSearchParams();
    const search = document.getElementById('filterSearch')?.value.trim();
    const skill = document.getElementById('filterSkill')?.value;
    const senioridade = document.getElementById('filterSenioridade')?.value;
    if (search) params.set('search', search);
    if (skill) params.set('skill', skill);
    if (senioridade) params.set('senioridade', senioridade);

    profissionais = await apiFetch(`/api/profissionais?${params.toString()}`);
    renderizarGrid(profissionais);
  } catch (e) {
    grid.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro ao carregar</h3><p>${e.message}</p></div>`;
  }
}

function renderizarGrid(lista) {
  const grid = document.getElementById('profissionaisGrid');
  document.getElementById('feedCount').textContent = `${lista.length} profissional(is)`;

  if (lista.length === 0) {
    grid.innerHTML = `<div class="empty-state"><div class="icon">🔍</div><h3>Nenhum profissional encontrado</h3><p>Tente ajustar os filtros ou cadastre-se!</p></div>`;
    return;
  }

  grid.innerHTML = lista.map(p => criarCard(p)).join('');
}

function criarCard(p) {
  const iniciais = p.nome?.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?';
  const avatar = p.foto_url
    ? `<img src="${p.foto_url}" alt="${p.nome}" />`
    : `<div class="avatar-placeholder">${iniciais}</div>`;

  const skills = (p.skills || []).slice(0, 4);
  const skillsExtra = (p.skills || []).length - 4;
  const skillsHtml = skills.map(s => `<span class="skill-tag">${s}</span>`).join('');
  const moreHtml = skillsExtra > 0 ? `<span class="skill-tag more">+${skillsExtra}</span>` : '';

  const objetivos = p.objetivos || [];
  const objetivosStr = objetivos.length > 0 ? objetivos.join(', ') : '';
  const score = p.score_contribuicao || 0;
  const scoreClass = score >= 50 ? 'high' : (score >= 20 ? 'medium' : 'low');

  return `
    <div class="card" data-id="${p.id}">
      <div class="card-top">
        <div class="card-avatar">${avatar}</div>
        <div class="card-info">
          <h3>${p.nome}</h3>
          <div class="location">${p.cidade}${p.estado ? ', ' + p.estado : ''}</div>
        </div>
      </div>
      <div class="card-bio">${p.bio || ''}</div>
      <div class="card-skills">${skillsHtml}${moreHtml}</div>
      <div class="card-senioridade">
        <span class="senioridade-badge ${p.senioridade}">${senioridadeLabel(p.senioridade)}</span>
        ${objetivosStr ? `<span style="color:var(--text-muted);font-size:12px;margin-left:8px">${objetivosStr}</span>` : ''}
        ${score > 0 ? `<span class="reputation-score ${scoreClass}" onclick="verReputacao('${p.id}')" title="Score de contribuição">🏆 ${score}</span>` : ''}
      </div>
      <div class="card-actions">
        <button class="btn-connect" onclick="conectar('${p.id}')" id="connect-${p.id}">
          <span>🤝</span> Conectar
        </button>
        <button class="btn-profile" onclick="verPerfil('${p.id}')">Perfil</button>
      </div>
    </div>
  `;
}

/* ── Profile Modal ──────────────────────────────────────────────────── */
async function verPerfil(id) {
  try {
    const p = await apiFetch(`/api/profissionais/${id}`);
    const modalBody = document.getElementById('profileModalBody');
    const modalFooter = document.getElementById('profileModalFooter');

    const iniciais = p.nome?.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?';
    const avatar = p.foto_url
      ? `<img src="${p.foto_url}" alt="${p.nome}" />`
      : `<div class="avatar-placeholder">${iniciais}</div>`;

    modalBody.innerHTML = `
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
        <div class="card-avatar">${avatar}</div>
        <div>
          <h2>${p.nome}</h2>
          <div class="location">${p.cidade}${p.estado ? ', ' + p.estado : ''}</div>
          <span class="senioridade-badge ${p.senioridade}">${senioridadeLabel(p.senioridade)}</span>
          ${(p.score_contribuicao || 0) > 0
            ? `<span class="reputation-score ${p.score_contribuicao >= 50 ? 'high' : (p.score_contribuicao >= 20 ? 'medium' : 'low')}" style="margin-left:8px">🏆 ${p.score_contribuicao}</span>`
            : ''}
        </div>
      </div>
      <div class="bio-full">${p.bio || 'Sem bio ainda.'}</div>
      <div class="modal-section">
        <h4>Skills</h4>
        <div class="card-skills">${(p.skills || []).map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
      </div>
      <div class="modal-section">
        <h4>Objetivos</h4>
        <div class="card-skills">${(p.objetivos || []).map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
      </div>
      <div class="modal-section">
        <h4>Disponibilidade</h4>
        <p style="color:var(--text-muted);font-size:14px">${(p.disponibilidade || []).join(', ') || 'Não informado'}</p>
      </div>
      <div class="modal-section">
        <h4>Membro desde</h4>
        <p style="color:var(--text-muted);font-size:14px">${formatarData(p.criado_em)}</p>
      </div>
    `;

    modalFooter.innerHTML = `
      <button class="btn-connect" onclick="conectar('${p.id}'); closeModal('profileModal')">
        <span>🤝</span> Conectar
      </button>
      <button class="btn-profile" onclick="verReputacao('${p.id}'); closeModal('profileModal')">🏆 Score</button>
      <button class="btn-profile" onclick="closeModal('profileModal')">Fechar</button>
    `;

    document.getElementById('profileModal').classList.add('active');
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ── Connect / Match ────────────────────────────────────────────────── */
async function conectar(profissionalBId) {
  if (!profissionalLogadoId) {
    toast('Você precisa se cadastrar primeiro!', 'info');
    openRegisterModal();
    return;
  }

  if (profissionalBId === profissionalLogadoId) {
    toast('Você não pode conectar com você mesmo!', 'error');
    return;
  }

  const btn = document.getElementById(`connect-${profissionalBId}`);
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Analisando...'; }

  try {
    const match = await apiFetch('/api/matches', {
      method: 'POST',
      body: JSON.stringify({
        profissional_a_id: profissionalLogadoId,
        profissional_b_id: profissionalBId,
      }),
    });

    if (match.status === 'pendente') {
      const motivo = match.motivo_ia ? ` — ${match.motivo_ia}` : '';
      toast(`Convite enviado! Compatibilidade ${Math.round(match.score_ia)}%${motivo}`, 'success');
    } else if (match.status === 'match') {
      toast('Vocês já estão conectados!', 'info');
    }

    if (btn) {
      btn.className = 'btn-connect connected';
      btn.textContent = `✅ Match ${match.score_ia}%`;
      btn.disabled = true;
    }
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '🤝 Conectar'; }
  }
}

/* ── Register ────────────────────────────────────────────────────────── */
function openRegisterModal() {
  // v2: o cadastro acontece no modal unificado de autenticacao (com JWT)
  if (typeof abrirAuth === 'function') {
    abrirAuth('cadastro');
    return;
  }
  const legado = document.getElementById('registerModal');
  if (legado) legado.classList.add('active');
}

async function cadastrarProfissional(e) {
  e.preventDefault();
  const form = document.getElementById('registerForm');
  const data = new FormData(form);
  const body = {
    nome: data.get('nome'),
    email: data.get('email'),
    senha: data.get('senha'),
    cidade: data.get('cidade') || '',
    estado: data.get('estado') || '',
    bio: data.get('bio') || '',
    senioridade: data.get('senioridade') || 'junior',
    skills: data.get('skills')?.split(',').map(s => s.trim()).filter(Boolean) || [],
    objetivos: [...form.querySelectorAll('input[name="objetivos"]:checked')].map(el => el.value),
    disponibilidade: [],
    areas_interesse: [],
  };

  const btn = form.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = 'Cadastrando...';

  try {
    const result = await apiFetch('/api/profissionais', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    // O cadastro NAO devolve token: faz login automatico para o usuario ja
    // sair com sessao JWT valida (antes ficava um id sem token = sessao fantasma).
    let logado = false;
    try {
      const sessao = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: body.email, senha: body.senha }),
      });
      localStorage.setItem('prosync_token', sessao.access_token);
      localStorage.setItem('prosync_user_id', sessao.profissional_id);
      profissionalLogadoId = sessao.profissional_id;
      logado = true;
    } catch (_) {
      // se o login automatico falhar, cai no fluxo antigo (id sem token e
      // limpo no boot seguinte pelo v2.js)
      profissionalLogadoId = result.id;
      localStorage.setItem('prosync_user_id', result.id);
    }

    toast(`Bem-vindo(a), ${result.nome}!`, 'success');
    closeModal('registerModal');
    carregarProfissionais();
    atualizarHeader();
    if (logado && typeof irPara === 'function') irPara('dashboard');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Criar Perfil';
  }
}

/* ── Header / Status ─────────────────────────────────────────────────── */
function atualizarHeader() {
  // v2: o header de usuario e renderizado pelo v2.js (sessao com JWT)
  if (typeof atualizarHeaderV2 === 'function') atualizarHeaderV2();

  if (profissionalLogadoId) {
    carregarMatchesPendentes();
    carregarNaoLidas();
  }
}

async function carregarMatchesPendentes() {
  if (!profissionalLogadoId) return;
  try {
    const matches = await apiFetch(`/api/profissionais/${profissionalLogadoId}/matches`);
    const pendentes = matches.filter(m => m.status === 'pendente').length;
    matchesPendentes = pendentes;
    const badge = document.getElementById('matchBadge');
    if (pendentes > 0) {
      badge.style.display = 'inline';
      badge.textContent = pendentes;
    } else {
      badge.style.display = 'none';
    }
  } catch (e) {
    // ignore
  }
}

async function carregarNaoLidas() {
  if (!profissionalLogadoId) return;
  try {
    const conversas = await apiFetch(`/api/profissionais/${profissionalLogadoId}/conversas`);
    const totalNaoLidas = conversas.reduce((acc, c) => acc + c.nao_lidas, 0);
    const badge = document.getElementById('conversasBadge');
    if (totalNaoLidas > 0) {
      badge.style.display = 'inline';
      badge.textContent = totalNaoLidas;
    } else {
      badge.style.display = 'none';
    }
  } catch (_) {}
}

/* ═══════════════════════════════════════════════════════════════════════
   CHAT
   ═══════════════════════════════════════════════════════════════════════ */

async function carregarConversas() {
  const container = document.getElementById('conversasList');
  if (!profissionalLogadoId) {
    container.innerHTML = `<div class="empty-state"><div class="icon">🔒</div><h3>Faça o cadastro primeiro</h3><p>Cadastre-se para ver suas conversas.</p></div>`;
    return;
  }

  container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const conversas = await apiFetch(`/api/profissionais/${profissionalLogadoId}/conversas`);

    if (conversas.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="icon">💬</div><h3>Nenhuma conversa ainda</h3><p>Conecte-se com outros profissionais para começar a conversar!</p></div>`;
      return;
    }

    container.innerHTML = conversas.map(c => `
      <div class="conversa-item" onclick="abrirChat('${c.match_id}', '${c.profissional_id}', '${c.profissional_nome.replace("'", "\\'")}', '${c.profissional_foto}')">
        <div class="avatar-sm">
          ${c.profissional_foto
            ? `<img src="${c.profissional_foto}" alt="${c.profissional_nome}" />`
            : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:18px">${c.profissional_nome[0]}</div>`}
        </div>
        <div class="conversa-info">
          <h4>${c.profissional_nome}</h4>
          <div class="ultima-msg">${c.ultima_mensagem || 'Nenhuma mensagem ainda'}</div>
          <div class="conversa-score">Match ${c.score_ia}%</div>
        </div>
        ${c.nao_lidas > 0 ? `<div class="conversa-badge">${c.nao_lidas}</div>` : ''}
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro</h3><p>${e.message}</p></div>`;
  }
}

function abrirChat(matchId, outroId, outroNome, outroFoto) {
  chatMatchId = matchId;
  chatOutroId = outroId;
  document.getElementById('chatNome').textContent = outroNome;

  const avatar = document.getElementById('chatAvatar');
  if (outroFoto) {
    avatar.src = outroFoto;
    avatar.style.display = 'inline';
  } else {
    avatar.style.display = 'none';
  }

  document.getElementById('chatModal').classList.add('active');
  carregarMensagens();
}

function fecharChat() {
  chatMatchId = null;
  chatOutroId = null;
  closeModal('chatModal');
}

async function carregarMensagens() {
  if (!chatMatchId) return;
  const container = document.getElementById('chatMessages');

  try {
    const msgs = await apiFetch(`/api/mensagens/${chatMatchId}`);

    if (msgs.length === 0) {
      container.innerHTML = `<div class="chat-empty"><div><div class="icon">💬</div><p>Nenhuma mensagem ainda. Envie algo!</p></div></div>`;
      return;
    }

    container.innerHTML = msgs.map(m => {
      const isMine = m.remetente_id === profissionalLogadoId;
      const readIndicator = isMine && m.lida ? `<span class="msg-read">✓ Lida</span>` : '';
      return `<div class="chat-msg ${isMine ? 'mine' : 'theirs'}">
        ${m.conteudo}
        <span class="msg-time">${formatarHora(m.criado_em)}</span>
        ${readIndicator}
      </div>`;
    }).join('');

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;

    // Mark received messages as read
    msgs.filter(m => m.remetente_id !== profissionalLogadoId && !m.lida).forEach(m => {
      apiFetch(`/api/mensagens/${m.id}/ler`, { method: 'PATCH' }).catch(() => {});
    });

  } catch (e) {
    container.innerHTML = `<div class="chat-empty"><div><div class="icon">⚠</div><p>Erro ao carregar mensagens: ${e.message}</p></div></div>`;
  }
}

async function enviarMensagem() {
  const input = document.getElementById('chatInput');
  const conteudo = input.value.trim();
  if (!conteudo || !chatMatchId || !profissionalLogadoId) return;

  input.disabled = true;

  try {
    await apiFetch('/api/mensagens', {
      method: 'POST',
      body: JSON.stringify({
        match_id: chatMatchId,
        remetente_id: profissionalLogadoId,
        conteudo: conteudo,
      }),
    });

    input.value = '';
    carregarMensagens();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    input.disabled = false;
    input.focus();
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   DESAFIOS
   ═══════════════════════════════════════════════════════════════════════ */

async function carregarDesafios() {
  const container = document.getElementById('desafiosList');
  container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const params = new URLSearchParams();
    const status = document.getElementById('desafioFilterStatus')?.value;
    const skill = document.getElementById('desafioFilterSkill')?.value.trim();
    if (status) params.set('status', status);
    if (skill) params.set('skill', skill);

    const desafios = await apiFetch(`/api/desafios?${params.toString()}`);

    if (desafios.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="icon">🏆</div><h3>Nenhum desafio encontrado</h3><p>Crie o primeiro desafio colaborativo!</p></div>`;
      return;
    }

    container.innerHTML = desafios.map(d => criarDesafioCard(d)).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro</h3><p>${e.message}</p></div>`;
  }
}

function criarDesafioCard(d) {
  const statusLabels = { aberto: 'Aberto', em_andamento: 'Em andamento', concluido: 'Concluído' };
  const statusLabel = statusLabels[d.status] || d.status;
  const tipoIcon = d.tipo === 'dupla' ? '👥' : '👨‍👩‍👧‍👦';

  const skillsHtml = (d.skills_necessarias || []).map(s => `<span class="skill-tag">${s}</span>`).join('');
  const prazoStr = d.prazo ? `📅 ${formatarData(d.prazo)}` : '';

  const podeInscrever = d.status === 'aberto' && profissionalLogadoId;

  return `
    <div class="desafio-card">
      <div class="desafio-header">
        <div class="desafio-icon">${tipoIcon}</div>
        <h3>${d.titulo}</h3>
        <span class="desafio-status-badge ${d.status}">${statusLabel}</span>
      </div>
      <div class="desafio-body">${d.descricao || ''}</div>
      <div class="desafio-skills">${skillsHtml}</div>
      <div class="desafio-meta">
        <span>${tipoIcon} ${d.tipo === 'dupla' ? 'Dupla' : 'Grupo'}</span>
        ${prazoStr ? `<span>${prazoStr}</span>` : ''}
      </div>
      <div class="desafio-actions">
        <button class="btn-participar" onclick="participarDesafio('${d.id}', this)" id="part-${d.id}">
          ${podeInscrever ? '➕ Participar' : '🔍 Ver detalhes'}
        </button>
        <button class="btn-profile" onclick="verDetalheDesafio('${d.id}')">Detalhes</button>
      </div>
    </div>
  `;
}

async function participarDesafio(desafioId, btn) {
  if (!profissionalLogadoId) {
    toast('Cadastre-se primeiro para participar!', 'info');
    openRegisterModal();
    return;
  }

  btn.disabled = true;
  btn.textContent = '⏳ Inscrevendo...';

  try {
    await apiFetch(`/api/desafios/${desafioId}/participar?profissional_id=${profissionalLogadoId}`, {
      method: 'POST',
    });
    btn.className = 'btn-participar inscrito';
    btn.textContent = '✅ Inscrito';
    toast('Inscrição realizada com sucesso!', 'success');
  } catch (e) {
    toast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = '➕ Participar';
  }
}

async function verDetalheDesafio(desafioId) {
  try {
    const d = await apiFetch(`/api/desafios/${desafioId}`);
    const participantes = await apiFetch(`/api/desafios/${desafioId}/participantes`);

    const statusLabels = { aberto: 'Aberto', em_andamento: 'Em andamento', concluido: 'Concluído' };
    const skillsHtml = (d.skills_necessarias || []).map(s => `<span class="skill-tag">${s}</span>`).join('');
    const prazoStr = d.prazo ? `📅 ${formatarData(d.prazo)}` : 'Sem prazo definido';
    const tipoIcon = d.tipo === 'dupla' ? '👥' : '👨‍👩‍👧‍👦';

    const participantesHtml = participantes.map(p => `
      <div class="participante-item">
        <div class="avatar-sm">
          ${p.profissional_foto
            ? `<img src="${p.profissional_foto}" alt="${p.profissional_nome}" />`
            : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:14px">${p.profissional_nome?.[0] || '?'}</div>`}
        </div>
        <span>${p.profissional_nome || 'Profissional'}</span>
      </div>
    `).join('') || '<p style="color:var(--text-muted)">Nenhum participante ainda.</p>';

    const body = document.getElementById('desafioDetailBody');
    body.innerHTML = `
      <div class="desafio-detail-header">
        <div class="desafio-icon" style="width:56px;height:56px;font-size:28px">${tipoIcon}</div>
        <div>
          <h2>${d.titulo}</h2>
          <span class="desafio-status-badge ${d.status}">${statusLabels[d.status]}</span>
        </div>
      </div>

      <div class="desafio-detail-section">
        <h4>Descrição</h4>
        <p style="color:var(--text-secondary);font-size:15px;line-height:1.7">${d.descricao || 'Sem descrição.'}</p>
      </div>

      <div class="desafio-detail-section">
        <h4>Skills necessárias</h4>
        <div class="card-skills">${skillsHtml || '<span style="color:var(--text-muted)">Nenhuma</span>'}</div>
      </div>

      <div class="desafio-detail-section">
        <h4>Informações</h4>
        <p style="color:var(--text-muted);font-size:14px">
          ${tipoIcon} ${d.tipo === 'dupla' ? 'Dupla' : 'Grupo'} &middot;
          ${prazoStr}
        </p>
      </div>

      <div class="desafio-detail-section">
        <h4>Participantes (${participantes.length})</h4>
        ${participantesHtml}
      </div>
    `;

    document.getElementById('desafioDetailModal').classList.add('active');
  } catch (e) {
    toast(e.message, 'error');
  }
}

function openCreateDesafioModal() {
  if (!profissionalLogadoId) {
    toast('Cadastre-se primeiro para criar um desafio!', 'info');
    openRegisterModal();
    return;
  }
  document.getElementById('createDesafioModal').classList.add('active');
}

async function criarDesafio(e) {
  e.preventDefault();
  const form = document.getElementById('createDesafioForm');
  const data = new FormData(form);

  const body = {
    criador_id: profissionalLogadoId,
    titulo: data.get('titulo'),
    descricao: data.get('descricao') || '',
    skills_necessarias: data.get('skills')?.split(',').map(s => s.trim()).filter(Boolean) || [],
    tipo: data.get('tipo') || 'dupla',
    prazo: null,
  };

  const prazoVal = data.get('prazo');
  if (prazoVal) {
    body.prazo = new Date(prazoVal).toISOString();
  }

  const btn = form.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = 'Criando...';

  try {
    await apiFetch('/api/desafios', {
      method: 'POST',
      body: JSON.stringify(body),
      headers: { 'X-Profissional-Id': profissionalLogadoId },
    });
    toast('Desafio criado com sucesso!', 'success');
    closeModal('createDesafioModal');
    form.reset();
    carregarDesafios();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Criar Desafio';
  }
}

/* ── Stats ──────────────────────────────────────────────────────────── */
async function carregarStats() {
  try {
    const all = await apiFetch('/api/profissionais?limit=200');
    document.getElementById('totalProfissionais').textContent = all.length.toString();
  } catch (_) {}
}

/* ── Hamburger Menu (mobile) ─────────────────────────────────────────── */
function toggleHamburger() {
  const nav = document.getElementById('headerNav');
  nav.classList.toggle('open');
}
function closeHamburger() {
  const nav = document.getElementById('headerNav');
  nav.classList.remove('open');
}

/* ── Init ────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  carregarProfissionais();
  carregarStats();

  // v2: a sessao real e restaurada pelo v2.js a partir do JWT
  const savedId = localStorage.getItem('prosync_user_id');
  const token = localStorage.getItem('prosync_token');
  if (savedId && !token) {
    // id orfao sem token (ex.: cadastro no v1 que nao gera JWT): limpa para
    // evitar estado inconsistente (navbar "logada" sem sessao por tras)
    localStorage.removeItem('prosync_user_id');
    profissionalLogadoId = null;
    atualizarHeader();
    return;
  }
  if (savedId) {
    profissionalLogadoId = savedId;
    atualizarHeader();
  }
});

/* ── Keyboard: Escape closes modals ─────────────────────────────────── */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (document.getElementById('chatModal').classList.contains('active')) {
      fecharChat();
    } else {
      document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
  }
});

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('active');
  });
});

/* ═══════════════════════════════════════════════════════════════════════
   MENTORIA
   ═══════════════════════════════════════════════════════════════════════ */

function mudarSubAbaMentoria(subaba, btn) {
  document.querySelectorAll('#abaMentoria .tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('mentoriaSubMinhas').style.display = subaba === 'minhas' ? 'block' : 'none';
  document.getElementById('mentoriaSubMentores').style.display = subaba === 'mentores' ? 'block' : 'none';
  if (subaba === 'mentores') carregarMentores();
}

async function carregarMinhasMentorias() {
  const container = document.getElementById('mentoriasList');
  if (!profissionalLogadoId) {
    container.innerHTML = `<div class="empty-state"><div class="icon">🔒</div><h3>Faça o cadastro primeiro</h3><p>Cadastre-se para participar do programa de mentoria.</p></div>`;
    return;
  }

  container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const mentorias = await apiFetch(`/api/mentorias?profissional_id=${profissionalLogadoId}`);
    if (mentorias.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="icon">🧠</div><h3>Nenhuma mentoria ainda</h3><p>Encontre um mentor ou aguarde solicitações.</p></div>`;
      return;
    }

    container.innerHTML = mentorias.map(m => criarMentoriaCard(m)).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro</h3><p>${e.message}</p></div>`;
  }
}

function criarMentoriaCard(m) {
  const statusLabels = { pendente: 'Pendente', ativa: 'Ativa', concluida: 'Concluída' };
  const statusLabel = statusLabels[m.status] || m.status;
  const souMentor = m.mentor_id === profissionalLogadoId;
  const outroNome = souMentor ? m.mentorado_nome : m.mentor_nome;
  const outroFoto = souMentor ? m.mentorado_foto : m.mentor_foto;
  const iniciais = (outroNome || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  const avatar = outroFoto
    ? `<img src="${outroFoto}" alt="${outroNome}" />`
    : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:18px">${iniciais}</div>`;
  const papel = souMentor ? 'Mentor' : 'Mentorado';

  let actions = '';
  if (m.status === 'pendente' && souMentor) {
    actions = `<button class="btn-connect" onclick="aceitarMentoria('${m.id}')">✅ Aceitar</button>`;
  }
  if (m.status === 'ativa') {
    actions = `<button class="btn-connect" onclick="concluirMentoria('${m.id}')" style="background:var(--green)">🏁 Concluir</button>`;
  }

  return `
    <div class="mentoria-card">
      <div class="mentoria-header">
        <div class="avatar-sm">${avatar}</div>
        <div>
          <h3>${outroNome || 'Profissional'}</h3>
          <div class="mentoria-area">${papel} · ${m.area || 'Área geral'}</div>
        </div>
        <span class="mentoria-status-badge ${m.status}">${statusLabel}</span>
      </div>
      <div class="mentoria-body">${m.objetivos || ''}</div>
      ${actions ? `<div class="mentoria-actions">${actions}</div>` : ''}
    </div>
  `;
}

async function carregarMentores() {
  const container = document.getElementById('mentoresList');
  if (!profissionalLogadoId) {
    container.innerHTML = `<div class="empty-state"><div class="icon">🔒</div><h3>Faça o cadastro primeiro</h3><p>Cadastre-se para encontrar mentores.</p></div>`;
    return;
  }

  container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const mentores = await apiFetch('/api/profissionais/mentores');
    if (mentores.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="icon">🔍</div><h3>Nenhum mentor disponível</h3><p>Nenhum profissional com objetivo de mentorar encontrado.</p></div>`;
      return;
    }

    const lista = mentores.filter(m => m.id !== profissionalLogadoId);
    if (lista.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="icon">😅</div><h3>Ninguém além de você</h3><p>Você é o único com objetivo de mentorar. Que tal cadastrar outro perfil?</p></div>`;
      return;
    }

    container.innerHTML = lista.map(m => {
      const iniciais = m.nome?.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?';
      const avatar = m.foto_url
        ? `<img src="${m.foto_url}" alt="${m.nome}" />`
        : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:18px">${iniciais}</div>`;
      return `
        <div class="mentor-item" onclick="openSolicitarMentoria('${m.id}', '${m.nome.replace("'", "\\'")}')">
          <div class="avatar-sm">${avatar}</div>
          <div class="mentor-info">
            <h4>${m.nome}</h4>
            <div class="mentor-detail">${m.cidade}${m.estado ? ', ' + m.estado : ''} · ${senioridadeLabel(m.senioridade)} · ${(m.skills || []).join(', ')}</div>
          </div>
          <button class="btn-filter" style="padding:6px 14px;font-size:12px">Solicitar</button>
        </div>
      `;
    }).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro</h3><p>${e.message}</p></div>`;
  }
}

function openSolicitarMentoria(mentorId, mentorNome) {
  if (!profissionalLogadoId) {
    toast('Cadastre-se primeiro!', 'info');
    openRegisterModal();
    return;
  }
  document.getElementById('solicitarMentorId').value = mentorId;
  document.getElementById('solicitarMentorNome').textContent = mentorNome;
  document.getElementById('solicitarMentoriaModal').classList.add('active');
}

async function solicitarMentoria(e) {
  e.preventDefault();
  const form = document.getElementById('solicitarMentoriaForm');
  const data = new FormData(form);

  const mentorId = data.get('mentor_id');
  const body = {
    mentorado_id: profissionalLogadoId,
    mentor_id: mentorId,
    area: data.get('area') || '',
    objetivos: data.get('objetivos') || '',
  };

  const btn = form.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = 'Solicitando...';

  try {
    await apiFetch('/api/mentorias/solicitar', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    toast('Mentoria solicitada com sucesso!', 'success');
    closeModal('solicitarMentoriaModal');
    form.reset();
    carregarMinhasMentorias();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Solicitar Mentoria';
  }
}

async function aceitarMentoria(mentoriaId) {
  try {
    await apiFetch(`/api/mentorias/${mentoriaId}/aceitar`, { method: 'PATCH' });
    toast('Mentoria aceita! 🎉', 'success');
    carregarMinhasMentorias();
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function concluirMentoria(mentoriaId) {
  try {
    await apiFetch(`/api/mentorias/${mentoriaId}/concluir`, { method: 'PATCH' });
    toast('Mentoria concluída! 🏆 +25 pontos para o mentor, +10 para o mentorado', 'success');
    carregarMinhasMentorias();
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   OPORTUNIDADES
   ═══════════════════════════════════════════════════════════════════════ */

function openCreateOportunidadeModal() {
  if (!profissionalLogadoId) {
    toast('Cadastre-se primeiro para criar uma oportunidade!', 'info');
    openRegisterModal();
    return;
  }
  document.getElementById('createOportunidadeModal').classList.add('active');
}

async function criarOportunidade(e) {
  e.preventDefault();
  const form = document.getElementById('createOportunidadeForm');
  const data = new FormData(form);

  const body = {
    criador_id: profissionalLogadoId,
    titulo: data.get('titulo'),
    descricao: data.get('descricao') || '',
    tipo: data.get('tipo') || 'vaga',
    skills_necessarias: data.get('skills')?.split(',').map(s => s.trim()).filter(Boolean) || [],
    contato: data.get('contato') || '',
  };

  const btn = form.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = 'Publicando...';

  try {
    await apiFetch('/api/oportunidades', {
      method: 'POST',
      body: JSON.stringify(body),
      headers: { 'X-Profissional-Id': profissionalLogadoId },
    });
    toast('Oportunidade publicada! +5 pontos de contribuição', 'success');
    closeModal('createOportunidadeModal');
    form.reset();
    carregarOportunidades();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Publicar Oportunidade';
  }
}

async function carregarOportunidades() {
  const container = document.getElementById('oportunidadesList');
  container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

  try {
    const params = new URLSearchParams();
    const tipo = document.getElementById('opFilterTipo')?.value;
    const skill = document.getElementById('opFilterSkill')?.value.trim();
    const status = document.getElementById('opFilterStatus')?.value;
    if (tipo) params.set('tipo', tipo);
    if (skill) params.set('skill', skill);
    if (status) params.set('status', status);

    const oportunidades = await apiFetch(`/api/oportunidades?${params.toString()}`);

    if (oportunidades.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="icon">💼</div><h3>Nenhuma oportunidade encontrada</h3><p>Crie a primeira oportunidade!</p></div>`;
      return;
    }

    container.innerHTML = oportunidades.map(o => criarOportunidadeCard(o)).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><h3>Erro</h3><p>${e.message}</p></div>`;
  }
}

function criarOportunidadeCard(o) {
  const tipoIcons = { vaga: '💼', projeto: '📋', parceria: '🤝' };
  const tipoIcon = tipoIcons[o.tipo] || '📌';
  const tipoLabels = { vaga: 'Vaga', projeto: 'Projeto', parceria: 'Parceria' };
  const statusLabels = { aberta: 'Aberta', preenchida: '🔒 Preenchida' };

  const tipoLabel = tipoLabels[o.tipo] || o.tipo;
  const skillsHtml = (o.skills_necessarias || []).map(s => `<span class="skill-tag">${s}</span>`).join('');
  const podeFechar = o.status === 'aberta' && o.criador_id === profissionalLogadoId;

  return `
    <div class="oportunidade-card">
      <div class="oportunidade-header">
        <div class="oportunidade-icon">${tipoIcon}</div>
        <h3>${o.titulo}</h3>
        <span class="oportunidade-tipo-badge ${o.tipo}">${tipoLabel}</span>
      </div>
      <div class="oportunidade-body">${o.descricao || ''}</div>
      <div class="oportunidade-skills">${skillsHtml}</div>
      <div class="oportunidade-contato">${o.status === 'aberta' ? `📧 ${o.contato || 'Contato não informado'}` : '🔒 Preenchida'}</div>
      <div class="oportunidade-actions">
        <button class="btn-profile" onclick="verDetalheOportunidade('${o.id}')">Detalhes</button>
        ${podeFechar ? `<button class="btn-connect" onclick="fecharOportunidade('${o.id}')" style="background:var(--red)">🔒 Fechar</button>` : ''}
        <span style="color:var(--text-muted);font-size:12px">${tipoIcon} por ${o.criador_nome || 'Alguém'}</span>
      </div>
    </div>
  `;
}

async function verDetalheOportunidade(oportunidadeId) {
  try {
    const o = await apiFetch(`/api/oportunidades/${oportunidadeId}`);
    const tipoIcons = { vaga: '💼', projeto: '📋', parceria: '🤝' };
    const tipoIcon = tipoIcons[o.tipo] || '📌';
    const tipoLabels = { vaga: 'Vaga', projeto: 'Projeto', parceria: 'Parceria' };
    const statusLabels = { aberta: 'Aberta', preenchida: 'Preenchida' };
    const iniciais = (o.criador_nome || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

    const avatar = o.criador_foto
      ? `<img src="${o.criador_foto}" alt="${o.criador_nome}" />`
      : `<div class="avatar-placeholder">${iniciais}</div>`;

    const body = document.getElementById('oportunidadeDetailBody');
    body.innerHTML = `
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
        <div class="oportunidade-icon" style="width:56px;height:56px;font-size:28px">${tipoIcon}</div>
        <div>
          <h2>${o.titulo}</h2>
          <span class="oportunidade-tipo-badge ${o.tipo}">${tipoLabels[o.tipo]}</span>
          <span style="color:var(--text-muted);font-size:13px;margin-left:8px">${statusLabels[o.status] || o.status}</span>
        </div>
      </div>
      <div class="modal-section">
        <h4>Descrição</h4>
        <p style="color:var(--text-secondary);font-size:15px;line-height:1.7">${o.descricao || 'Sem descrição.'}</p>
      </div>
      <div class="modal-section">
        <h4>Skills desejadas</h4>
        <div class="card-skills">${(o.skills_necessarias || []).map(s => `<span class="skill-tag">${s}</span>`).join('') || '<span style="color:var(--text-muted)">Nenhuma</span>'}</div>
      </div>
      <div class="modal-section">
        <h4>Contato</h4>
        <p style="color:var(--accent);font-size:15px">${o.status === 'aberta' ? (o.contato || 'Não informado') : '🔒 Oportunidade preenchida'}</p>
      </div>
      <div class="modal-section">
        <div style="display:flex;align-items:center;gap:10px">
          <div class="avatar-sm">${avatar}</div>
          <span style="color:var(--text-secondary);font-size:14px">Publicado por <strong>${o.criador_nome || 'Alguém'}</strong></span>
        </div>
      </div>
      <div style="margin-top:12px">
        <button class="btn-profile" onclick="closeModal('oportunidadeDetailModal')">Fechar</button>
        ${o.status === 'aberta' && o.criador_id === profissionalLogadoId ? `<button class="btn-connect" onclick="fecharOportunidade('${o.id}'); closeModal('oportunidadeDetailModal')" style="background:var(--red)">🔒 Marcar como Preenchida</button>` : ''}
      </div>
    `;

    document.getElementById('oportunidadeDetailModal').classList.add('active');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function fecharOportunidade(oportunidadeId) {
  try {
    await apiFetch(`/api/oportunidades/${oportunidadeId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'preenchida' }),
    });
    toast('Oportunidade marcada como preenchida!', 'success');
    carregarOportunidades();
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   REPUTAÇÃO
   ═══════════════════════════════════════════════════════════════════════ */

async function verReputacao(profissionalId) {
  try {
    const r = await apiFetch(`/api/profissionais/${profissionalId}/reputacao`);
    const scoreClass = r.score_contribuicao >= 50 ? 'high' : (r.score_contribuicao >= 20 ? 'medium' : 'low');
    const breakdownLabels = {
      match_aceito: 'Matches aceitos (+10 cada)',
      participou_desafio: 'Participou de desafios (+15 cada)',
      mentor_concluido: 'Mentorias concluídas como mentor (+25 cada)',
      mentorado_concluido: 'Mentorias concluídas como mentorado (+10 cada)',
      criou_oportunidade: 'Oportunidades criadas (+5 cada)',
    };

    const breakdownHtml = Object.entries(r.breakdown)
      .filter(([_, val]) => val > 0)
      .map(([key, val]) => {
        const label = breakdownLabels[key] || key;
        return `<div class="breakdown-item"><span>${label}</span><span class="breakdown-value">+${val}</span></div>`;
      }).join('') || '<p style="color:var(--text-muted);text-align:center">Nenhuma contribuição registrada ainda.</p>';

    const body = document.getElementById('reputacaoModalBody');
    body.innerHTML = `
      <div style="text-align:center;margin-bottom:24px">
        <div style="font-size:48px;margin-bottom:8px">🏆</div>
        <h2>Score de Contribuição</h2>
        <div style="font-size:40px;font-weight:800;color:var(--accent);margin:12px 0">${r.score_contribuicao}</div>
        <span class="reputation-score ${scoreClass}" style="font-size:14px">${r.score_contribuicao >= 50 ? '🌟 Destaque' : (r.score_contribuicao >= 20 ? '📈 Ativo' : '🌱 Iniciante')}</span>
      </div>
      <div class="modal-section">
        <h4>Detalhamento</h4>
        <div class="breakdown-list">${breakdownHtml}</div>
      </div>
      <div style="margin-top:16px;text-align:center">
        <p style="color:var(--text-muted);font-size:13px">
          Participe de mentorias, desafios e publique oportunidades para aumentar seu score!
        </p>
      </div>
      <button class="btn-primary" onclick="closeModal('reputacaoModal')">Fechar</button>
    `;

    document.getElementById('reputacaoModal').classList.add('active');
  } catch (e) {
    toast(e.message, 'error');
  }
}