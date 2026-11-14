"""Renderiza carrossel de Instagram (1080x1350) a partir de um JSON.

Uso: python3 tools/render_carrossel.py conteudo.json pasta_saida/
Fontes esperadas em /tmp/fonts/ (Cormorant Garamond e Inter, do Google Fonts).
Trechos entre *asteriscos* nos títulos saem em dourado, com sublinhado fino.

Campos por card:
  cover:   kicker, title, subtitle, hint (opcional)
  content: category, title, body, bullets[], quote + quote_ref (opcionais)
  cta:     kicker, title, subtitle, button, note (opcional)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
M = 100  # margem lateral
NAVY_DEEP = (7, 17, 36)
NAVY_TOP = (11, 26, 51)
NAVY_BOT = (16, 38, 74)
GOLD = (201, 162, 75)
GOLD_LIGHT = (226, 196, 128)
INK = (243, 238, 227)
INK_SOFT = (243, 238, 227, 190)
INK_DIM = (243, 238, 227, 120)
AUTHOR = "Ivan Rodrigues"
FEAT = ["lnum"]  # algarismos alinhados

FONT_DIR = Path("/tmp/fonts")
FONT_FILES = {
    "serif600": "CormorantGaramond-600.ttf",
    "serif700": "CormorantGaramond-700.ttf",
    "serif600i": "CormorantGaramond-600i.ttf",
    "sans400": "Inter-400.ttf",
    "sans500": "Inter-500.ttf",
    "sans600": "Inter-600.ttf",
    "sans700": "Inter-700.ttf",
}

TOP = 130          # início da área útil
BOTTOM = 1180      # fim da área útil (acima do rodapé)


def check_fonts():
    missing = [f for f in FONT_FILES.values() if not (FONT_DIR / f).exists()]
    if missing:
        sys.exit("ERRO: fontes premium ausentes em /tmp/fonts: " + ", ".join(missing)
                 + ". Não renderizei com fonte de fallback.")


_fc = {}


def font(key, size):
    if (key, size) not in _fc:
        _fc[key, size] = ImageFont.truetype(str(FONT_DIR / FONT_FILES[key]), size)
    return _fc[key, size]


# ---------------------------------------------------------------- fundo

def background(seed, variant="content"):
    """Gradiente + brilho radial + vinheta + granulação de papel."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = yy / (H - 1)
    base = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        base[..., i] = NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * t

    # brilho dourado suave (posição varia por tipo de card)
    gx, gy = {"cover": (0.78, 0.30), "cta": (0.5, 0.42)}.get(variant, (0.85, 0.12))
    d = np.sqrt(((xx / W) - gx) ** 2 + ((yy / H) - gy) ** 2)
    glow = np.clip(1 - d / 0.75, 0, 1) ** 2.2
    warm = np.array([62, 40, 4], np.float32)
    base += glow[..., None] * warm * {"cover": 0.6, "cta": 0.35}.get(variant, 0.4)

    # luz azul fria embaixo à esquerda
    d2 = np.sqrt(((xx / W) - 0.1) ** 2 + ((yy / H) - 0.95) ** 2)
    cool = np.clip(1 - d2 / 0.8, 0, 1) ** 2
    base += cool[..., None] * np.array([6, 18, 40], np.float32)

    # vinheta
    dv = np.sqrt(((xx / W) - 0.5) ** 2 + ((yy / H) - 0.5) ** 2)
    vig = np.clip((dv - 0.35) / 0.45, 0, 1) ** 1.6
    base = base * (1 - vig[..., None] * 0.45) + np.array(NAVY_DEEP, np.float32) * vig[..., None] * 0.45

    # granulação
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 5.5, (H, W, 1)).astype(np.float32)
    base += noise
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return img


def overlay(img, draw_fn, blur=0):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer, "RGBA"))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img, layer)


def diamond(d, cx, cy, r, fill):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=fill)


def frame(img):
    def f(d):
        d.rectangle([34, 34, W - 35, H - 35], outline=GOLD + (120,), width=2)
        d.rectangle([46, 46, W - 47, H - 47], outline=GOLD + (45,), width=1)
        for cx, cy in [(34, 34), (W - 35, 34), (34, H - 35), (W - 35, H - 35)]:
            diamond(d, cx, cy, 7, GOLD + (230,))
        # marcas de canto
        L = 46
        for (x, y, sx, sy) in [(46, 46, 1, 1), (W - 47, 46, -1, 1), (46, H - 47, 1, -1), (W - 47, H - 47, -1, -1)]:
            d.line([(x, y), (x + sx * L, y)], fill=GOLD + (200,), width=2)
            d.line([(x, y), (x, y + sy * L)], fill=GOLD + (200,), width=2)
    return overlay(img, f)


def arch(img, cx, top, w, h, alpha=70, glow=34):
    """Janela em arco (motivo de arquitetura sagrada)."""
    r = w / 2
    if glow:
        def g(d):
            d.rounded_rectangle([cx - r + 30, top + 40, cx + r - 30, top + h], radius=int(r), fill=GOLD + (glow,))
        img = overlay(img, g, blur=60)

    def f(d):
        for k, a in [(0, alpha), (18, int(alpha * 0.45))]:
            rr = r - k
            box = [cx - rr, top + k, cx + rr, top + k + 2 * rr]
            d.arc(box, 180, 360, fill=GOLD + (a,), width=2)
            d.line([(cx - rr, top + k + rr), (cx - rr, top + h)], fill=GOLD + (a,), width=2)
            d.line([(cx + rr, top + k + rr), (cx + rr, top + h)], fill=GOLD + (a,), width=2)
        diamond(d, cx, top - 14, 6, GOLD + (alpha + 40,))
    return overlay(img, f)


def rays(img, cx, cy, n=28, length=700, alpha=16):
    def f(d):
        for i in range(n):
            a = math.pi * (i / (n - 1))  # semicírculo para baixo
            a = math.pi + a
            x2 = cx + math.cos(a) * length * -1
            y2 = cy + math.sin(a) * length * -1
            d.line([(cx, cy), (x2, y2)], fill=GOLD + (alpha,), width=1)
    return overlay(img, f, blur=1)


# ---------------------------------------------------------------- texto

class Canvas:
    """Desenha ou só mede (dry=True), para permitir centralizar o bloco."""

    def __init__(self, img=None):
        self.dry = img is None
        self.img = img
        self.d = ImageDraw.Draw(img if img else Image.new("RGBA", (W, H)), "RGBA")

    def tw(self, s, f):
        return self.d.textlength(s, font=f, features=FEAT)

    def text(self, xy, s, f, fill, shadow=False, **kw):
        if self.dry:
            return
        if shadow:
            self.d.text((xy[0], xy[1] + 4), s, font=f, fill=(0, 0, 0, 90), features=FEAT, **kw)
        self.d.text(xy, s, font=f, fill=fill, features=FEAT, **kw)

    def __getattr__(self, name):  # line, rectangle, rounded_rectangle, polygon...
        fn = getattr(self.d, name)
        return (lambda *a, **k: None) if self.dry else fn


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


def paragraph(c, x, y, text, f, maxw, color, lh, align="left"):
    for ln in wrap(c, text, f, maxw):
        xx = x if align == "left" else x + (maxw - c.tw(ln, f)) / 2
        c.text((xx, y), ln, f, color)
        y += lh
    return y


def rich_words(text):
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


def rich_title(c, x, y, text, f, maxw, lh, align="left", underline=True):
    words = rich_words(text)
    space = c.tw(" ", f)
    wlen = lambda segs: sum(c.tw(s, f) for s, _ in segs)
    lines, cur, curw = [], [], 0
    for segs in words:
        ww = wlen(segs)
        add = ww if not cur else curw + space + ww
        if add > maxw and cur:
            lines.append((cur, curw))
            cur, curw = [segs], ww
        else:
            cur.append(segs)
            curw = add
    if cur:
        lines.append((cur, curw))
    asc = f.getmetrics()[0]
    for line, lw in lines:
        cx = x if align == "left" else x + (maxw - lw) / 2
        for i, segs in enumerate(line):
            if i:
                cx += space
            for s, h in segs:
                sw = c.tw(s, f)
                c.text((cx, y), s, f, GOLD_LIGHT if h else INK, shadow=True)
                if h and underline and s[-1:].isalnum():
                    uy = y + asc + 6
                    c.line([(cx + 2, uy), (cx + sw - 2, uy)], fill=GOLD + (170,), width=3)
                cx += sw
        y += lh
    return y


def ornament(c, x, y, w, align="left"):
    """Filete com losango central: ——◆——"""
    if align == "center":
        x0, x1 = x + w / 2 - 110, x + w / 2 + 110
    else:
        x0, x1 = x, x + 150
    mid = (x0 + x1) / 2
    c.line([(x0, y), (mid - 14, y)], fill=GOLD + (200,), width=2)
    c.line([(mid + 14, y), (x1, y)], fill=GOLD + (200,), width=2)
    if not c.dry:
        diamond(c.d, mid, y, 7, GOLD + (255,))


def footer(c, idx, total):
    y = H - 112
    c.line([(M, y), (W - M, y)], fill=GOLD + (70,), width=1)
    f = font("sans500", 23)
    if not c.dry:
        diamond(c.d, M + 6, y + 41, 5, GOLD + (220,))
    c.text((M + 22, y + 27), AUTHOR, f, INK_SOFT)
    # bolinhas de progresso
    gap, r = 28, 5
    x = W - M - 12 - (total - 1) * gap
    for i in range(1, total + 1):
        cx = x + (i - 1) * gap
        if i == idx:
            c.rounded_rectangle([cx - 12, y + 36, cx + 12, y + 46], radius=5, fill=GOLD)
        else:
            c.ellipse([cx - r, y + 36, cx + r, y + 46], fill=INK + (70,))


# ---------------------------------------------------------------- blocos

def block_cover(c, card, y):
    maxw = W - 2 * M
    c.text((M, y), spaced(card["kicker"]), font("sans600", 25), GOLD)
    y += 52
    ornament(c, M, y, maxw)
    y += 62
    y = rich_title(c, M, y, card["title"], font("serif700", 120), maxw, 122)
    y += 40
    return paragraph(c, M, y, card["subtitle"], font("sans400", 35), maxw - 60, INK_SOFT, 52)


def block_content(c, card, n, y):
    maxw = W - 2 * M
    # cabeçalho: nº em pílula + categoria + filete
    fpill = font("sans700", 22)
    num = f"{n:02d}"
    pw = c.tw(num, fpill) + 34
    c.rounded_rectangle([M, y, M + pw, y + 40], radius=20, fill=GOLD)
    c.text((M + 17, y + 20), num, fpill, NAVY_TOP, anchor="lm")
    fcat = font("sans600", 23)
    cat = spaced(card["category"])
    cx = M + pw + 22
    c.text((cx, y + 20), cat, fcat, GOLD, anchor="lm")
    lx = cx + c.tw(cat, fcat) + 24
    c.line([(lx, y + 20), (W - M, y + 20)], fill=GOLD + (90,), width=1)
    y += 84
    y = rich_title(c, M, y, card["title"], font("serif700", 82), maxw, 86)
    y += 26
    y = paragraph(c, M, y, card["body"], font("sans400", 31), maxw, INK_SOFT, 47)
    y += 34
    # painel dos tópicos
    fb = font("sans500", 30)
    pad = 30
    inner = maxw - 2 * pad - 40
    hgt = 0
    for b in card["bullets"]:
        hgt += len(wrap(c, b, fb, inner)) * 42 + 20
    hgt += 2 * pad - 20
    c.rounded_rectangle([M, y, W - M, y + hgt], radius=18, fill=(255, 255, 255, 14),
                        outline=GOLD + (60,), width=1)
    c.rectangle([M, y + 18, M + 4, y + hgt - 18], fill=GOLD)
    by = y + pad
    for b in card["bullets"]:
        if not c.dry:
            diamond(c.d, M + pad + 8, by + 21, 7, GOLD)
        by = paragraph(c, M + pad + 40, by, b, fb, inner, INK, 42) + 20
    y += hgt
    if card.get("quote"):
        y += 36
        fq = font("serif600i", 40)
        qy = y
        y = paragraph(c, M + 34, y, "“" + card["quote"] + "”", fq, maxw - 34, GOLD_LIGHT, 48)
        c.line([(M, qy + 6), (M, y - 6)], fill=GOLD + (160,), width=2)
        if card.get("quote_ref"):
            c.text((M + 34, y + 6), "— " + card["quote_ref"], font("sans500", 22), INK_DIM)
            y += 36
    return y


def block_cta(c, card, y):
    maxw = W - 2 * M
    fk = font("sans600", 25)
    k = spaced(card.get("kicker", "Para fechar"))
    c.text((M + (maxw - c.tw(k, fk)) / 2, y), k, fk, GOLD)
    y += 52
    ornament(c, M, y, maxw, align="center")
    y += 64
    y = rich_title(c, M, y, card["title"], font("serif700", 104), maxw, 110, align="center")
    y += 34
    y = paragraph(c, M + 40, y, card["subtitle"], font("sans400", 33), maxw - 80, INK_SOFT, 49, align="center")
    y += 70
    fbtn = font("sans700", 33)
    label = spaced(card["button"])
    bw, bh = c.tw(label, fbtn) + 150, 106
    bx = (W - bw) / 2
    c.rounded_rectangle([bx, y + 8, bx + bw, y + bh + 8], radius=53, fill=(0, 0, 0, 80))
    c.rounded_rectangle([bx, y, bx + bw, y + bh], radius=53, fill=GOLD, outline=GOLD_LIGHT, width=2)
    # ícone de marcador (bookmark)
    ix, iy = bx + 52, y + bh / 2
    c.polygon([(ix - 11, iy - 17), (ix + 11, iy - 17), (ix + 11, iy + 17), (ix, iy + 8), (ix - 11, iy + 17)],
              fill=NAVY_TOP)
    c.text((bx + 86, y + bh / 2), label, fbtn, NAVY_TOP, anchor="lm")
    y += bh + 8
    if card.get("note"):
        y += 40
        y = paragraph(c, M + 60, y, card["note"], font("sans500", 25), maxw - 120, INK_DIM, 36, align="center")
    return y


# ---------------------------------------------------------------- montagem

def render(card, idx, total, seed):
    kind = card["type"]
    img = background(seed + idx, "cover" if kind == "cover" else kind)
    if kind == "cover":
        fn = lambda c, y: block_cover(c, card, y)
        img = rays(img, W * 0.78, 300, length=900, alpha=14)
        img = arch(img, W - 240, 150, 280, 430, alpha=80)
    elif kind == "cta":
        fn = lambda c, y: block_cta(c, card, y)
        img = arch(img, W / 2, 150, 760, 1000, alpha=55, glow=14)
    else:
        fn = lambda c, y: block_content(c, card, idx - 1, y)
        # número gigante como marca d'água
        num = f"{idx - 1:02d}"
        fw = font("serif700", 560)

        def wm(d):
            d.text((W - 60, 40), num, font=fw, fill=GOLD + (20,), anchor="ra", features=FEAT)
        img = overlay(img, wm)
    img = frame(img)

    height = fn(Canvas(), 0)
    if kind == "cover":
        y0 = max(TOP + 90, BOTTOM - height - 40)  # capa ancorada embaixo
    else:
        y0 = TOP + max(0, (BOTTOM - TOP - height) / 2)
    img = img.convert("RGB")  # RGB + Draw("RGBA") = mistura alfa correta
    c = Canvas(img)
    end = fn(c, y0)
    if kind == "cover" and card.get("hint"):
        fh = font("sans600", 22)
        hint = spaced(card["hint"])
        hx = M
        c.text((hx, TOP + 4), hint, fh, GOLD)
        ax = hx + c.tw(hint, fh) + 18
        c.line([(ax, TOP + 17), (ax + 60, TOP + 17)], fill=GOLD, width=2)
        c.polygon([(ax + 60, TOP + 11), (ax + 72, TOP + 17), (ax + 60, TOP + 23)], fill=GOLD)
    footer(c, idx, total)
    return img, y0, end


def main():
    check_fonts()
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cards = data["cards"]
    seed = sum(map(ord, out.name))
    ok = True
    for i, card in enumerate(cards, 1):
        img, y0, end = render(card, i, len(cards), seed)
        flag = "" if end <= BOTTOM else "  << ESTOURA A ÁREA ÚTIL"
        ok &= not flag
        img.convert("RGB").save(out / f"card-{i:02d}.png", optimize=True)
        print(f"card-{i:02d}.png  y={y0:.0f}..{end:.0f}{flag}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
