let currentFood = null;
let currentClip = null;
let lastGen = null;

// ---------- ส่วนบน: แคลอรี่ ----------

function renderLog(list, items, cells, deleteUrl, labelOf) {
  list.replaceChildren(...items.map((item) => {
    const del = el('button', { type: 'button', className: 'link-btn', textContent: 'ลบ' });
    del.setAttribute('aria-label', `ลบ ${labelOf(item)}`);
    del.addEventListener('click', async () => {
      del.disabled = true;
      await api(deleteUrl(item), { method: 'DELETE' });
      toast(`ลบ ${labelOf(item)} แล้ว`);
      loadToday();
    });
    return el('li', {}, ...cells(item), del);
  }));
}

function renderCalories(t) {
  const budget = t.target + t.burned;
  const over = t.remaining < 0;
  $('remaining-label').textContent = over ? 'กินเกินไปแล้ว' : 'เหลือกินได้อีก';
  $('remaining-num').textContent = fmt(Math.abs(t.remaining));
  document.querySelector('.today').classList.toggle('over', over);
  $('balance').setAttribute('aria-label', `กินแล้ว ${fmt(t.eaten)} จาก ${fmt(budget)} แคล`);
  $('bar-eaten').style.width = `${Math.min(100, (t.eaten / budget) * 100)}%`;
  $('bar-burned').style.width = over ? '0%' : `${(t.burned / budget) * 100}%`;
  $('fig-target').textContent = fmt(t.target);
  $('fig-eaten').textContent = fmt(t.eaten);
  $('fig-burned').textContent = fmt(t.burned);
  $('streak').hidden = !t.streak;
  $('streak').textContent = `ทำตามแผนต่อเนื่อง ${t.streak} วัน`;
}

// ---------- วันนี้ควรออกอะไร ----------

function sessionBlock(s, single) {
  const head = el('div', { className: 'session-head' }, el('h3', { textContent: s.title }));
  if (!single) head.append(metaLine(`${fmt(s.minutes)} นาที`, `ประมาณ ${fmt(s.kcal)} แคล`, intensityBadge(s.intensity)));
  const box = el('div', { className: 'session' }, head);
  if (s.muscle_text) box.append(el('p', { className: 'meta', textContent: `กล้ามเนื้อ: ${s.muscle_text}` }));
  if (s.kind === 'program') {
    box.append(el('p', { className: 'meta', textContent: `รูปแบบ: ${s.style}` }), exerciseList(s.exercises));
  } else {
    if (s.exercise_names.length) box.append(el('p', { className: 'meta', textContent: `ท่าในคลิป: ${s.exercise_names.join(', ')}` }));
    box.append(el('a', { className: 'btn btn-outline btn-start', href: s.url, target: '_blank', rel: 'noopener', textContent: 'เริ่มออกกำลังกาย (เปิดคลิป)' }));
  }
  return box;
}

function renderPlan(t) {
  const box = $('plan');
  const p = t.plan;
  $('plan-heading').textContent = `วันนี้ วัน${t.day_name}`;
  if (!p) {
    box.replaceChildren(el('p', { className: 'empty first', textContent: 'วันนี้เป็นวันพักตามตาราง ถ้าอยากขยับ ลองเลือกส่วนที่อยากฝึกด้านล่าง' }));
    return;
  }
  const groups = p.groups.length ? p.groups.join(' + ') : 'ออกกำลังกาย';
  const summary = el('div', { className: 'plan-summary' },
    el('p', { className: 'plan-groups', textContent: groups }),
    metaLine(`รวม ${fmt(p.minutes)} นาที`, `ประมาณ ${fmt(p.kcal)} แคล`, intensityBadge(p.intensity)));

  const actions = el('div', { className: 'actions' });
  if (p.status === 'done') {
    actions.append(span('status done', 'ทำสำเร็จแล้ว'), undoBtn('today'));
  } else if (p.status === 'skipped') {
    actions.append(span('status', 'ข้ามวันนี้แล้ว'), undoBtn('today'));
  } else {
    const done = el('button', { type: 'button', className: 'btn btn-primary', textContent: 'ทำสำเร็จ' });
    const skip = el('button', { type: 'button', className: 'btn btn-outline', textContent: 'ข้ามวันนี้' });
    done.addEventListener('click', () => complete('today', done));
    skip.addEventListener('click', () => skipDay('today', skip));
    actions.append(done, skip);
  }
  box.replaceChildren(summary, ...p.sessions.map((s) => sessionBlock(s, p.sessions.length === 1)), el('p', { className: 'ask', textContent: 'วันนี้ทำ workout สำเร็จไหม' }), actions);
  box.querySelector('.ask').hidden = Boolean(p.status);
}

function undoBtn(day) {
  const b = el('button', { type: 'button', className: 'link-btn', textContent: 'ยกเลิก' });
  b.addEventListener('click', async () => {
    await api('/api/day/undo', { method: 'POST', body: JSON.stringify({ day }) });
    $('proposal').hidden = true;
    loadToday();
  });
  return b;
}

async function complete(day, btn) {
  await busy(btn, 'กำลังบันทึก…', async () => {
    const r = await api('/api/day/complete', { method: 'POST', body: JSON.stringify({ day }) });
    toast(`เยี่ยม! เผาไปประมาณ ${fmt(r.kcal)} แคล${r.streak > 1 ? ` ทำตามแผนต่อเนื่อง ${r.streak} วัน` : ''}`);
    await loadToday();
  });
}

async function skipDay(day, btn) {
  await busy(btn, 'กำลังคำนวณตารางใหม่…', async () => {
    const p = await api('/api/day/skip', { method: 'POST', body: JSON.stringify({ day }) });
    showProposal(p, day);
    await loadToday();
  });
}

function showProposal(p, day) {
  $('proposal-text').textContent = p.message;
  const actions = $('proposal-actions');
  actions.replaceChildren();
  if (p.best) {
    const yes = el('button', { type: 'button', className: 'btn btn-small', textContent: `ย้ายไปวัน${p.best.day_name}` });
    const no = el('button', { type: 'button', className: 'btn btn-small btn-quiet', textContent: 'ไม่ต้องชดเชย' });
    yes.addEventListener('click', () => busy(yes, 'กำลังย้าย…', async () => {
      const r = await api('/api/reschedule/apply', { method: 'POST', body: JSON.stringify({ from_day: day, to_weekday: p.best.day }) });
      $('proposal').hidden = true;
      toast(`ย้ายไปวัน${r.to_day_name}แล้ว (เฉพาะสัปดาห์นี้)`);
      loadToday();
    }));
    no.addEventListener('click', () => { $('proposal').hidden = true; });
    actions.append(yes, no);
  } else {
    const ok = el('button', { type: 'button', className: 'btn btn-small btn-quiet', textContent: 'รับทราบ' });
    ok.addEventListener('click', () => { $('proposal').hidden = true; });
    actions.append(ok);
  }
  $('proposal').hidden = false;
  $('proposal').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderPending(p) {
  $('pending').hidden = !p;
  if (!p) return;
  const titles = p.sessions.map((s) => s.title).join(', ');
  $('pending-text').textContent = `เมื่อวาน (วัน${p.day_name}) มี ${titles} ในตาราง ได้ทำไหม`;
}

$('pending-done').addEventListener('click', (e) => complete('yesterday', e.currentTarget));
$('pending-skip').addEventListener('click', (e) => skipDay('yesterday', e.currentTarget));

// ---------- โหลดข้อมูลวันนี้ ----------

async function loadToday() {
  const t = await api('/api/today');
  renderCalories(t);
  renderPlan(t);
  renderPending(t.pending);
  renderLog($('food-log'), t.logs, (log) => [
    el('span', { className: 'grow' }, span('name', log.name), span('meta', `${log.servings} หน่วย`)),
    span('num', fmt(log.kcal)),
  ], (log) => `/api/food/log/${log.id}`, (log) => log.name);
  renderLog($('workout-log'), t.workouts, (w) => [
    el('span', { className: 'grow' }, span('name', w.title), span('meta', 'ออกกำลังกายนอกตาราง')),
    span('num burned', `−${fmt(w.kcal)}`),
  ], (w) => `/api/workout/log/${w.id}`, (w) => w.title);
  $('food-empty').hidden = t.logs.length > 0;
}

// ---------- อยากออกส่วนไหนวันนี้ ----------

$('gen-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const fd = new FormData(e.currentTarget);
  const body = { target: fd.get('target'), minutes: Number(fd.get('minutes')) };
  showError('gen-error');
  busy(e.submitter, 'กำลังจัดท่า…', async () => {
    try {
      const w = await api('/api/workout/generate', { method: 'POST', body: JSON.stringify(body) });
      lastGen = body;
      const save = el('button', { type: 'button', className: 'btn btn-primary btn-block', textContent: 'บันทึกว่าทำแล้ว' });
      save.addEventListener('click', () => busy(save, 'กำลังบันทึก…', async () => {
        const r = await api('/api/workout/log-program', { method: 'POST', body: JSON.stringify(lastGen) });
        $('gen-result').hidden = true;
        toast(`บันทึกแล้ว เผาไปประมาณ ${fmt(r.kcal)} แคล`);
        await loadToday();
      }));
      $('gen-result').replaceChildren(
        el('h3', { className: 'gen-title', textContent: w.title }),
        metaLine(`${fmt(w.minutes)} นาที (รวมวอร์มอัปและยืดเหยียด)`, `ประมาณ ${fmt(w.kcal)} แคล`, intensityBadge(w.intensity)),
        el('p', { className: 'meta', textContent: `รูปแบบ: ${w.style}` }),
        ...w.warnings.map((t) => el('p', { className: 'warn-note', textContent: t })),
        exerciseList(w.exercises),
        save);
      $('gen-result').hidden = false;
    } catch (err) { showError('gen-error', err); }
  });
});

// ---------- อาหาร ----------

function showEstimate(food, manualName) {
  currentFood = food;
  $('estimate').hidden = false;
  $('est-servings').value = '1';
  if (food) {
    const conf = { high: 'ค่อนข้างแม่น', medium: 'เป็นค่าประมาณ', low: 'ไม่ค่อยแน่ใจ แก้ตัวเลขเองได้' }[food.confidence];
    const macros = [
      food.protein_g != null && `โปรตีน ${fmt(food.protein_g)} ก.`,
      food.carb_g != null && `คาร์บ ${fmt(food.carb_g)} ก.`,
      food.fat_g != null && `ไขมัน ${fmt(food.fat_g)} ก.`,
    ].filter(Boolean).join(', ');
    $('est-name').textContent = food.name;
    $('est-meta').textContent = `1 หน่วย = ${food.portion}${macros ? ` (${macros})` : ''} ${conf}`;
    $('est-kcal').value = food.kcal;
  } else {
    $('est-name').textContent = manualName;
    $('est-meta').textContent = 'ใส่แคลอรี่ต่อหน่วยเอง เช่น ดูจากฉลาก';
    $('est-kcal').value = '';
    $('est-kcal').focus();
  }
}

$('food-search').addEventListener('submit', (e) => {
  e.preventDefault();
  const name = $('food-name').value.trim();
  if (!name) return;
  showError('food-error');
  busy(e.submitter, 'กำลังประเมิน…', async () => {
    try {
      showEstimate(await api('/api/food/estimate', { method: 'POST', body: JSON.stringify({ name }) }));
    } catch (err) {
      showError('food-error', err);
      if (err.status === 502) showEstimate(null, name); else $('estimate').hidden = true;
    }
  });
});

$('est-save').addEventListener('click', (e) => {
  const kcal = parseFloat($('est-kcal').value);
  if (Number.isNaN(kcal) || kcal < 0) { $('est-kcal').focus(); return; }
  const name = $('est-name').textContent;
  const body = { servings: parseFloat($('est-servings').value), kcal_per_serving: kcal,
                 ...(currentFood ? { food_id: currentFood.id } : { name }) };
  busy(e.currentTarget, 'กำลังบันทึก…', async () => {
    try {
      await api('/api/food/log', { method: 'POST', body: JSON.stringify(body) });
      $('estimate').hidden = true;
      showError('food-error');
      $('food-name').value = '';
      toast(`บันทึก ${name} แล้ว`);
      await loadToday();
    } catch (err) { showError('food-error', err); }
  });
});

// ---------- คลิป ----------

function showClip(v) {
  currentClip = v;
  $('clip-title').textContent = v.title;
  $('clip-title').href = v.url;
  $('clip-kcal').replaceChildren(`เผาประมาณ ${fmt(v.kcal)} แคล `, intensityBadge(v.intensity));
  $('clip-meta').textContent = `ถ้าทำครบทั้งคลิป ยาว ${fmt(v.total_minutes)} นาที คิดจากน้ำหนัก ${$('workout').dataset.weight} กก.`
    + (v.muscle_text ? ` กล้ามเนื้อ: ${v.muscle_text}` : '');
  $('clip-segments').replaceChildren(...v.segments.map((s) => el('li', { className: s.category === 'rest' ? 'rest' : '' },
    span('seg-start', s.start),
    el('div', {}, span('seg-name', s.name), span('seg-cat', [s.label, s.muscle_text].filter(Boolean).join(', '))),
    span('seg-min', `${fmt(s.minutes)} นาที`),
    span('seg-kcal', fmt(s.kcal)))));
  $('clip-portion').value = '1';
  $('clip').hidden = false;
}

$('video-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const url = $('video-url').value.trim();
  if (!url) return;
  showError('video-error');
  $('clip').hidden = true;
  $('video-wait').hidden = false;
  busy(e.submitter, 'กำลังวิเคราะห์…', async () => {
    try { showClip(await api('/api/video/analyze', { method: 'POST', body: JSON.stringify({ url }) })); }
    catch (err) { showError('video-error', err); }
    finally { $('video-wait').hidden = true; }
  });
});

$('clip-save').addEventListener('click', (e) => {
  if (!currentClip) return;
  busy(e.currentTarget, 'กำลังบันทึก…', async () => {
    try {
      const r = await api('/api/workout/log', { method: 'POST',
        body: JSON.stringify({ video_id: currentClip.id, portion: parseFloat($('clip-portion').value) }) });
      $('clip').hidden = true;
      $('video-url').value = '';
      toast(`บันทึกแล้ว เผาไปประมาณ ${fmt(r.kcal)} แคล`);
      await loadToday();
    } catch (err) { showError('video-error', err); }
  });
});

loadToday();
