"""Renderiza carrossel de Instagram (1080x1350) a partir de um JSON.

Uso: python3 tools/render_carrossel.py conteudo.json pasta_saida/
Fontes esperadas em /tmp/fonts/ (Cormorant Garamond e Inter, do Google Fonts).
Trechos entre *asteriscos* nos títulos saem na cor de acento (dourado).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
M = 96  # margem lateral
NAVY_TOP = (11, 26, 51)
NAVY_BOT = (15, 36, 71)
GOLD = (201, 162, 75)
GOLD_LIGHT = (217, 183, 106)
INK = (243, 238, 227)
INK_SOFT = (243, 238, 227, 185)
AUTHOR = "Ivan Rodrigues"
FEAT = ["lnum"]  # algarismos alinhados (Cormorant usa estilo antigo por padrão)

FONT_DIR = Path("/tmp/fonts")
FONT_FILES = {
    "serif600": "CormorantGaramond-600.ttf",
    "serif700": "CormorantGaramond-700.ttf",
    "sans400": "Inter-400.ttf",
    "sans500": "Inter-500.ttf",
    "sans600": "Inter-600.ttf",
    "sans700": "Inter-700.ttf",
}

CONTENT_TOP = 150      # início da área útil
CONTENT_BOTTOM = 1150  # fim da área útil (acima do rodapé)


def check_fonts():
    missing = [f for f in FONT_FILES.values() if not (FONT_DIR / f).exists()]
    if missing:
        sys.exit("ERRO: fontes premium ausentes em /tmp/fonts: " + ", ".join(missing)
                 + ". Não renderizei com fonte de fallback.")


def font(key, size):
    return ImageFont.truetype(str(FONT_DIR / FONT_FILES[key]), size)


class Canvas:
    """Desenha ou só mede (dry=True), para permitir centralizar o bloco."""

    def __init__(self, img=None):
        self.dry = img is None
        self.d = ImageDraw.Draw(img if img else Image.new("RGBA", (W, H)), "RGBA")

    def tw(self, s, f):
        return self.d.textlength(s, font=f, features=FEAT)

    def text(self, xy, s, f, fill, **kw):
        if not self.dry:
            self.d.text(xy, s, font=f, fill=fill, features=FEAT, **kw)

    def line(self, *a, **kw):
        if not self.dry:
            self.d.line(*a, **kw)

    def rect(self, *a, **kw):
        if not self.dry:
            self.d.rectangle(*a, **kw)

    def rrect(self, *a, **kw):
        if not self.dry:
            self.d.rounded_rectangle(*a, **kw)


def background():
    img = Image.new("RGB", (W, H), NAVY_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    img = img.convert("RGBA")
    ImageDraw.Draw(img, "RGBA").rectangle([36, 36, W - 37, H - 37], outline=GOLD + (90,), width=2)
    return img


def spaced(s):
    return " ".join(s.upper())


def wrap(c, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if c.tw(trial, f) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def paragraph(c, x, y, text, f, maxw, color, lh):
    for ln in wrap(c, text, f, maxw):
        c.text((x, y), ln, f, color)
        y += lh
    return y


def rich_words(text):
    """Cada palavra vira lista de segmentos (texto, destacado?). '*' alterna destaque."""
    words, hi = [], False
    for raw in text.split():
        segs, buf = [], ""
        for ch in raw:
            if ch == "*":
                if buf:
                    segs.append((buf, hi))
                buf, hi = "", not hi
            else:
                buf += ch
        if buf:
            segs.append((buf, hi))
        if segs:
            words.append(segs)
    return words


def rich_title(c, x, y, text, f, maxw, lh):
    words = rich_words(text)
    wlen = lambda segs: sum(c.tw(s, f) for s, _ in segs)
    space = c.tw(" ", f)
    lines, cur, curw = [], [], 0
    for segs in words:
        ww = wlen(segs)
        add = ww if not cur else curw + space + ww
        if add > maxw and cur:
            lines.append(cur)
            cur, curw = [segs], ww
        else:
            cur.append(segs)
            curw = add
    if cur:
        lines.append(cur)
    for line in lines:
        cx = x
        for i, segs in enumerate(line):
            if i:
                cx += space
            for s, h in segs:
                c.text((cx, y), s, f, GOLD_LIGHT if h else INK)
                cx += c.tw(s, f)
        y += lh
    return y


def footer(c, idx, total):
    y = H - 104
    c.line([(M, y), (W - M, y)], fill=GOLD + (90,), width=1)
    f = font("sans500", 24)
    c.text((M, y + 26), AUTHOR, f, INK_SOFT)
    pg = f"{idx:02d}/{total:02d}"
    c.text((W - M - c.tw(pg, f), y + 26), pg, f, GOLD)


# ---------- blocos (y0 -> y final) ----------

def block_cover(c, card, y):
    maxw = W - 2 * M
    c.text((M, y), spaced(card["kicker"]), font("sans600", 26), GOLD)
    y += 56
    c.line([(M, y), (M + 90, y)], fill=GOLD, width=3)
    y += 70
    y = rich_title(c, M, y, card["title"], font("serif700", 118), maxw, 124)
    y += 44
    return paragraph(c, M, y, card["subtitle"], font("sans400", 36), maxw - 30, INK_SOFT, 54)


def block_content(c, card, n, y):
    maxw = W - 2 * M
    fnum = font("serif600", 150)
    num = f"{n:02d}"
    c.text((M - 4, y - 28), num, fnum, GOLD)
    c.text((M + c.tw(num, fnum) + 34, y + 76), spaced(card["category"]), font("sans600", 25), GOLD)
    y += 160
    c.line([(M, y), (W - M, y)], fill=GOLD + (130,), width=1)
    y += 50
    y = rich_title(c, M, y, card["title"], font("serif700", 80), maxw, 86)
    y += 30
    y = paragraph(c, M, y, card["body"], font("sans400", 33), maxw, INK_SOFT, 49)
    y += 36
    fb = font("sans500", 32)
    for b in card["bullets"]:
        c.rect([M, y + 16, M + 12, y + 28], fill=GOLD)
        y = paragraph(c, M + 38, y, b, fb, maxw - 38, INK, 44)
        y += 18
    return y - 18


def block_cta(c, card, y):
    maxw = W - 2 * M
    c.text((M, y), spaced(card.get("kicker", "Para fechar")), font("sans600", 26), GOLD)
    y += 56
    c.line([(M, y), (M + 90, y)], fill=GOLD, width=3)
    y += 70
    y = rich_title(c, M, y, card["title"], font("serif700", 104), maxw, 112)
    y += 40
    y = paragraph(c, M, y, card["subtitle"], font("sans400", 34), maxw, INK_SOFT, 50)
    y += 80
    fbtn = font("sans700", 34)
    label = spaced(card["button"])
    bw, bh = c.tw(label, fbtn) + 128, 108
    c.rrect([M, y, M + bw, y + bh], radius=54, fill=GOLD)
    c.text((M + 64, y + bh / 2), label, fbtn, NAVY_TOP, anchor="lm")
    return y + bh


def render(card, idx, total):
    if card["type"] == "cover":
        fn = lambda c, y: block_cover(c, card, y)
    elif card["type"] == "cta":
        fn = lambda c, y: block_cta(c, card, y)
    else:
        fn = lambda c, y: block_content(c, card, idx - 1, y)
    height = fn(Canvas(), 0)
    y0 = CONTENT_TOP + max(0, (CONTENT_BOTTOM - CONTENT_TOP - height) / 2)
    if card["type"] == "cover":
        y0 = max(CONTENT_TOP, CONTENT_BOTTOM - height - 60)  # capa ancorada embaixo
    img = background()
    c = Canvas(img)
    end = fn(c, y0)
    if card["type"] == "cover" and card.get("hint"):
        fh = font("sans600", 24)
        hint = card["hint"].upper() + "  →"
        c.text((W - M - c.tw(hint, fh), CONTENT_TOP), hint, fh, GOLD)
    footer(c, idx, total)
    return img, y0, end


def main():
    check_fonts()
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cards = data["cards"]
    ok = True
    for i, card in enumerate(cards, 1):
        img, y0, end = render(card, i, len(cards))
        flag = "" if end <= CONTENT_BOTTOM else "  << ESTOURA A ÁREA ÚTIL"
        ok &= not flag
        img.convert("RGB").save(out / f"card-{i:02d}.png", optimize=True)
        print(f"card-{i:02d}.png  y={y0:.0f}..{end:.0f}{flag}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
