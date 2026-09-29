'use strict';
const form = document.querySelector('#coa-form');
const query = document.querySelector('#coa-query');
const statusText = document.querySelector('#coa-status');
const results = document.querySelector('#coa-results');
const count = document.querySelector('#coa-count');
const submit = document.querySelector('#coa-submit');
let controller;

document.querySelector('#menu-toggle').addEventListener('click', (event) => {
  const open = document.querySelector('#nav').classList.toggle('open');
  event.currentTarget.setAttribute('aria-expanded', String(open));
  event.currentTarget.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

async function download(record, button) {
  button.disabled = true;
  button.textContent = '준비 중';
  try {
    // Refresh the short-lived link so a long-open results page still works.
    const response = await fetch('/api/coa/lookup?q=' + encodeURIComponent(record.code + '-' + record.lot), {cache: 'no-store', signal: AbortSignal.timeout(20000)});
    if (!response.ok) throw new Error('lookup');
    const data = await response.json();
    const current = data.results.find(item => item.filename === record.filename);
    if (!current || !current.download.startsWith('/api/coa/download/')) throw new Error('missing');
    const file = await fetch(current.download, {cache: 'no-store', signal: AbortSignal.timeout(60000)});
    if (!file.ok || !(file.headers.get('Content-Type') || '').includes('application/pdf')) throw new Error('download');
    const blob = await file.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = current.filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    statusText.textContent = '성적서 다운로드를 시작했습니다.';
  } catch (error) {
    statusText.textContent = '다운로드에 실패했습니다. 잠시 후 다시 시도하거나 성적서를 요청해 주세요.';
  } finally {
    button.disabled = false;
    button.textContent = 'PDF 다운로드';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  controller?.abort();
  controller = new AbortController();
  const active = controller;
  const timeout = setTimeout(() => active.abort(), 20000);
  results.replaceChildren();
  count.textContent = '';
  const value = query.value.trim();
  if (!/^[A-Za-z0-9\s-]{3,80}$/.test(value) || value.replace(/[\s-]/g, '').length < 3) {
    clearTimeout(timeout);
    statusText.textContent = '영문과 숫자로 된 제품코드 또는 LOT 번호를 확인해 주세요.';
    return;
  }
  submit.disabled = true;
  results.setAttribute('aria-busy', 'true');
  statusText.textContent = '성적서를 조회하고 있습니다.';
  try {
    const response = await fetch('/api/coa/lookup?q=' + encodeURIComponent(value), {cache: 'no-store', signal: active.signal});
    if (!response.ok) throw new Error('lookup');
    const data = await response.json();
    count.textContent = data.count + '건';
    statusText.textContent = data.count ? '제품코드와 LOT 번호를 확인해 주세요.' : '일치하는 성적서가 없습니다. 전체 제품코드 또는 LOT 번호를 확인하거나 성적서를 요청해 주세요.';
    for (const record of data.results) {
      const row = element('article', 'coa-result', '');
      const product = element('div', '', '');
      product.append(element('h3', '', record.code), element('p', '', '제조사 원본 · PDF · ' + (record.size / 1024 / 1024).toFixed(1) + ' MB'));
      const lot = element('div', '', '');
      lot.append(element('p', 'lot-label', 'LOT'), element('p', 'lot-value', record.lot));
      const button = element('button', 'coa-download', 'PDF 다운로드');
      button.type = 'button';
      button.setAttribute('aria-label', record.code + ' LOT ' + record.lot + ' PDF 다운로드');
      button.addEventListener('click', () => download(record, button));
      row.append(product, lot, button);
      results.append(row);
    }
  } catch (error) {
    if (controller === active) statusText.textContent = '조회 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.';
  } finally {
    clearTimeout(timeout);
    if (controller === active) {
      submit.disabled = false;
      results.setAttribute('aria-busy', 'false');
    }
  }
});
