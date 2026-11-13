'use strict';
const $ = id => document.getElementById(id);
const examples = {
  save: 'Після завантаження збереження персонаж іноді застрягає в текстурах, неможливо рухатися, допомагає лише перезавантаження.',
  crash: 'Після натискання кнопки «Почати гру» застосунок щоразу аварійно завершується. До головного меню повернутися не вдається.',
  ui: 'У меню налаштувань текст підказки перекриває повзунок гучності. Повзунок працює, звук змінюється.'
};
const priorityNames = ['невідкладний', 'високий', 'середній', 'низький', 'мінімальний'];
const severityNames = {1:'критична',2:'значна',3:'помірна',4:'косметична'};
let currentReport = null;
let busy = false;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function render(report) {
  const root = $('report'); root.replaceChildren();
  root.append(node('h3', report.title, 'report-title'));
  const badges = node('div', undefined, 'badges');
  badges.append(node('span', `Пріоритет ${report.priority} · ${priorityNames[report.priority]}`, 'badge priority'),
    node('span', `Серйозність ${report.severity} · ${severityNames[report.severity]}`, 'badge severity'),
    node('span', report.area_path, 'badge'));
  root.append(badges);
  for (const [key, label] of [['description','Опис'],['repro_steps','Кроки відтворення'],['actual_result','Фактичний результат'],['expected_result','Очікуваний результат'],['suggested_fix','Рекомендація щодо виправлення']]) {
    const section = node('section', undefined, `report-section${key === 'suggested_fix' ? ' fix' : ''}`);
    section.append(node('h4', label));
    if (key === 'repro_steps') {
      const list = node('ol'); report[key].forEach(step => list.append(node('li', step))); section.append(list);
    } else section.append(node('p', report[key]));
    root.append(section);
  }
  root.hidden = false; $('actions').hidden = false;
}
function toMarkdown(r) {
  return `# ${r.title}\n\n**Пріоритет:** ${r.priority} — ${priorityNames[r.priority]}\n\n**Серйозність:** ${r.severity} — ${severityNames[r.severity]}\n\n**Шлях області:** ${r.area_path}\n\n## Опис\n\n${r.description}\n\n## Кроки відтворення\n\n${r.repro_steps.map((s,i)=>`${i+1}. ${s}`).join('\n')}\n\n## Фактичний результат\n\n${r.actual_result}\n\n## Очікуваний результат\n\n${r.expected_result}\n\n## Рекомендація щодо виправлення\n\n${r.suggested_fix}\n`;
}
function download(text, extension, mime) {
  const url = URL.createObjectURL(new Blob([text], {type: mime}));
  const anchor = node('a'); anchor.href = url; anchor.download = `bag-report.${extension}`;
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(()=>URL.revokeObjectURL(url), 1000);
}
$('description').addEventListener('input', ()=> { $('counter').textContent = `${$('description').value.length} / 2400`; });
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', ()=> {
  if (busy) return;
  $('description').value = examples[button.dataset.example];
  $('description').dispatchEvent(new Event('input')); $('description').focus();
}));
$('bug-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  const description = $('description').value.trim();
  $('error').hidden = true;
  if (description.length < 12) { $('error').textContent = 'Опишіть баг докладніше: щонайменше 12 символів.'; $('error').hidden = false; return; }
  busy = true; currentReport = null; $('report').hidden = true; $('actions').hidden = true;
  $('empty').hidden = true; $('loading').hidden = false; $('generate').disabled = true;
  $('report-state').textContent = 'ГЕНЕРАЦІЯ'; $('report-state').classList.remove('done');
  $('status').textContent = 'Аналізуємо опис за допомогою локальної моделі…';
  const start = performance.now(); $('elapsed').textContent = '0 с';
  const ticker = setInterval(()=> $('elapsed').textContent = `${Math.floor((performance.now()-start)/1000)} с`, 1000);
  const controller = new AbortController(); const timeout = setTimeout(()=>controller.abort(), 185000);
  try {
    const response = await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({description}), signal:controller.signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Не вдалося сформувати звіт.');
    currentReport = data.report; render(currentReport);
    $('report-state').textContent = 'ГОТОВО ДО ПЕРЕВІРКИ'; $('report-state').classList.add('done');
    $('status').textContent = 'Звіт готовий.';
    $('metrics').textContent = `${data.elapsed_s} с · ${data.usage.completion_tokens ?? '—'} токенів`;
  } catch (error) {
    $('empty').hidden = false; $('error').hidden = false;
    $('error').textContent = error.name === 'AbortError' ? 'Час очікування вичерпано. Перевірте сервер моделі та спробуйте ще раз.' : (error.message === 'Failed to fetch' ? 'Сервер застосунку недоступний. Перевірте його запуск.' : error.message);
    $('report-state').textContent = 'ПОТРІБНА УВАГА'; $('status').textContent = 'Звіт не створено. Усуньте причину й повторіть запит.';
  } finally {clearInterval(ticker);clearTimeout(timeout);busy=false;$('loading').hidden=true;$('generate').disabled=false;}
});
$('json').addEventListener('click', ()=>currentReport && download(JSON.stringify(currentReport,null,2),'json','application/json;charset=utf-8'));
$('markdown').addEventListener('click', ()=>currentReport && download(toMarkdown(currentReport),'md','text/markdown;charset=utf-8'));
$('copy').addEventListener('click', async ()=> {
  if (!currentReport) return;
  try {await navigator.clipboard.writeText(toMarkdown(currentReport));$('status').textContent='Текст звіту скопійовано.';}
  catch {$('status').textContent='Копіювання недоступне. Збережіть звіт як Markdown.';}
});
async function health() {
  try {const response=await fetch('/api/health'); const data=await response.json();$('health').className=`health ${data.ready?'ready':'offline'}`;$('health').lastChild.textContent=data.message;}
  catch {$('health').className='health offline';$('health').lastChild.textContent='Сервер застосунку недоступний';}
}
fetch('/api/config').then(r=>r.json()).then(data=>{$('model-name').textContent=`${data.model} · локальна модель`;}).catch(()=>{});
health();setInterval(health,30000);
