/* Kontur Deck — канонический рендер + линт.
 *
 * Использование (из папки деки, где лежит html и рядом kontur-deck.css):
 *   node render.js deck.html "Имя итогового файла.pdf"
 *   node render.js deck.html --no-pdf          # только PNG + линт
 *
 * Что делает:
 *   1. Открывает деку в Chromium (1700×1000, deviceScaleFactor 2, ждёт шрифты).
 *   2. ЛИНТ (детерминированный): overflow за границы слайда, кегль < 15px,
 *      длинные тире в тексте, «стены» списков, переполненные строки, остатки
 *      плейсхолдеров {{...}}. Ошибки => exit code 1 (правь и перезапускай).
 *   3. PNG каждого слайда в ./render/slide-NN.png (смотреть глазами обязательно).
 *   4. PDF страница-в-страницу 1600×900 + проверка: страниц == слайдов.
 *
 * Требует playwright в NODE_PATH или node_modules. На маке:
 *   NODE_PATH=/Users/andrej/node_modules node render.js deck.html "Дека.pdf"
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

const args = process.argv.slice(2);
const htmlFile = args.find(a => a.endsWith('.html'));
const pdfName = args.find(a => a.endsWith('.pdf'));
const noPdf = args.includes('--no-pdf');
if (!htmlFile) {
  console.error('Использование: node render.js <deck.html> ["Имя.pdf" | --no-pdf]');
  process.exit(2);
}

(async () => {
  const dir = path.resolve(path.dirname(htmlFile));
  const outdir = path.join(dir, 'render');
  fs.mkdirSync(outdir, { recursive: true });

  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1700, height: 1000 }, deviceScaleFactor: 2 });
  await page.goto('file://' + path.resolve(htmlFile), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500); // дождаться Montserrat

  const slides = page.locator('.slide');
  const n = await slides.count();
  console.log(`Слайдов: ${n}`);

  // ---------- ЛИНТ ----------
  const lint = await page.evaluate(() => {
    const errors = [];
    const warns = [];
    const slideEls = [...document.querySelectorAll('.slide')];

    slideEls.forEach((s, i) => {
      const id = `слайд ${String(i + 1).padStart(2, '0')}`;
      const sr = s.getBoundingClientRect();

      // 1. Overflow: любой видимый элемент за границами слайда
      s.querySelectorAll('*').forEach(el => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return;
        if (r.bottom > sr.bottom + 4 || r.right > sr.right + 4 || r.top < sr.top - 4 || r.left < sr.left - 4) {
          errors.push(`${id}: OVERFLOW <${el.tagName.toLowerCase()} ${String(el.className).slice(0, 40)}> выходит за слайд`);
        }
      });

      // 2. Кегль меньше 15px на элементах с собственным текстом
      s.querySelectorAll('*').forEach(el => {
        const ownText = [...el.childNodes].some(nd => nd.nodeType === 3 && nd.textContent.trim());
        if (!ownText) return;
        const fs = parseFloat(getComputedStyle(el).fontSize);
        if (fs && fs < 15) {
          errors.push(`${id}: КЕГЛЬ ${fs}px < 15px у <${el.tagName.toLowerCase()} ${String(el.className).slice(0, 30)}>`);
        }
      });

      // 3. Длинные тире в видимом тексте (правило: дефис/двоеточие или переписать)
      if ((s.innerText || '').includes('—')) {
        const line = (s.innerText.split('\n').find(l => l.includes('—')) || '').slice(0, 60);
        errors.push(`${id}: ДЛИННОЕ ТИРЕ в тексте: «${line}…»`);
      }

      // 4. Остатки плейсхолдеров
      if (/\{\{|\}\}|LOREM|TODO/i.test(s.innerText || '')) {
        errors.push(`${id}: остался ПЛЕЙСХОЛДЕР ({{...}} / lorem / todo)`);
      }

      // 5. Стены списков: >6 элементов или элемент длиннее 150 знаков
      s.querySelectorAll('ul,ol').forEach(list => {
        const items = list.querySelectorAll('li');
        if (items.length > 6) warns.push(`${id}: список из ${items.length} пунктов, дели на два слайда`);
        items.forEach(li => {
          if (li.innerText.length > 150) warns.push(`${id}: пункт списка ${li.innerText.length} знаков (>150), режь текст`);
        });
      });
      s.querySelectorAll('.s-list .row').forEach(row => {
        if (row.innerText.length > 240) warns.push(`${id}: строка списка ${row.innerText.length} знаков, режь`);
      });
      const listRows = s.querySelectorAll('.s-list .row').length;
      if (listRows > 5) errors.push(`${id}: ${listRows} строк в s-list (макс 5)`);

      // 6. Заголовки-простыни
      const h2 = s.querySelector('h2');
      if (h2 && h2.innerText.length > 70) warns.push(`${id}: h2 ${h2.innerText.length} знаков (>70)`);
      const h1 = s.querySelector('h1');
      if (h1 && h1.innerText.length > 95) warns.push(`${id}: h1 ${h1.innerText.length} знаков (>95)`);
    });

    return { errors: [...new Set(errors)], warns: [...new Set(warns)] };
  });

  if (lint.warns.length) {
    console.log('\n⚠ ПРЕДУПРЕЖДЕНИЯ:');
    lint.warns.forEach(w => console.log('  ' + w));
  }
  if (lint.errors.length) {
    console.log('\n✗ ОШИБКИ ЛИНТА (исправь и перезапусти):');
    lint.errors.forEach(e => console.log('  ' + e));
  } else {
    console.log('✓ линт чистый');
  }

  // ---------- PNG ----------
  for (let i = 0; i < n; i++) {
    await slides.nth(i).screenshot({ path: path.join(outdir, `slide-${String(i + 1).padStart(2, '0')}.png`) });
  }
  console.log(`✓ PNG: ${outdir}/slide-01..${String(n).padStart(2, '0')}.png — ПОСМОТРИ КАЖДЫЙ`);

  // ---------- PDF ----------
  if (!noPdf) {
    const pdfPath = path.join(dir, pdfName || htmlFile.replace(/\.html$/, '.pdf'));
    await page.pdf({
      path: pdfPath,
      width: '1600px', height: '900px', printBackground: true,
      margin: { top: 0, bottom: 0, left: 0, right: 0 },
    });
    let pages = null;
    try {
      const info = execFileSync('pdfinfo', [pdfPath], { encoding: 'utf8' });
      pages = parseInt((info.match(/^Pages:\s+(\d+)/m) || [])[1], 10);
    } catch (e) { /* pdfinfo нет — пропускаем */ }
    if (pages !== null && pages !== n) {
      lint.errors.push(`PDF: страниц ${pages} != слайдов ${n} — нарезка уехала (проверь @media print в css)`);
      console.log(`✗ PDF: страниц ${pages}, слайдов ${n} — НАРЕЗКА УЕХАЛА`);
    } else {
      console.log(`✓ PDF: ${pdfPath}${pages !== null ? ` (${pages} стр.)` : ' (pdfinfo нет, страницы не проверены)'}`);
    }
  }

  await b.close();
  if (lint.errors.length) process.exit(1);
})();
