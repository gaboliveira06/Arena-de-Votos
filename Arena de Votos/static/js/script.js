let CANDIDATOS = [];
let TOTAL_DUELOS = 903; // total máximo de pares únicos possíveis com 43 vereadores
let csrfToken = "";
let browserFingerprint = "NAO_INFORMADO";

let estado = {
  indiceAtual: 2,
  candidatoEsq: null,
  candidatoDir: null,
  duelosFeitos: 0,
  jaVotou: false,
  bloqueado: false,
};

const elems = {
  imgLeft: document.getElementById("img-left"), imgRight: document.getElementById("img-right"),
  nameLeft: document.getElementById("name-left"), nameRight: document.getElementById("name-right"),
  numLeft: document.getElementById("num-left"), numRight: document.getElementById("num-right"),
  btnLeft: document.getElementById("btn-left"), btnRight: document.getElementById("btn-right"),
  cardLeft: document.getElementById("card-left"), cardRight: document.getElementById("card-right"),
  roundPill: document.getElementById("round-pill"), progFill: document.getElementById("progress-fill"),
  progLabel: document.getElementById("progress-label"), toast: document.getElementById("toast"),
  tyScreen: document.getElementById("ty-screen"), tySub: document.getElementById("ty-sub"),
  stopModal: document.getElementById("stop-modal"), phoneModal: document.getElementById("phone-modal"),
  whatsappInput: document.getElementById("whatsapp-input"),
};

async function criarFingerprint() {
  const bruto = [
    navigator.userAgent,
    navigator.language,
    screen.width + "x" + screen.height,
    screen.colorDepth,
    new Date().getTimezoneOffset(),
    navigator.platform || "",
  ].join("|");

  try {
    const enc = new TextEncoder().encode(bruto);
    const hash = await crypto.subtle.digest("SHA-256", enc);
    return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
  } catch (e) {
    return btoa(bruto).replace(/[^a-zA-Z0-9]/g, "").slice(0, 32) || "NAO_INFORMADO";
  }
}

function candidatoPorNome(nome) {
  return CANDIDATOS.find(c => c.nome === nome) || null;
}

async function inicializar() {
  try {
    browserFingerprint = await criarFingerprint();
    const resp = await fetch("/api/candidatos");
    const dados = await resp.json();
    CANDIDATOS = dados.candidatos;
    TOTAL_DUELOS = dados.total_duelos;

    const inicioResp = await fetch("/api/pesquisa/iniciar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fingerprint: browserFingerprint })
    });
    const inicio = await inicioResp.json();
    csrfToken = inicio.csrf_token || "";

    estado.candidatoEsq = candidatoPorNome(inicio.current_left) || CANDIDATOS[0];
    estado.candidatoDir = candidatoPorNome(inicio.current_right) || CANDIDATOS[1];
    estado.indiceAtual = Number(inicio.next_index || 2);
    estado.duelosFeitos = Number(inicio.duelos_feitos || 0);
    estado.jaVotou = estado.duelosFeitos > 0;
    estado.bloqueado = false;

    renderizarDuelo(true);
    animarCanvas();
  } catch (e) {
    mostrarToast("Erro ao carregar o sistema.");
    console.error(e);
  }
}

function renderizarDuelo(inicial = false) {
  if (!estado.candidatoEsq || !estado.candidatoDir) return;
  atualizarCard("left", estado.candidatoEsq);
  atualizarCard("right", estado.candidatoDir);

  const round = estado.duelosFeitos + 1;
  elems.roundPill.textContent = `DUELO ${round}`;
  const pct = Math.min((estado.duelosFeitos / TOTAL_DUELOS) * 100, 100);
  elems.progFill.style.width = pct + "%";
  elems.progLabel.textContent = `${estado.duelosFeitos} duelos realizados • sem repetir confrontos`;
  habilitarBotoes(true);

  if (inicial) {
    elems.cardLeft.classList.add("anim-enter-left");
    elems.cardRight.classList.add("anim-enter-right");
    setTimeout(() => {
      elems.cardLeft.classList.remove("anim-enter-left");
      elems.cardRight.classList.remove("anim-enter-right");
    }, 600);
  }
}

async function votar(lado) {
  if (estado.bloqueado) return;
  estado.bloqueado = true;

  const vencedor = lado === "left" ? estado.candidatoEsq : estado.candidatoDir;
  const perdedor = lado === "left" ? estado.candidatoDir : estado.candidatoEsq;
  if (!vencedor || !perdedor || vencedor.nome === perdedor.nome) {
    estado.bloqueado = false;
    return;
  }

  habilitarBotoes(false);
  const resposta = await enviarVoto(vencedor.nome, perdedor.nome);
  if (!resposta.ok) {
    estado.bloqueado = false;
    habilitarBotoes(true);
    return;
  }

  estado.jaVotou = true;
  estado.duelosFeitos++;

  const cardVenc = lado === "left" ? elems.cardLeft : elems.cardRight;
  const cardPerd = lado === "left" ? elems.cardRight : elems.cardLeft;
  const exitAnim = lado === "left" ? "anim-exit-right" : "anim-exit-left";

  cardVenc.classList.add("anim-win-pulse");
  cardPerd.classList.add(exitAnim);
  await esperar(500);
  cardVenc.classList.remove("anim-win-pulse");
  cardPerd.classList.remove(exitAnim);

  // O servidor agora é a fonte da verdade da sequência.
  estado.indiceAtual = Number(resposta.next_index || estado.indiceAtual);
  estado.candidatoEsq = candidatoPorNome(resposta.current_left) || vencedor;

  if (!resposta.current_right) {
    elems.progFill.style.width = "100%";
    elems.progLabel.textContent = `${estado.duelosFeitos} duelos realizados • campeão enfrentou todos os adversários possíveis`;
    abrirWhatsapp();
    return;
  }

  estado.candidatoDir = candidatoPorNome(resposta.current_right);

  if (lado === "left") {
    elems.cardRight.classList.add("anim-enter-right");
    setTimeout(() => elems.cardRight.classList.remove("anim-enter-right"), 600);
  } else {
    elems.cardLeft.classList.add("anim-enter-left");
    elems.cardRight.classList.add("anim-enter-right");
    setTimeout(() => {
      elems.cardLeft.classList.remove("anim-enter-left");
      elems.cardRight.classList.remove("anim-enter-right");
    }, 600);
  }

  renderizarDuelo();
  estado.bloqueado = false;
}

function atualizarCard(lado, candidato) {
  const prefix = lado === "left" ? "Left" : "Right";
  elems[`img${prefix}`].src = candidato.img;
  elems[`img${prefix}`].alt = candidato.nome;
  elems[`name${prefix}`].textContent = candidato.nome;
  elems[`num${prefix}`].textContent = `#${candidato.id} • ${candidato.partido}`;
}

async function enviarVoto(candidatoVotado, candidatoAdversario) {
  try {
    const response = await fetch("/votar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({
        candidato_votado: candidatoVotado,
        candidato_adversario: candidatoAdversario,
        fingerprint: browserFingerprint,
      }),
    });

    const dados = await response.json();
    if (!response.ok || !dados.sucesso) {
      mostrarToast(dados.erro || "Erro ao registrar voto.");
      return { ok: false };
    }
    mostrarToast(`✓ Voto em ${candidatoVotado} registrado!`);
    return { ok: true, current_left: dados.current_left, current_right: dados.current_right, next_index: dados.next_index };
  } catch (err) {
    mostrarToast("⚠ Não foi possível contactar o servidor.");
    return { ok: false };
  }
}

function abrirParar() {
  if (!estado.jaVotou) {
    mostrarToast("Vote pelo menos uma vez antes de parar.");
    return;
  }
  elems.stopModal.style.display = "flex";
}
function fecharParar() { elems.stopModal.style.display = "none"; }
function abrirWhatsapp() {
  elems.stopModal.style.display = "none";
  elems.phoneModal.style.display = "flex";
  setTimeout(() => elems.whatsappInput.focus(), 100);
}
function voltarConfirmacao() {
  elems.phoneModal.style.display = "none";
  elems.stopModal.style.display = "flex";
}

function limparWhatsapp(valor) { return (valor || "").replace(/\D/g, ""); }
function whatsappValido(valor) {
  const d = limparWhatsapp(valor);
  const n = d.startsWith("55") && (d.length === 12 || d.length === 13) ? d.slice(2) : d;
  if (!(n.length === 10 || n.length === 11)) return false;
  if (new Set(n).size <= 2) return false;
  const ddd = Number(n.slice(0, 2));
  return ddd >= 11 && ddd <= 99;
}
function ganhadorAtual() { return estado.candidatoEsq; }

async function finalizarPesquisa() {
  const whatsapp = elems.whatsappInput.value;
  if (!whatsappValido(whatsapp)) {
    mostrarToast("Informe um WhatsApp válido com DDD ou finalize sem WhatsApp.");
    return;
  }
  await enviarFinalizacao({ whatsapp, sem_whatsapp: false });
}

async function finalizarSemWhatsapp() {
  await enviarFinalizacao({ whatsapp: "", sem_whatsapp: true });
}

async function enviarFinalizacao({ whatsapp, sem_whatsapp }) {
  const ganhador = ganhadorAtual();
  if (!ganhador) {
    mostrarToast("Não foi possível identificar o ganhador atual.");
    return;
  }
  try {
    const resp = await fetch("/api/pesquisa/finalizar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ whatsapp, sem_whatsapp, ganhador: ganhador.nome, fingerprint: browserFingerprint }),
    });
    const dados = await resp.json();
    if (!resp.ok || !dados.sucesso) {
      mostrarToast(dados.erro || "Erro ao finalizar pesquisa.");
      return;
    }
    elems.phoneModal.style.display = "none";
    const aviso = dados.status === "VALIDO" ? "" : " Registro mantido para auditoria.";
    const contato = dados.whatsapp_informado ? "" : " WhatsApp não informado.";
    elems.tySub.textContent = `Ganhador da sua pesquisa: ${dados.ganhador}.${contato}${aviso}`;
    elems.tyScreen.style.display = "flex";
  } catch (e) {
    mostrarToast("Erro ao salvar a pesquisa.");
  }
}

async function reiniciar() {
  elems.tyScreen.style.display = "none";
  elems.whatsappInput.value = "";
  csrfToken = "";
  await inicializar();
}
function habilitarBotoes(ativo) { elems.btnLeft.disabled = !ativo; elems.btnRight.disabled = !ativo; }
function esperar(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function mostrarToast(msg) {
  elems.toast.textContent = msg;
  elems.toast.classList.add("show");
  setTimeout(() => elems.toast.classList.remove("show"), 3000);
}

function animarCanvas() {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas || canvas.dataset.on) return;
  canvas.dataset.on = "1";
  const ctx = canvas.getContext("2d");
  let W = canvas.width = window.innerWidth;
  let H = canvas.height = window.innerHeight;
  window.addEventListener("resize", () => { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; });
  const particulas = Array.from({ length: 60 }, () => ({
    x: Math.random() * W, y: Math.random() * H,
    r: Math.random() * 1.5 + .3,
    vx: (Math.random() - .5) * .3,
    vy: (Math.random() - .5) * .3,
    alpha: Math.random() * .5 + .1,
  }));
  function tick() {
    ctx.clearRect(0, 0, W, H);
    particulas.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(245,197,24,${p.alpha})`;
      ctx.fill();
    });
    requestAnimationFrame(tick);
  }
  tick();
}

inicializar();
