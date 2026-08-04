#!/usr/bin/env python3
"""kontur_slides — библиотека макетов Контура для Google Slides API.

Собирает деки в фирстиле Контура (тёмная/светлая тема) программно, через
presentations.batchUpdate. Холст 720x405 pt (16:9). Шрифт Montserrat
(есть в Google Fonts, подмен нет): 600 заголовки, 400 текст, 500 подписи.

Использование (см. также make_catalog.py — живой пример на все макеты):

    from kontur_slides import Deck
    d = Deck("Название деки")           # рабочий аккаунт Контура по умолчанию
    d.title_slide(label="...", title="ИИ, агенты\\nи рок-н-ролл", subtitle="...", speaker="...")
    d.thesis(label="...", text="ИИ сильно больше, чем чат", accents=[("больше", Deck.PURPLE)])
    d.big_numbers(label="...", items=[("4", "гипотезы...", Deck.TEAL), ("80%", "задач...", Deck.PURPLE)])
    d.commit()                          # один batchUpdate на всё
    print(d.url)
    d.qa_thumbnails("/tmp/deck-qa")     # скачать миниатюры на визуальную проверку

Правила текста (обязательны): без длинных тире, ёлочки, точек в заголовках нет,
имя и фамилия людей полностью, минимум англицизмов.
"""
import os
import urllib.request

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def _find_token(name):
    """Токен ищем по всем известным локациям: мак/claude5 (~/.claude/skills),
    US-бокс Hermes (~/.hermes/skills)."""
    for base in ("~/.claude/skills/google-slides-skill/tokens",
                 "~/.hermes/skills/google-slides-skill/tokens"):
        p = os.path.expanduser(os.path.join(base, name))
        if os.path.exists(p):
            return p
    return os.path.expanduser(os.path.join("~/.claude/skills/google-slides-skill/tokens", name))

WORK_TOKEN = _find_token("token_a.tomachinsky_skbkontur.ru.json")
PERSONAL_TOKEN = _find_token("token_default.json")


def _hx(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


class Deck:
    # токены Контура (шаблон «Экосистема 2023»)
    BG = "1C1C22"          # тёмный фон
    CARD = "34353F"        # карточка на тёмном
    WHITE = "FEFFFE"
    GREY = "9E9E9E"        # вторичный текст / label
    GREY2 = "C9C9CE"       # светло-серый текст на карточках
    LINE = "595959"
    PURPLE = "844BEC"      # основной акцент
    TEAL = "00BEA2"
    ORANGE = "FC7630"
    BLUE = "366AF3"
    MAGENTA = "B850CF"
    PLUM = "6B1D45"        # тёмный акцентный фон (финал/дивайдер)

    W, H = 720, 405        # холст, pt
    MX = 30                # поле слева/справа

    def __init__(self, title=None, token_path=WORK_TOKEN, presentation_id=None):
        """title — создать новую деку; presentation_id — подключиться к существующей
        (для точечных правок: удалить слайд + пересоздать с at=индекс)."""
        creds = Credentials.from_authorized_user_file(token_path)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            open(token_path, "w").write(creds.to_json())
        self.svc = build("slides", "v1", credentials=creds)
        if presentation_id:
            self.pid = presentation_id
            self._default = None
        else:
            pres = self.svc.presentations().create(body={"title": title}).execute()
            self.pid = pres["presentationId"]
            self._default = pres["slides"][0]["objectId"]
        self.url = f"https://docs.google.com/presentation/d/{self.pid}/edit"
        self.R = []
        self._n = 0
        self._pg = 0

    # ---------- примитивы ----------
    def _uid(self, p):
        # пер-инстансовый неймспейс: без него повторное подключение к деке
        # (presentation_id=...) даст коллизии objectId с прошлых сборок
        if not hasattr(self, "_ns"):
            import uuid
            self._ns = uuid.uuid4().hex[:6]
        self._n += 1
        return f"{p}{self._ns}_{self._n:04d}"

    def slide(self, bg=None, at=None):
        """at — insertionIndex для вставки в конкретную позицию существующей деки."""
        sid = self._uid("sl")
        req = {"objectId": sid, "slideLayoutReference": {"predefinedLayout": "BLANK"}}
        if at is not None:
            req["insertionIndex"] = at
        self.R.append({"createSlide": req})
        self.R.append({"updatePageProperties": {"objectId": sid, "fields": "pageBackgroundFill",
            "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": _hx(bg or self.BG)}}}}}})
        return sid

    def shape(self, sid, x, y, w, h, kind="ROUND_RECTANGLE", fill=None, valign=None):
        oid = self._uid("sh")
        self.R.append({"createShape": {"objectId": oid, "shapeType": kind,
            "elementProperties": {"pageObjectId": sid,
                "size": {"width": {"magnitude": w, "unit": "PT"}, "height": {"magnitude": h, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})
        props, fields = {}, []
        if fill:
            props["shapeBackgroundFill"] = {"solidFill": {"color": {"rgbColor": _hx(fill)}}}
            fields.append("shapeBackgroundFill")
        props["outline"] = {"propertyState": "NOT_RENDERED"}
        fields.append("outline")
        if valign:
            props["contentAlignment"] = valign
            fields.append("contentAlignment")
        self.R.append({"updateShapeProperties": {"objectId": oid, "fields": ",".join(fields), "shapeProperties": props}})
        return oid

    def text(self, sid, x, y, w, h, s, size, color=None, weight=400, align="START",
             valign=None, line_spacing=None, accents=None):
        """accents: [(подстрока, цвет, вес)] выделения внутри строки."""
        color = color or self.WHITE
        oid = self._uid("tx")
        self.R.append({"createShape": {"objectId": oid, "shapeType": "TEXT_BOX",
            "elementProperties": {"pageObjectId": sid,
                "size": {"width": {"magnitude": w, "unit": "PT"}, "height": {"magnitude": h, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})
        if valign:
            self.R.append({"updateShapeProperties": {"objectId": oid, "fields": "contentAlignment",
                "shapeProperties": {"contentAlignment": valign}}})
        self.R.append({"insertText": {"objectId": oid, "text": s}})
        self.R.append({"updateTextStyle": {"objectId": oid, "textRange": {"type": "ALL"},
            "fields": "fontSize,foregroundColor,weightedFontFamily",
            "style": {"fontSize": {"magnitude": size, "unit": "PT"},
                      "foregroundColor": {"opaqueColor": {"rgbColor": _hx(color)}},
                      "weightedFontFamily": {"fontFamily": "Montserrat", "weight": weight}}}})
        para, fields = {"alignment": align}, "alignment"
        if line_spacing:
            para["lineSpacing"] = line_spacing
            fields += ",lineSpacing"
        self.R.append({"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"},
            "fields": fields, "style": para}})
        for sub, c, wgt in (accents or []):
            i = s.find(sub)
            if i < 0:
                continue
            self.R.append({"updateTextStyle": {"objectId": oid,
                "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + len(sub)},
                "fields": "foregroundColor,weightedFontFamily",
                "style": {"foregroundColor": {"opaqueColor": {"rgbColor": _hx(c)}},
                          "weightedFontFamily": {"fontFamily": "Montserrat", "weight": wgt}}}})
        return oid

    def image(self, sid, url, x, y, w, h):
        """PNG/JPEG по публичному URL. SVG API не принимает.
        Лого Контура: https://s.kontur.ru/common-v2/logos/v2/{p}/{p}-32@2x.png (тёмных PNG нет,
        светлое лого класть на белую плашку)."""
        self.R.append({"createImage": {"objectId": self._uid("im"), "url": url,
            "elementProperties": {"pageObjectId": sid,
                "size": {"width": {"magnitude": w, "unit": "PT"}, "height": {"magnitude": h, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})

    def hline(self, sid, x, y, w, weight=1.5, color=None):
        oid = self._uid("ln")
        self.R.append({"createLine": {"objectId": oid, "category": "STRAIGHT",
            "elementProperties": {"pageObjectId": sid,
                "size": {"width": {"magnitude": w, "unit": "PT"}, "height": {"magnitude": 0.5, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})
        self.R.append({"updateLineProperties": {"objectId": oid, "fields": "lineFill,weight",
            "lineProperties": {"lineFill": {"solidFill": {"color": {"rgbColor": _hx(color or self.LINE)}}},
                               "weight": {"magnitude": weight, "unit": "PT"}}}})

    def chrome(self, sid, label, pg=True, dark_bg=True):
        """Служебный слой: label слева, вордмарк справа, номер страницы."""
        wm = self.WHITE if dark_bg else "000000"
        self.text(sid, self.MX, 20, 500, 16, label.upper(), 9, self.GREY, 500)
        self.text(sid, 610, 20, 80, 16, "Контур", 12, wm, 700, align="END")
        if pg:
            self._pg += 1
            self.text(sid, 660, 378, 30, 14, str(self._pg), 8, self.GREY, 500, align="END")

    def heading(self, sid, title, y=55, size=26):
        self.text(sid, self.MX, y, 660, size + 14, title, size, self.WHITE, 600)

    # ---------- макеты (типология шаблона Контура) ----------
    def title_slide(self, label, title, subtitle, speaker):
        """Титул с плюс-декором."""
        s = self.slide()
        self.text(s, self.MX, 20, 560, 16, label.upper(), 9, self.GREY, 500)
        self.text(s, 610, 20, 80, 16, "Контур", 12, self.WHITE, 700, align="END")
        self.text(s, 470, 60, 230, 260, "+", 220, self.PURPLE, 600, align="CENTER")
        self.text(s, 585, 240, 90, 110, "+", 90, self.TEAL, 600, align="CENTER")
        self.text(s, self.MX, 118, 440, 132, title, 44, self.WHITE, 600, line_spacing=105)
        self.text(s, self.MX, 258, 440, 44, subtitle, 15, self.GREY, 400)
        self.text(s, self.MX, 360, 500, 20, speaker, 11, self.GREY2, 500)
        return s

    def divider(self, num, title, bg=None):
        """Раздел: крупная цифра на акцентном фоне."""
        s = self.slide(bg=bg or self.PURPLE)
        self.text(s, 610, 20, 80, 16, "Контур", 12, self.WHITE, 700, align="END")
        self.text(s, self.MX, 105, 320, 150, num, 120, self.WHITE, 600)
        self.text(s, self.MX, 255, 620, 46, title, 28, self.WHITE, 600)
        return s

    def thesis(self, label, text, accents=None, sub=None):
        """Крупный тезис, акцентное слово цветом."""
        s = self.slide()
        self.chrome(s, label)
        acc = [(a, c, 600) for a, c in (accents or [])]
        self.text(s, self.MX, 140, 660, 110, text, 40, self.WHITE, 600, accents=acc, line_spacing=108)
        if sub:
            self.text(s, self.MX, 258, 580, 50, sub, 14, self.GREY, 400)
        return s

    def quote(self, label, text, author):
        """Цитата: ёлочки акцентом, автор с полным именем."""
        s = self.slide()
        self.chrome(s, label)
        self.text(s, self.MX, 70, 90, 90, "«", 84, self.PURPLE, 600)
        self.text(s, self.MX + 4, 165, 620, 120, text, 22, self.WHITE, 500, line_spacing=124)
        self.text(s, self.MX + 4, 320, 500, 22, author, 12, self.GREY, 500)
        return s

    def big_numbers(self, label, items):
        """2 цифры крупно. items: [(число, подпись, цвет)] x2."""
        s = self.slide()
        self.chrome(s, label)
        for i, (num, cap, color) in enumerate(items[:2]):
            x = 60 + i * 330
            self.text(s, x, 90, 290, 140, num, 120, color, 600)
            self.text(s, x, 238, 270, 70, cap, 12.5, self.GREY2, 400, line_spacing=120)
        return s

    def six_numbers(self, label, title, items):
        """6 важных цифр, сетка 3x2. items: [(число, подпись, цвет|None)] x6."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        for i, (num, cap, color) in enumerate(items[:6]):
            x = self.MX + (i % 3) * 224
            y = 120 + (i // 3) * 135
            self.text(s, x, y, 200, 56, num, 44, color or self.WHITE, 600)
            self.text(s, x, y + 58, 196, 48, cap, 10.5, self.GREY, 400, line_spacing=115)
        return s

    def timeline(self, label, title, steps, accent_last=True):
        """Таймлайн. steps: [(имя, подпись)] до 5-6 шагов."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        n = len(steps)
        col_w = (self.W - 2 * (self.MX - 4)) // n
        self.hline(s, 52, 200, self.W - 104, 1.5)
        for i, (name, sub) in enumerate(steps):
            cx = (self.MX - 4) + i * col_w
            c = self.PURPLE if (accent_last and i == n - 1) else self.LINE
            self.shape(s, cx + col_w // 2 - 7, 193, 14, 14, kind="ELLIPSE", fill=c)
            self.text(s, cx, 225, col_w, 36, name, 12.5, self.WHITE, 600, align="CENTER", line_spacing=105)
            self.text(s, cx, 268, col_w, 40, sub, 9.5, self.GREY, 400, align="CENTER")
        return s

    def cards(self, label, title, items):
        """3 карточки с цветным маркером. items: [(заголовок, текст, цвет)] x3."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        n = min(len(items), 3)
        w = (660 - (n - 1) * 16) // n
        for i, (h, p, acc) in enumerate(items[:3]):
            x = self.MX + i * (w + 16)
            self.shape(s, x, 125, w, 210, fill=self.CARD)
            self.shape(s, x + 22, 150, 14, 14, kind="ELLIPSE", fill=acc)
            self.text(s, x + 22, 178, w - 44, 26, h, 17, self.WHITE, 600)
            self.text(s, x + 22, 210, w - 44, 105, p, 11, self.GREY2, 400, line_spacing=118)
        return s

    def bullets(self, label, title, items):
        """Маркированный список: цветные квадраты-маркеры. items: [(текст, цвет|None)]."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        y = 130
        for txt, color in items:
            self.shape(s, self.MX + 2, y + 5, 9, 9, fill=color or self.PURPLE)
            self.text(s, self.MX + 26, y - 3, 620, 34, txt, 13.5, self.GREY2, 400)
            y += 44
        return s

    def two_columns(self, label, title, cols):
        """Заголовок + 2 колонки. cols: [(подзаголовок, текст)] x2."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        for i, (h, p) in enumerate(cols[:2]):
            x = self.MX + i * 340
            self.text(s, x, 130, 320, 26, h, 15, self.WHITE, 600)
            self.text(s, x, 162, 315, 190, p, 11.5, self.GREY2, 400, line_spacing=130)
        return s

    def screenshot(self, label, title, caption, img_url=None, at=None):
        """Заголовок + скриншот на 70-80% площади (или рамка-плейсхолдер).
        Заголовок держи в одну строку (до ~45 знаков на 26 pt) — рамка начинается на y=130."""
        s = self.slide(at=at)
        self.chrome(s, label)
        self.heading(s, title)
        if img_url:
            self.image(s, img_url, 60, 130, 600, 218)
        else:
            self.shape(s, 60, 130, 600, 218, fill=self.CARD)
            self.text(s, 60, 218, 600, 30, "Скриншот продукта · 70-80% площади слайда", 13, self.GREY, 500, align="CENTER")
        self.text(s, 60, 362, 600, 18, caption, 10, self.GREY, 400, align="CENTER")
        return s

    def table(self, label, title, rows, col_widths=None):
        """Таблица. rows[0] = шапка."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        tid = self._uid("tb")
        nr, nc = len(rows), len(rows[0])
        self.R.append({"createTable": {"objectId": tid, "rows": nr, "columns": nc,
            "elementProperties": {"pageObjectId": s,
                "size": {"width": {"magnitude": 660, "unit": "PT"}, "height": {"magnitude": 60 * nr, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": self.MX, "translateY": 125, "unit": "PT"}}}})
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                cell = {"rowIndex": r, "columnIndex": c}
                self.R.append({"insertText": {"objectId": tid, "cellLocation": cell, "text": val}})
                self.R.append({"updateTextStyle": {"objectId": tid, "cellLocation": cell,
                    "textRange": {"type": "ALL"}, "fields": "fontSize,foregroundColor,weightedFontFamily",
                    "style": {"fontSize": {"magnitude": 13 if r == 0 else 12, "unit": "PT"},
                              "foregroundColor": {"opaqueColor": {"rgbColor": _hx(self.WHITE if r == 0 else self.GREY2)}},
                              "weightedFontFamily": {"fontFamily": "Montserrat", "weight": 600 if r == 0 else 400}}}})
                self.R.append({"updateTableCellProperties": {"objectId": tid,
                    "tableRange": {"location": cell, "rowSpan": 1, "columnSpan": 1},
                    "fields": "tableCellBackgroundFill,contentAlignment",
                    "tableCellProperties": {"contentAlignment": "MIDDLE",
                        "tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": _hx(self.CARD if r == 0 else self.BG)}}}}}})
        self.R.append({"updateTableBorderProperties": {"objectId": tid, "borderPosition": "ALL",
            "fields": "tableBorderFill,weight",
            "tableBorderProperties": {"weight": {"magnitude": 1, "unit": "PT"},
                "tableBorderFill": {"solidFill": {"color": {"rgbColor": _hx(self.CARD)}}}}}})
        return s

    def bar_chart(self, label, title, bars, unit=""):
        """Столбики из шейпов (без Sheets). bars: [(подпись, значение, цвет|None)]."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        base_y, max_h = 330, 175
        vmax = max(v for _, v, _ in bars)
        n = len(bars)
        slot = 660 // n
        bw = min(72, slot - 40)
        for i, (cap, v, color) in enumerate(bars):
            h = max(10, int(max_h * v / vmax))
            x = self.MX + i * slot + (slot - bw) // 2
            self.shape(s, x, base_y - h, bw, h, kind="RECTANGLE", fill=color or self.CARD)
            self.text(s, x - 20, base_y - h - 24, bw + 40, 20, f"{v}{unit}", 13, self.WHITE, 600, align="CENTER")
            self.text(s, x - 24, base_y + 10, bw + 48, 30, cap, 9.5, self.GREY, 400, align="CENTER")
        self.hline(s, self.MX, base_y, 660, 1, self.LINE)
        return s

    def final(self, contact):
        """Финал на сливовом фоне."""
        s = self.slide(bg=self.PLUM)
        self.text(s, 610, 20, 80, 16, "Контур", 12, self.WHITE, 700, align="END")
        self.text(s, self.MX, 140, 640, 120, "Есть вопросы?\nДавайте обсудим", 40, self.WHITE, 600, line_spacing=108)
        self.text(s, self.MX, 300, 560, 22, contact, 12, "E3C9D8", 500)
        return s


    def mega(self, label, value, caption="", color=None):
        """Мега-акцент: одна огромная цифра или слово по центру."""
        s = self.slide()
        self.chrome(s, label)
        v = str(value)
        size = 150 if len(v) <= 7 else (96 if len(v) <= 14 else 60)
        self.text(s, 30, 96, 660, 190, v, size, color or self.PURPLE, 600, align="CENTER")
        if caption:
            self.text(s, 110, 300, 500, 54, caption, 14, self.GREY, 400, align="CENTER", line_spacing=120)
        return s

    def stairs(self, label, title, steps, accent_last=True):
        """Лесенка этапов: 3-5 ступеней, высота нарастает. steps: [(имя, подпись)]."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        steps = steps[:5]
        n = max(len(steps), 2)
        base, hmin, hmax = 358, 100, 222
        slot = 660 // n
        for i, (name, cap) in enumerate(steps):
            h = hmin + int((hmax - hmin) * (i / (n - 1)))
            x = self.MX + i * slot
            top = base - h
            accent = accent_last and i == len(steps) - 1
            fill = self.PURPLE if accent else self.CARD
            self.shape(s, x, top, slot - 12, h, kind="RECTANGLE", fill=fill)
            self.text(s, x + 14, top + 10, slot - 40, 22, f"{i + 1:02d}", 15,
                      self.WHITE if accent else self.PURPLE, 600)
            self.text(s, x + 14, top + 36, slot - 40, 42, name, 12.5, self.WHITE, 600, line_spacing=110)
            if cap and h - 96 >= 28:
                self.text(s, x + 14, top + 82, slot - 40, h - 96, cap, 9.5,
                          "D9C9F5" if accent else self.GREY2, 400, line_spacing=115)
        return s

    def org(self, label, title, root, children):
        """Орг-схема: корневая роль сверху, 2-4 ветки вниз.
        root=(имя, подпись); children: [(имя, подпись, цвет|None)]."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        rname, rcap = root
        rw, rh, ry = 280, 58, 116
        rx = (self.W - rw) // 2
        self.shape(s, rx, ry, rw, rh, fill=self.PURPLE)
        self.text(s, rx + 16, ry + 9, rw - 32, 22, rname, 14, self.WHITE, 600)
        if rcap:
            self.text(s, rx + 16, ry + 33, rw - 32, 20, rcap, 9.5, "D9C9F5", 400)
        children = children[:4]
        n = max(len(children), 1)
        slot = 660 // n
        bus_y, cy, ch = 208, 232, 122
        self.shape(s, self.W // 2 - 1, ry + rh, 2, bus_y - ry - rh, kind="RECTANGLE", fill=self.LINE)
        if n > 1:
            first_cx = self.MX + slot // 2
            last_cx = self.MX + (n - 1) * slot + slot // 2
            self.shape(s, first_cx, bus_y, last_cx - first_cx, 2, kind="RECTANGLE", fill=self.LINE)
        for i, (name, cap, color) in enumerate(children):
            cx = self.MX + i * slot + slot // 2
            self.shape(s, cx - 1, bus_y, 2, cy - bus_y, kind="RECTANGLE", fill=self.LINE)
            x = self.MX + i * slot + 8
            w = slot - 16
            self.shape(s, x, cy, w, ch, fill=self.CARD)
            self.shape(s, x + 14, cy + 14, 10, 10, kind="ELLIPSE", fill=color or self.PURPLE)
            self.text(s, x + 14, cy + 32, w - 28, 36, name, 12, self.WHITE, 600, line_spacing=110)
            if cap:
                self.text(s, x + 14, cy + 70, w - 28, ch - 80, cap, 9, self.GREY2, 400, line_spacing=115)
        return s

    # ---------- макеты v3 (дека «Вопрос №3 КСР» + хакатон-формат, 2026-07-17) ----------
    def _blend(self, base, other, t):
        """Смесь цветов (имитация полупрозрачности: у текста в Slides нет alpha)."""
        a, b = _hx(base), _hx(other)
        return "%02X%02X%02X" % tuple(int((a[k] + (b[k] - a[k]) * t) * 255)
                                      for k in ("red", "green", "blue"))

    def chip(self, sid, x, y, text, color=None, ink="FFFFFF"):
        """Чип-лейбл над заголовком: один на слайд, цвет = ведущий акцент.
        Ширина с запасом: у текст-боксов Slides дефолтные внутренние отступы ~14 pt."""
        w = int(34 + len(text) * 5.8)
        self.shape(sid, x, y, w, 17, fill=color or self.PURPLE)
        self.text(sid, x, y + 1, w, 15, text, 8.5, ink, 600, align="CENTER", valign="MIDDLE")
        return w

    def pills(self, label, title, items, sub=None, accents=None):
        """Реестр пилюль 4×N: продукты, команды, регионы. items: [str], 8-16 шт, ≤22 знаков."""
        s = self.slide()
        self.chrome(s, label)
        self.text(s, self.MX, 55, 660, 40, title, 26, self.WHITE, 600,
                  accents=[(a, c, 600) for a, c in (accents or [])])
        if sub:
            self.text(s, self.MX, 92, 620, 16, sub, 11, self.GREY, 400)
        pw, ph, gx, gy = 157, 47, 10.5, 11
        for i, name in enumerate(items[:16]):
            x = self.MX + (i % 4) * (pw + gx)
            y = 126 + (i // 4) * (ph + gy)
            self.shape(s, x, y, pw, ph, fill=self.CARD)
            self.text(s, x + 6, y, pw - 12, ph, name, 11, self.WHITE, 500,
                      align="CENTER", valign="MIDDLE", line_spacing=105)
        return s

    def grid_panel(self, label, title, cards, panel_title, panel_points, panel_color=None):
        """Сетка фактов + акцентная панель: 6 карточек 2×3 слева, вывод справа.
        cards: [(заголовок ≤24, подпись ≤64)] x6; panel_points: [str ≤66] x2-3."""
        s = self.slide()
        self.chrome(s, label)
        self.heading(s, title)
        cw, ch = 218, 76
        for i, (b, sp) in enumerate(cards[:6]):
            x = self.MX + (i % 2) * (cw + 12)
            y = 112 + (i // 2) * (ch + 10)
            self.shape(s, x, y, cw, ch, fill=self.CARD)
            self.text(s, x + 13, y + 10, cw - 26, 16, b, 11.5, self.WHITE, 600)
            self.text(s, x + 13, y + 30, cw - 26, 40, sp, 9, self.GREY, 400, line_spacing=112)
        self.shape(s, 490, 112, 200, 248, fill=panel_color or self.PURPLE)
        self.text(s, 506, 126, 168, 20, panel_title, 13.5, self.WHITE, 600)
        y = 155
        for pt in panel_points[:3]:
            self.shape(s, 506, y + 7, 5, 5, fill=self.WHITE)
            self.text(s, 518, y, 158, 46, pt, 10, self.WHITE, 400, line_spacing=118)
            y += 54
        return s

    def divider_full(self, num, chip_text, title, sub=None, bg=None, dark_ink=False):
        """Полноцветный дивайдер (хакатон-формат): фон = акцент, гигантский
        полупрозрачный номер справа-сверху, чип и заголовок снизу-слева.
        dark_ink=True для светлых акцентов (teal/orange)."""
        bg = bg or self.PURPLE
        s = self.slide(bg=bg)
        ink = "141414" if dark_ink else "FFFFFF"
        self.text(s, 610, 20, 80, 16, "Контур", 12,
                  self._blend(bg, "000000" if dark_ink else "FFFFFF", .5 if dark_ink else .7), 700, align="END")
        ghost = self._blend(bg, "000000" if dark_ink else "FFFFFF", .10 if dark_ink else .16)
        self.text(s, 240, 6, 450, 160, str(num), 150, ghost, 700, align="END")
        chip_bg = self._blend(bg, "000000" if dark_ink else "FFFFFF", .14 if dark_ink else .20)
        self.chip(s, self.MX, 200, chip_text, color=chip_bg, ink=ink)
        self.text(s, self.MX, 230, 620, 88, title, 38, ink, 700, line_spacing=105)
        if sub:
            self.text(s, self.MX, 320, 560, 40, sub, 12.5, ink, 400, line_spacing=120)
        return s

    def cover_art(self, klabel, title, subtitle, art_url=None):
        """Обложка с фирменной арт-панелью справа (референс «Принципы УМ»).
        title с \\n-переносами (2-3 строки). art_url: PNG 620×844 по публичному URL;
        дефолт - постоянный ассет на kontur.ideafromai.ru (см. GOOGLE-SLIDES.md)."""
        s = self.slide()
        self.text(s, 30, 46, 400, 14, klabel.upper(), 9, self.GREY, 500)
        self.text(s, 30, 78, 390, 150, title, 44, self.WHITE, 600, line_spacing=105)
        if subtitle:
            self.text(s, 30, 242, 365, 60, subtitle, 12.5, self.GREY, 400, line_spacing=125)
        self.text(s, 30, 352, 200, 26, "Контур", 20, self.WHITE, 700)
        self.image(s, art_url or "https://kontur.ideafromai.ru/deck-assets/art-cover.png", 428, 13, 279, 379)
        return s

    def final_art(self, title="Спасибо!\nВопросы?", art_url=None):
        """Финал с арт-панелью, пара к cover_art."""
        s = self.slide()
        self.text(s, 30, 60, 390, 120, title, 44, self.WHITE, 600, line_spacing=105)
        self.text(s, 30, 352, 200, 26, "Контур", 20, self.WHITE, 700)
        self.image(s, art_url or "https://kontur.ideafromai.ru/deck-assets/art-final.png", 428, 13, 279, 379)
        return s

    def speaker(self, label, chip_text, name, role, stats, photo_url=None):
        """Спикер: чип + имя + роль слева, 2-4 стат-чипа (первый акцентный), фото справа.
        stats: [(число ≤6, подпись ≤50)]. Фото: публичный URL или серый плейсхолдер."""
        s = self.slide()
        self.text(s, self.MX, 20, 400, 16, label.upper(), 9, self.GREY, 500)
        if photo_url:
            self.image(s, photo_url, 441, 0, 279, 405)
        else:
            self.shape(s, 441, 0, 279, 405, kind="RECTANGLE", fill=self.CARD)
        self.chip(s, self.MX, 56, chip_text)
        self.text(s, self.MX, 88, 395, 40, name, 28, self.WHITE, 600)
        self.text(s, self.MX, 134, 360, 40, role, 11, self.GREY, 400, line_spacing=125)
        for i, (n, l) in enumerate(stats[:4]):
            x = self.MX + (i % 2) * 200
            y = 240 + (i // 2) * 82
            hot = i == 0
            self.shape(s, x, y, 188, 74, fill=self.PURPLE if hot else self.CARD)
            self.text(s, x + 13, y + 9, 162, 28, n, 24, self.WHITE if hot else self.PURPLE, 600)
            self.text(s, x + 13, y + 44, 162, 24, l, 8.5, "D9C9F5" if hot else self.GREY, 400, line_spacing=112)
        return s

    # ---------- запуск ----------
    def commit(self):
        if self._default:
            self.R.append({"deleteObject": {"objectId": self._default}})
            self._default = None
        self.svc.presentations().batchUpdate(presentationId=self.pid, body={"requests": self.R}).execute()
        self.R = []

    def delete_slide(self, index):
        """Удалить слайд по индексу (0-based) в существующей деке."""
        pres = self.svc.presentations().get(presentationId=self.pid).execute()
        self.R.append({"deleteObject": {"objectId": pres["slides"][index]["objectId"]}})

    def qa_thumbnails(self, outdir):
        """Скачать миниатюры всех слайдов: обязательный визуальный QA перед отправкой."""
        os.makedirs(outdir, exist_ok=True)
        pres = self.svc.presentations().get(presentationId=self.pid).execute()
        paths = []
        for i, sl in enumerate(pres["slides"], 1):
            t = self.svc.presentations().pages().getThumbnail(
                presentationId=self.pid, pageObjectId=sl["objectId"],
                thumbnailProperties_thumbnailSize="LARGE").execute()
            p = os.path.join(outdir, f"slide-{i:02d}.png")
            urllib.request.urlretrieve(t["contentUrl"], p)
            paths.append(p)
        return paths
