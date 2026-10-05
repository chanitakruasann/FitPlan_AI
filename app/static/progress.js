const thDate = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });
const kg = (n) => (n == null ? '–' : `${n.toFixed(1)}`);

function renderNow(p) {
  const w = p.this_week;
  const fig = (label, value) => el('div', {}, el('dt', { textContent: label }), el('dd', { textContent: value }));
  $('now').replaceChildren(
    fig('ทำตามแผนสัปดาห์นี้', `${w.done_planned_days}/${w.planned_days} วัน`),
    fig('ทำตามแผนต่อเนื่อง', `${p.streak} วัน`),
    fig('แคลที่เผาสัปดาห์นี้', fmt(w.kcal)),
    fig('เวลาออกกำลังกาย', `${fmt(w.minutes)} นาที`),
  );
}

// กราฟเส้นน้ำหนักแบบเรียบง่าย (SVG)
function renderChart(weeks) {
  const pts = weeks.map((w, i) => ({ i, w: w.weight_kg, label: thDate(w.week_start) })).filter((p) => p.w != null);
  const box = $('chart');
  if (pts.length < 2) {
    box.replaceChildren(el('p', { className: 'empty first', textContent: 'บันทึกน้ำหนักอย่างน้อย 2 สัปดาห์ แล้วกราฟจะขึ้นที่นี่' }));
    return;
  }
  const W = 640, H = 220, padX = 40, padY = 28;
  const min = Math.min(...pts.map((p) => p.w)) - 0.5, max = Math.max(...pts.map((p) => p.w)) + 0.5;
  const x = (i) => padX + (i / (weeks.length - 1)) * (W - padX * 2);
  const y = (v) => padY + (1 - (v - min) / (max - min)) * (H - padY * 2);
  const ns = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs) => { const n = document.createElementNS(ns, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); return n; };
  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': `น้ำหนัก ${pts.map((p) => `${p.label} ${p.w} กก.`).join(', ')}` });
  svg.append(svgEl('polyline', { points: pts.map((p) => `${x(p.i)},${y(p.w)}`).join(' '), class: 'line' }));
  for (const p of pts) {
    svg.append(svgEl('circle', { cx: x(p.i), cy: y(p.w), r: 4, class: 'pt' }));
    const t = svgEl('text', { x: x(p.i), y: y(p.w) - 10, class: 'val' }); t.textContent = p.w.toFixed(1); svg.append(t);
  }
  weeks.forEach((w, i) => { const t = svgEl('text', { x: x(i), y: H - 6, class: 'axis' }); t.textContent = thDate(w.week_start); svg.append(t); });
  const first = pts[0].w, last = pts[pts.length - 1].w, diff = last - first;
  const summary = diff === 0 ? 'น้ำหนักเท่าเดิม' : `${diff < 0 ? 'ลดลง' : 'เพิ่มขึ้น'} ${Math.abs(diff).toFixed(1)} กก. (${pts.map((p) => p.w.toFixed(1)).join(' → ')})`;
  box.replaceChildren(el('p', { className: 'chart-summary', textContent: summary }), svg);
}

function renderTable(weeks) {
  $('weeks').replaceChildren(...[...weeks].reverse().map((w) => el('tr', {},
    el('td', { textContent: thDate(w.week_start) }),
    el('td', { textContent: w.weight_kg != null ? `${kg(w.weight_kg)} กก.` : '–' }),
    el('td', { textContent: w.waist_cm != null ? `${w.waist_cm} ซม.` : '–' }),
    el('td', { textContent: w.planned_days ? `${w.done_planned_days}/${w.planned_days}${w.adherence != null ? ` (${w.adherence}%)` : ''}` : '–' }),
    el('td', { textContent: `${w.exercise_days} วัน` }),
    el('td', { textContent: fmt(w.minutes) }),
    el('td', { textContent: fmt(w.kcal) }))));
}

async function load() {
  const p = await api('/api/progress');
  renderNow(p);
  renderChart(p.weeks);
  renderTable(p.weeks);
  const w = p.this_week;
  if (w.waist_cm != null) document.querySelector('[name=waist_cm]').value = w.waist_cm;
}

$('checkin').addEventListener('submit', (e) => {
  e.preventDefault();
  const fd = new FormData(e.currentTarget);
  const body = { weight_kg: Number(fd.get('weight_kg')), waist_cm: fd.get('waist_cm') ? Number(fd.get('waist_cm')) : null };
  busy(e.submitter, 'กำลังบันทึก…', async () => {
    try {
      const r = await api('/api/checkin', { method: 'POST', body: JSON.stringify(body) });
      toast(`บันทึกแล้ว แคลอรี่ต่อวันใหม่ ${fmt(r.daily_kcal_target)} แคล`);
      await load();
    } catch (err) { toast(err.message, 'error'); }
  });
});

$('insight-btn').addEventListener('click', (e) => {
  showError('insight-error');
  busy(e.currentTarget, 'AI กำลังดูข้อมูล…', async () => {
    try {
      const r = await api('/api/progress/insight', { method: 'POST' });
      $('insight-overview').textContent = r.overview;
      $('insight-list').replaceChildren(...r.suggestions.map((s) => el('li', { textContent: s })));
      $('insight').hidden = false;
    } catch (err) { showError('insight-error', err); }
  });
});

load();
