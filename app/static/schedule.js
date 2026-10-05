const todayIndex = (new Date().getDay() + 6) % 7;   // JS: อาทิตย์ = 0 → จันทร์ = 0
let data = null;

function scoreClass(n) { return n >= 80 ? 'good' : n >= 60 ? 'ok' : 'low'; }

function renderAnalysis() {
  const { score, totals: t, findings } = data;
  $('context').textContent = `วิเคราะห์ตาม${data.level} เป้าหมาย${data.goal}`;
  $('score').hidden = !score;
  if (score) {
    $('score-num').textContent = score.total;
    $('score').dataset.level = scoreClass(score.total);
    $('parts').replaceChildren(...score.parts.map((p) => {
      const fill = el('div', { className: `fill ${scoreClass(p.score)}` });
      fill.style.width = `${p.score}%`;
      return el('li', {}, span('part-label', p.label), el('div', { className: 'bar' }, fill), span('part-num', `${p.score}%`));
    }));
  }
  const g = t.group_days;
  const stat = (label, value) => el('div', {}, el('dt', { textContent: label }), el('dd', { textContent: value }));
  $('stats').replaceChildren(
    stat('ส่วนล่าง / ส่วนบน / แกนกลาง', `${g.lower} / ${g.upper} / ${g.core} ครั้ง`),
    stat('คาร์ดิโอ (นาทีหนักนับ 2 เท่า)', `${fmt(t.cardio_equivalent_min)} / ${fmt(t.cardio_target)} นาที`),
    stat('วันฝึกกล้ามเนื้อ', `${t.strength_days} / ${t.strength_target} วัน`),
    stat('วันพัก, เผาทั้งสัปดาห์', `${t.rest_days} วัน, ${fmt(t.kcal)} แคล`),
  );
  $('findings').replaceChildren(...findings.map((f) => el('li', { className: f.level },
    el('span', { className: 'mark' }), el('span', { textContent: f.text }))));
  $('advice-btn').disabled = !score;
}

function itemRow(day, it) {
  const del = el('button', { type: 'button', className: 'link-btn', textContent: 'เอาออก' });
  del.setAttribute('aria-label', `เอา ${it.title} ออกจากวัน${day.name}`);
  del.addEventListener('click', async () => {
    del.disabled = true;
    await api(`/api/schedule/item/${it.id}`, { method: 'DELETE' });
    toast(`เอาออกจากวัน${day.name}แล้ว`);
    load();
  });
  const title = it.url
    ? el('a', { href: it.url, target: '_blank', rel: 'noopener', textContent: it.title })
    : el('span', { className: 'item-title', textContent: it.title });
  const info = el('div', { className: 'grow' }, title,
    metaLine(`${fmt(it.minutes)} นาที`, `${fmt(it.kcal)} แคล`, intensityBadge(it.intensity)));
  if (it.muscle_text) info.append(span('meta', it.muscle_text));
  if (it.exercises) {
    info.append(el('details', { className: 'ex-details' },
      el('summary', { textContent: `ดูท่า ${it.exercises.length} ท่า` }), exerciseList(it.exercises)));
  }
  return el('li', {}, info, del);
}

function addControls(day) {
  const select = el('select', {});
  select.setAttribute('aria-label', `เลือกสิ่งที่จะเพิ่มในวัน${day.name}`);
  const progGroup = el('optgroup', { label: `โปรแกรมจัดท่าให้ (${data.program_minutes} นาที)` },
    ...data.programs.map((p) => el('option', { value: `p:${p.key}`, textContent: p.label })));
  select.append(progGroup);
  if (data.library.length) {
    select.append(el('optgroup', { label: 'คลิปในคลัง' },
      ...data.library.map((v) => el('option', { value: `v:${v.id}`, textContent: `${v.title} (${fmt(v.minutes)} นาที, ${INTENSITY[v.intensity]})` }))));
  }
  const add = el('button', { type: 'button', className: 'btn btn-small', textContent: 'เพิ่ม' });
  const cancel = el('button', { type: 'button', className: 'link-btn', textContent: 'ยกเลิก' });
  const toggle = el('button', { type: 'button', className: 'link-btn add-toggle', textContent: '+ เพิ่ม' });
  const row = el('div', { className: 'add-row', hidden: true }, select, add, cancel);
  toggle.addEventListener('click', () => { row.hidden = false; toggle.hidden = true; select.focus(); });
  cancel.addEventListener('click', () => { row.hidden = true; toggle.hidden = false; toggle.focus(); });
  add.addEventListener('click', () => busy(add, 'กำลังเพิ่ม…', async () => {
    const [kind, value] = select.value.split(':');
    const body = { weekday: day.weekday, ...(kind === 'p' ? { program: value } : { video_id: Number(value) }) };
    try {
      await api('/api/schedule/item', { method: 'POST', body: JSON.stringify(body) });
      toast(`เพิ่มลงวัน${day.name}แล้ว`);
      await load();
    } catch (err) { toast(err.message, 'error'); }
  }));
  return [toggle, row];
}

function dayRow(day) {
  const st = day.stats;
  const isToday = day.weekday === todayIndex;
  const tags = el('span', { className: 'tags' });
  if (st.is_high) tags.append(span('tag hard', 'วันหนัก'));
  for (const g of st.groups) tags.append(span('tag', { lower: 'ส่วนล่าง', upper: 'ส่วนบน', core: 'แกนกลาง' }[g]));
  const head = el('div', { className: 'day-head' },
    el('h3', {}, day.name, isToday ? span('today-pill', 'วันนี้') : ''),
    span('day-summary', st.is_rest ? 'วันพัก' : `${fmt(st.active_min)} นาที, ${fmt(st.kcal)} แคล`), tags);

  const items = el('ul', { className: 'day-items' }, ...day.items.map((it) => itemRow(day, it)));
  const controls = el('div', { className: 'day-controls' }, ...addControls(day));
  if (day.items.length) {
    const time = el('input', { type: 'time', value: day.remind_time, step: 60 });
    time.addEventListener('change', async () => {
      if (!time.value) return;
      try {
        await api(`/api/schedule/day/${day.weekday}`, { method: 'PUT', body: JSON.stringify({ remind_time: time.value }) });
        toast(`ตั้งเตือนวัน${day.name} เวลา ${time.value} น. แล้ว`);
      } catch (err) { toast(err.message, 'error'); }
    });
    controls.append(el('label', { className: 'remind' }, 'เตือนทาง LINE', time));
  }
  return el('li', { className: 'day' + (st.is_rest ? ' rest' : '') + (isToday ? ' today' : '') }, head, items, controls);
}

async function load() {
  data = await api('/api/schedule');
  $('line-hint').hidden = data.line_linked || !data.days.some((d) => d.items.length);
  renderAnalysis();
  $('week').replaceChildren(...data.days.map(dayRow));
}

$('advice-btn').addEventListener('click', (e) => {
  showError('advice-error');
  busy(e.currentTarget, 'AI กำลังอ่านตาราง…', async () => {
    try {
      const r = await api('/api/schedule/advice', { method: 'POST' });
      $('advice-overview').textContent = r.overview;
      $('advice-list').replaceChildren(...r.suggestions.map((s) => el('li', { textContent: s })));
      $('advice').hidden = false;
    } catch (err) { showError('advice-error', err); }
  });
});

$('video-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const url = $('video-url').value.trim();
  showError('video-error');
  $('video-status').textContent = 'กำลังดูคลิป คลิปยาวอาจใช้เวลาราวหนึ่งนาที';
  $('video-status').hidden = false;
  busy(e.submitter, 'กำลังวิเคราะห์…', async () => {
    try {
      const v = await api('/api/video/analyze', { method: 'POST', body: JSON.stringify({ url }) });
      $('video-status').textContent = `"${v.title}" อยู่ในคลังแล้ว (${fmt(v.total_minutes)} นาที, ความหนัก${INTENSITY[v.intensity]}) กด "+ เพิ่ม" ในวันที่ต้องการ`;
      $('video-url').value = '';
      await load();
    } catch (err) {
      $('video-status').hidden = true;
      showError('video-error', err);
    }
  });
});

load();
