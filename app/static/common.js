// ตัวช่วยที่ใช้ร่วมกันทุกหน้า
const fmt = (n) => Math.round(n).toLocaleString('th-TH');
const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};
const span = (className, textContent) => el('span', { className, textContent });

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (res.status === 401) { location.href = '/login'; return; }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail : 'ข้อมูลไม่ถูกต้อง ลองตรวจอีกครั้ง';
    throw Object.assign(new Error(msg), { status: res.status });
  }
  return data;
}

let toastTimer;
function toast(message, kind = 'ok') {
  const t = $('toast');
  t.textContent = message;
  t.dataset.kind = kind;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

// ปุ่มที่กำลังรอผล: ปิดปุ่ม เปลี่ยนข้อความ แล้วคืนค่าเดิมเมื่อเสร็จ
async function busy(btn, label, fn) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.classList.add('is-busy');
  btn.textContent = label;
  try { return await fn(); }
  finally {
    btn.disabled = false;
    btn.classList.remove('is-busy');
    btn.textContent = original;
  }
}

function showError(id, err) {
  const box = $(id);
  if (!err) { box.hidden = true; return; }
  box.textContent = err.message || err;
  box.hidden = false;
}

// ---------- ส่วนแสดงผลที่ใช้หลายหน้า ----------

const INTENSITY = { low: 'เบา', moderate: 'ปานกลาง', high: 'หนัก' };
const DAY_NAMES = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์'];

function intensityBadge(level) {
  if (!level) return '';
  return el('span', { className: `intensity ${level}`, textContent: `ความหนัก${INTENSITY[level]}` });
}

function amountText(e) {
  return e.reps ? `${e.sets} เซต × ${e.reps} ครั้ง` : `${e.sets} เซต × ${e.seconds} วินาที`;
}

// รายการท่าพร้อมเซต/ครั้ง/เวลาพัก/คำแนะนำ (เรียงตามลำดับที่ควรทำ)
function exerciseList(exercises) {
  return el('ol', { className: 'exercises' }, ...exercises.map((e) => el('li', {},
    el('div', { className: 'ex-main' },
      el('span', { className: 'ex-name' }, e.name, el('span', { className: 'ex-en', textContent: ` ${e.en}` })),
      span('ex-amount', amountText(e))),
    span('ex-cue', `${e.cue} พักระหว่างเซต ${e.rest_sec} วินาที`))));
}

function metaLine(...parts) {
  return el('p', { className: 'meta-line' }, ...parts.filter(Boolean).flatMap((p, i) => (i ? [' ', p] : [p])));
}
