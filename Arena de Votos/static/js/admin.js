const chartData = JSON.parse(document.getElementById('chart-data')?.textContent || '{}');

function makeChart(id, type, labels, data, label) {
  const el = document.getElementById(id);
  if (!el || !window.Chart) return;
  new Chart(el, {
    type,
    data: { labels, datasets: [{ label, data, borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#F0F2FF' } } }, scales: { x: { ticks: { color: '#F0F2FF' }, grid: { color: 'rgba(255,255,255,.06)' } }, y: { ticks: { color: '#F0F2FF' }, grid: { color: 'rgba(255,255,255,.06)' }, beginAtZero: true } } }
  });
}

makeChart('chartEvolucao', 'line', (chartData.evolucao||[]).map(x=>x.data), (chartData.evolucao||[]).map(x=>x.total), 'Pesquisas válidas');
makeChart('chartTop10', 'bar', (chartData.top10||[]).map(x=>x.vereador), (chartData.top10||[]).map(x=>x.pesquisas_ganhas), 'Pesquisas ganhas');
makeChart('chartStatus', 'doughnut', (chartData.status||[]).map(x=>x.status), (chartData.status||[]).map(x=>x.total), 'Status');

document.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(btn.dataset.tab).classList.add('active');
}));

function brDateToISO(v) { if (!v || v === 'None') return ''; const [d,m,y] = v.split('/'); return `${y}-${m}-${d}`; }
function rowText(row) { return (row.dataset.search || row.textContent || '').toLowerCase(); }

function applyPesquisaFilters() {
  const q = (document.getElementById('pesquisaSearch')?.value || '').toLowerCase();
  const status = document.getElementById('statusFilter')?.value || '';
  const ini = document.getElementById('dataInicio')?.value || '';
  const fim = document.getElementById('dataFim')?.value || '';
  document.querySelectorAll('#pesquisasTable tbody tr, #pesquisasIncompletasTable tbody tr').forEach(row => {
    const iso = brDateToISO(row.dataset.date || '');
    const okQ = !q || rowText(row).includes(q);
    const okS = !status || row.dataset.status === status;
    const okI = !ini || iso >= ini;
    const okF = !fim || iso <= fim;
    row.style.display = okQ && okS && okI && okF ? '' : 'none';
  });
}
['pesquisaSearch','statusFilter','dataInicio','dataFim'].forEach(id => document.getElementById(id)?.addEventListener('input', applyPesquisaFilters));
document.getElementById('clearPesquisas')?.addEventListener('click', () => { ['pesquisaSearch','statusFilter','dataInicio','dataFim'].forEach(id => document.getElementById(id).value=''); document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active')); document.querySelector('.filter-btn[data-days="all"]')?.classList.add('active'); applyPesquisaFilters(); });

document.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
  const days = btn.dataset.days;
  const ini = document.getElementById('dataInicio'), fim = document.getElementById('dataFim');
  if (days === 'all') { ini.value=''; fim.value=''; }
  else { const d = new Date(); const f = d.toISOString().slice(0,10); d.setDate(d.getDate() - Number(days)); ini.value = d.toISOString().slice(0,10); fim.value = f; }
  applyPesquisaFilters();
}));

function applyRankingFilters() {
  const q = (document.getElementById('rankingSearch')?.value || '').toLowerCase();
  const metric = document.getElementById('rankingMetric')?.value || 'pesquisas';
  const min = Number(document.getElementById('rankingMin')?.value || 0);
  const tbody = document.querySelector('#rankingTable tbody'); if (!tbody) return;
  const rows = [...tbody.querySelectorAll('tr')];
  rows.sort((a,b) => Number(b.dataset[metric] || 0) - Number(a.dataset[metric] || 0));
  rows.forEach(row => { row.style.display = (!q || row.dataset.name.includes(q)) && Number(row.dataset.total || 0) >= min ? '' : 'none'; tbody.appendChild(row); });
}
['rankingSearch','rankingMetric','rankingMin'].forEach(id => document.getElementById(id)?.addEventListener('input', applyRankingFilters));
document.getElementById('clearRanking')?.addEventListener('click', () => { document.getElementById('rankingSearch').value=''; document.getElementById('rankingMetric').value='pesquisas'; document.getElementById('rankingMin').value='0'; applyRankingFilters(); });

const modal = document.getElementById('detailModal');
const modalBody = document.getElementById('modalBody');
document.getElementById('closeModal')?.addEventListener('click', () => modal.classList.remove('show'));
modal?.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });

document.querySelectorAll('.detail-btn[data-id]').forEach(btn => btn.addEventListener('click', async () => {
  modal.classList.add('show'); modalBody.textContent = 'Carregando...';
  try {
    const resp = await fetch(`/admin/api/pesquisa/${btn.dataset.id}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.erro || 'Erro');
    const p = data.pesquisa;
    modalBody.innerHTML = `<div class="info-grid">
      <div class="info-item"><div class="info-label">ID</div>#${p.id}</div><div class="info-item"><div class="info-label">WhatsApp</div>${p.whatsapp || 'Número não informado'}</div>
      <div class="info-item"><div class="info-label">Ganhador / parcial</div>${p.ganhador || p.current_left || '—'}</div><div class="info-item"><div class="info-label">Status</div><span class="badge ${p.status}">${p.status}</span></div>
      <div class="info-item"><div class="info-label">IP</div><span class="mono">${p.ip || '—'}</span></div><div class="info-item"><div class="info-label">Fingerprint</div><span class="mono">${p.fingerprint || '—'}</span></div>
      <div class="info-item"><div class="info-label">Início</div>${p.data_inicio || ''} ${p.hora_inicio || ''}</div><div class="info-item"><div class="info-label">Fim</div>${p.data_fim || ''} ${p.hora_fim || ''}</div>
      <div class="info-item" style="grid-column:1/-1"><div class="info-label">Motivo</div>${p.motivo_status || '—'}</div>
    </div><h3>Histórico de duelos</h3><div class="duel-list">${(data.duelos||[]).map((d,i)=>`<div class="duel-line"><strong>${i+1}.</strong> ${d.candidato_votado} venceu ${d.candidato_adversario} <span class="muted">(${d.data} ${d.horario})</span></div>`).join('') || '<p class="muted">Nenhum duelo registrado.</p>'}</div>`;
  } catch (e) { modalBody.textContent = 'Erro ao carregar detalhes.'; }
}));


// Preenche as barras de percentual do ranking sem usar CSS inline com Jinja.
document.querySelectorAll('.percent-fill').forEach((bar) => {
  const percent = Number(bar.dataset.percent || 0);
  bar.style.width = `${percent}%`;
});
