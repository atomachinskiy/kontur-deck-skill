---
name: kontur-deck
description: Создание презентаций в фирменном стиле СКБ Контур («Экосистема Контур», Montserrat, dark/light). Use when the user asks to build/design a presentation "для Контура", "в стиле Контура", "по брендбуку Контура", deck/слайды for Kontur, or references the Kontur template/brandbook.
---

# Kontur Deck — презентации в стиле Контура

Скилл-«рельсы»: качество деки обеспечивается процессом, а не талантом модели.
Собрано из официальных шаблонов «Экосистема Контур_16x9_Montserrat» + брендбука,
обкатано на 140+ боевых слайдах (стратсессия УМ и хакатон, июль 2026; дека «Вопрос №3 КСР»).

**Не начинай верстать, пока не прочитал:** `DESIGN-RULES.md` (принципы) и
`templates.html` (28 готовых шаблонов слайдов с лимитами знаков).

## Шаг 0. Выбери output (или спроси заказчика)

| Output | Когда | Путь |
|---|---|---|
| **HTML → PNG/PDF** | файл-артефакт, максимум контроля типографики, не редактируется получателем | этот файл, раздел «Пайплайн HTML» |
| **Google Slides** | дека уйдёт людям на совместную правку, нужна гугловая ссылка | `google-slides/GOOGLE-SLIDES.md` + библиотека `kontur_slides.py` |
| **Оба** | сначала HTML-дека как источник истины и PDF, затем порт в GSlides | HTML-пайплайн → порт по GOOGLE-SLIDES.md |
| **Native PPTX** | просят именно .pptx по официальному шаблону | скачанные `dark.pptx`/`light.pptx`, python-pptx |

Если дека будет жить и правиться людьми (рабочие сессии, столы) — почти всегда Google Slides.
Если это отчёт/материал «на посмотреть» — HTML→PDF.

## Пайплайн HTML → PNG/PDF (ОБЯЗАТЕЛЬНЫЙ ЦИКЛ, шаги не пропускать)

1. **Контент-план до вёрстки.** Таблица: слайд → шаблон из templates.html →
   заголовок-вывод → контент по зонам. Проверь лимиты знаков прямо в плане.
   Гейт: у каждого слайда одна мысль; заголовки читаются связным рассказом.
2. **Каркас.** Скопируй в рабочую папку `kontur-deck.css` и `render.js` из скилла.
   Дека = слайды, СКОПИРОВАННЫЕ из `templates.html`, с заменённым контентом.
   Не изобретай layout: нет подходящего шаблона = контент неправильно порезан.
3. **Рендер + линт.** `node render.js deck.html "Имя деки.pdf"`
   (на маке: `NODE_PATH=/Users/andrej/node_modules node render.js ...`).
   Линтер ловит: overflow, кегль <15px, длинные тире, стены списков,
   плейсхолдеры, разъехавшуюся нарезку PDF. Гейт: exit code 0.
4. **Смотри PNG глазами.** Каждый файл из `render/` — через Read. Ищи то, что
   линтер не видит: кривые переносы, сироты, визуальный дисбаланс, слипание.
   Гейт: ноль визуальных дефектов. Нашёл — правь HTML и вернись к шагу 3.
5. **Финальный чек-лист** из DESIGN-RULES.md (раздел «Перед отдачей»).
   Только после него отдавай файл.

Правило остановки: если после 3 итераций слайд всё ещё переполнен — проблема
в контенте, а не вёрстке. Вернись к шагу 1 и порежь текст или раздели слайд.

## Пайплайн Google Slides

Полная механика в `google-slides/GOOGLE-SLIDES.md`. Кратко:
1. Тот же контент-план (шаг 1 выше) — шаблоны один в один повторены методами
   класса `Deck` в `kontur_slides.py` (title_slide, divider, thesis, big_numbers,
   six_numbers, cards, bullets, two_columns, table, timeline, quote, bar_chart, final,
   mega, stairs, org, cover_art, final_art, pills, grid_panel, divider_full, speaker).
2. Один `presentations.batchUpdate` на всю деку; координаты 720×405 pt (px × 0.45).
3. **QA обязателен:** `deck.qa_thumbnails(dir)` → смотреть каждую миниатюру глазами
   (переносы, обрезки за x=690, наезды) → точечные фиксы → повторный QA.
4. Шаринг и передача ссылки. Дека редактируемая: не перезаписывай чужие правки
   при последующих апдейтах (сначала свежий `presentations.get`).

## Дизайн-токены (из .pptx, точно)

- **Формат:** 16:9; HTML-холст 1600×900.
- **Шрифт:** Montserrat — Regular 400 (текст), Medium 500, SemiBold 600 (заголовки).
  Fallback Arial. В GSlides задавать через `weightedFontFamily`, не `bold`.
- **Нейтральная база:** Dark фон `#1C1C22`, блок `#34353F`; Light фон `#FFFFFF`,
  блок `#F1F1F1`; текст `#FEFFFE`/`#000000`; вторичный `#9E9E9E`; серые `#595959`, `#4C4C4C`.
- **Акценты:** Purple `#844BEC` (основной), Teal `#00BEA2`, Orange `#FC7630`,
  Blue `#366AF3`, Light blue `#2291FF`, Magenta `#B850CF`, Plum `#6B1D45`
  (тёмный фон финала/дивайдеров), Red `#FF0000` (только ошибка/предупреждение).
- Машиночитаемо: `tokens.json`.

## Файлы скилла

| Файл | Что |
|---|---|
| `DESIGN-RULES.md` | Дизайн-принципы и антипаттерны — читать до вёрстки |
| `templates.html` | 28 эталонных шаблонов слайдов с лимитами знаков |
| `kontur-deck.css` | Канонический CSS: токены, типографика, layout-классы, @media print |
| `render.js` | Рендер + детерминированный линтер + PNG + PDF с проверкой нарезки |
| `tokens.json` | Токены машиночитаемо |
| `google-slides/GOOGLE-SLIDES.md` | Ветка нативных Google Slides: координаты, batchUpdate, QA |
| `google-slides/kontur_slides.py` | Библиотека макетов для Slides API (класс Deck) |
| `google-slides/make_catalog.py` | Живой каталог всех макетов = регресс-тест библиотеки |

## Источники (авторитетные)

- **Шаблоны PPTX** (56 слайдов, ~24 макета): Google Drive `1_vtUOu-0sUsbqaJ0gG4D1W9urNq_xTGo`;
  Dark `1XUP8KO-wTZsYf0RAbeEHtLfBmvRIBjzB`, Light `1S2AvEp1uKwFKn6hLkabWYU5jKAEQ7b-R`.
  Локально: `~/claude5-workspace/kontur-deck-guide/src/{dark,light}.pptx` (на claude5),
  контактные листы `{dark,light}_contact.png` там же.
- **Брендбук** (SPA, JS-рендер — открывать Playwright'ом): https://in.kontur.ru/brandbook
- **Иконки продуктов:** `https://s.kontur.ru/common-v2/icons-products/{product}/{product}-{size}.svg`;
  лого: `https://s.kontur.ru/common-v2/logos/v2/{product}/{product}-32@2x.png`.
  Гайд: https://guides.kontur.ru/re/sources/icons-products/ Новые — brandbook@kontur.ru.
- **Вордмарк «Контур» (SVG)** инлайнится в шаблонах s-cover из
  `~/.claude/skills/kontur-web/logos/svg/Kontur.svg` (fill заменить на currentColor).
- **Арт-панели обложки/финала (PNG 620×844)** для GSlides-пути хостятся постоянно:
  `https://kontur.ideafromai.ru/deck-assets/art-{cover,final}.png` (Jino, ssh jino-vps,
  docroot `/home/ubuntu/sites/kontur.ideafromai.ru/`).

## Гочи

- Тема `theme1` в .pptx = дефолтная Office (НЕ бренд). Реальная палитра в `theme2`/`theme4`.
- **Montserrat на серверах не установлен** → HTML-путь тянет его из Google Fonts при
  рендере (нужна сеть); soffice-рендер PPTX подставит шрифт (ок для QA структуры).
- `page.pdf` использует print media: блок `@media print` в kontur-deck.css обязателен,
  иначе нарезка уезжает (Pages = slides + 1). render.js это проверяет через pdfinfo.
- Файлы шаблонов ~39 МБ — не коммитить в лёгкие репозитории.
- ⚠️ Без длинных тире на слайдах (правило Андрея) — линтер валит сборку.
