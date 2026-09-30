#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IL SEGRETO DEL CARBONARO — versione 3D
Escape room in prima persona ambientata a Torino, 4 maggio 1860.

Installazione:   pip install ursina
Avvio:           python il_segreto_del_carbonaro_3d.py

Tutto (stanza, oggetti, texture, luci e suoni) è generato via codice:
nessuna immagine, modello 3D o file audio esterno.

Comandi:  WASD / frecce = muoviti · mouse = guarda · clic = esamina
          Invio = conferma · Esc = chiudi / pausa · M = audio · F11 = schermo intero
          R = rigioca (a fine partita)
"""

from ursina import *                         # noqa: F401,F403  (stile tipico di Ursina)
from ursina.shaders import unlit_shader

import math
import os
import random
import re
import shutil
import sys
import tempfile
import time
import unicodedata
import wave
from array import array

from panda3d.core import (ColorBlendAttrib, Filename, LVecBase3f, PTA_LVecBase3f,
                          TransparencyAttrib)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------
TEMPO_TOTALE = 45 * 60          # 45:00
DISTANZA_INTERAZIONE = 3.2      # metri
ALTEZZA_OCCHI = 1.62
VELOCITA = 2.4
SENSIBILITA_MOUSE = 40
MAX_INPUT = 32
N_LUCI = 6

# --------------------------------------------------------------------------
# Contenuti del gioco
# --------------------------------------------------------------------------
ENIGMI = [
    {
        "id": "pianoforte",
        "nome": "Pianoforte",
        "titolo": "Il Pianoforte",
        "domanda": ("I patrioti scrivono sui muri un nome per ingannare gli "
                    "austriaci, lodando un compositore. Ma è l'acronimo del "
                    "futuro Re d'Italia. Chi è il musicista?"),
        "soluzioni": ["verdi", "giuseppe verdi", "viva verdi"],
        "frammento": "OBBE",
        "curiosita": ("Gli austriaci cancellavano le scritte attirandosi "
                      "l'odio dei melomani europei!"),
    },
    {
        "id": "mappa",
        "nome": "Mappa",
        "titolo": "La Mappa",
        "domanda": ("La storia li ricorderà come 'I Mille', ma quanti "
                    "volontari salparono davvero da Quarto? "
                    "(Tra loro c'era una donna)."),
        "soluzioni": ["1089", "1 089"],
        "frammento": "DI",
        "curiosita": ("La donna era Rose Montmasson, moglie di Crispi, "
                      "travestita da marinaio."),
    },
    {
        "id": "ritratto",
        "nome": "Ritratto",
        "titolo": "Il Ritratto",
        "domanda": ("Sono il Primo Re dell'Italia unita, ma la mia firma porta "
                    "un altro numero romano ereditato dal Regno di Sardegna. "
                    "Qual è il numero in cifre?"),
        "soluzioni": ["2", "ii", "due"],
        "frammento": "S",
        "curiosita": ("Vittorio Emanuele II mantenne il numero 2, facendo "
                      "infuriare i patrioti."),
    },
    {
        "id": "scrivania",
        "nome": "Scrivania",
        "titolo": "La Scrivania",
        "domanda": ("Cavour pensava nella lingua della nazione che ci aiutò "
                    "contro gli austriaci. Quali sono i colori di quella "
                    "bandiera? (es: verde bianco rosso)"),
        "soluzioni": ["blu bianco rosso", "bleu blanc rouge"],
        "frammento": "CO",
        "curiosita": ("Cavour parlava un pessimo italiano e i suoi discorsi "
                      "andavano corretti in Parlamento."),
    },
]
ENIGMI_PER_ID = {e["id"]: e for e in ENIGMI}
PAROLA_ORDINE = "obbedisco"

TRAMA = ("4 maggio 1860. Sei un corriere della Carboneria, nascosto nello studio "
         "segreto di un patriota torinese. Porti un messaggio che deve raggiungere "
         "Garibaldi prima che salpi da Quarto. Ma qualcuno ha parlato: i gendarmi "
         "hanno circondato il palazzo e stanno forzando l'ingresso.\n"
         "Il patriota ha nascosto la parola d'ordine dell'uscita segreta in quattro "
         "frammenti, custoditi dagli oggetti della stanza. Hai 45 minuti per "
         "decifrare i codici, ricomporre la chiave e fuggire.")

CURIOSITA_FINALE = ("Sei anni dopo, il 9 agosto 1866, durante la Terza guerra "
                    "d'indipendenza, Garibaldi aveva appena battuto gli austriaci a "
                    "Bezzecca e marciava verso Trento. Dal generale La Marmora arrivò "
                    "l'ordine di sgomberare il Trentino: erano in corso le trattative "
                    "di armistizio con l'Austria. Garibaldi, a malincuore, rispose con "
                    "un telegramma di una sola parola, entrato nella storia: "
                    "«Obbedisco».")


# --------------------------------------------------------------------------
# Utilità
# --------------------------------------------------------------------------
def normalizza(testo):
    """Minuscole, senza accenti, punteggiatura e spazi superflui.
    La congiunzione 'e' viene ignorata ("blu, bianco e rosso")."""
    testo = unicodedata.normalize("NFKD", str(testo))
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r"[^a-z0-9]+", " ", testo.lower())
    return " ".join(p for p in testo.split() if p != "e")


def risposta_corretta(enigma, risposta):
    r = normalizza(risposta)
    return bool(r) and r in {normalizza(s) for s in enigma["soluzioni"]}


def formatta_tempo(secondi):
    secondi = max(0, int(math.ceil(secondi)))
    return "%02d:%02d" % (secondi // 60, secondi % 60)


def C(r, g, b, a=255):
    return color.rgba32(r, g, b, a)


# Palette "Dark Academia / Risorgimento"
ORO = C(212, 175, 55)
ORO_CHIARO = C(244, 218, 138)
ORO_SCURO = C(140, 108, 30)
PERGAMENA = C(238, 225, 194)
PERGAMENA_SCURA = C(206, 186, 146)
INCHIOSTRO = C(44, 30, 22)
BORDEAUX = C(120, 24, 40)
BORDEAUX_SCURO = C(68, 12, 24)
BORDEAUX_CHIARO = C(160, 40, 58)
VERDE_CHIARO = C(120, 200, 130)
VERDE_SCURO = C(20, 70, 40)
ROSSO_ALLARME = C(236, 70, 58)
LEGNO = C(96, 60, 36)
LEGNO_SCURO = C(52, 32, 20)
NERO_LACCA = C(14, 12, 14)
FERRO = C(58, 58, 64)
CERA = C(236, 226, 200)
TRICOLORE = [C(0, 146, 70), C(244, 245, 240), C(206, 43, 55)]


# --------------------------------------------------------------------------
# Font di sistema (con ripiego automatico)
# --------------------------------------------------------------------------
def _trova_font(tipo):
    win = os.environ.get("WINDIR", "C:/Windows") + "/Fonts/"
    mac = "/System/Library/Fonts/Supplemental/"
    dj = "/usr/share/fonts/truetype/dejavu/"
    lib = "/usr/share/fonts/truetype/liberation/"
    free = "/usr/share/fonts/truetype/freefont/"
    candidati = {
        "r": [win + "georgia.ttf", mac + "Georgia.ttf", "/Library/Fonts/Georgia.ttf", win + "times.ttf",
              mac + "Times New Roman.ttf", dj + "DejaVuSerif.ttf", lib + "LiberationSerif-Regular.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif.ttf", "/usr/share/fonts/dejavu/DejaVuSerif.ttf", free + "FreeSerif.ttf"],
        "b": [win + "georgiab.ttf", mac + "Georgia Bold.ttf", "/Library/Fonts/Georgia Bold.ttf", win + "timesbd.ttf",
              mac + "Times New Roman Bold.ttf", dj + "DejaVuSerif-Bold.ttf", lib + "LiberationSerif-Bold.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf",
              free + "FreeSerifBold.ttf"],
        "i": [win + "georgiai.ttf", mac + "Georgia Italic.ttf", "/Library/Fonts/Georgia Italic.ttf", win + "timesi.ttf",
              mac + "Times New Roman Italic.ttf", dj + "DejaVuSerif-Italic.ttf", lib + "LiberationSerif-Italic.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif-Italic.ttf", "/usr/share/fonts/dejavu/DejaVuSerif-Italic.ttf",
              free + "FreeSerifItalic.ttf"],
    }
    for p in candidati[tipo]:
        if os.path.isfile(p):
            return p
    return None


FONT_FILE = {k: _trova_font(k) for k in "rbi"}


def font_ui(tipo):
    """Percorso del font per Ursina (None = font predefinito)."""
    p = FONT_FILE[tipo] or FONT_FILE["r"]
    return Filename.fromOsSpecific(p).getFullpath() if p else None


_PIL_FONT = {}


def font_pil(tipo, size):
    key = (tipo, size)
    if key not in _PIL_FONT:
        p = FONT_FILE[tipo] or FONT_FILE["r"]
        try:
            _PIL_FONT[key] = ImageFont.truetype(p, size) if p else ImageFont.load_default(size)
        except Exception:
            _PIL_FONT[key] = ImageFont.load_default()
    return _PIL_FONT[key]


# --------------------------------------------------------------------------
# Texture procedurali (PIL)
# --------------------------------------------------------------------------
def tex(img, filtering="mipmap"):
    return Texture(img.convert("RGBA"), filtering=filtering)


def _mescola(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _gradiente(w, h, alto, basso):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_mescola(alto, basso, y / max(1, h - 1)))
    return img


def _macchie(img, n, col, rmin, rmax, alpha, seme):
    rnd = random.Random(seme)
    strato = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(strato)
    for _ in range(n):
        r = rnd.randint(rmin, rmax)
        x, y = rnd.randint(0, img.size[0]), rnd.randint(0, img.size[1])
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (alpha,))
    strato = strato.filter(ImageFilter.GaussianBlur(max(2, rmin // 2)))
    base = img.convert("RGBA")
    base.alpha_composite(strato)
    return base


def _rumore(img, forza, seme):
    rnd = random.Random(seme)
    px = img.load()
    w, h = img.size
    for _ in range(w * h // 3):
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = px[x, y]
        k = rnd.randint(-forza, forza)
        px[x, y] = tuple(max(0, min(255, v + k)) for v in c[:3]) + tuple(c[3:])
    return img


def img_carta_da_parati():
    w = h = 256
    img = Image.new("RGB", (w, h), (84, 20, 32))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 32):
        d.line([(x, 0), (x, h)], fill=(90, 23, 36), width=10)
    for cx, cy in ((64, 64), (192, 192), (192, 64), (64, 192)):
        grande = (cx, cy) in ((64, 64), (192, 192))
        s = 46 if grande else 22
        d.polygon([(cx, cy - s), (cx + s * 0.62, cy), (cx, cy + s), (cx - s * 0.62, cy)], fill=(106, 28, 42))
        d.polygon([(cx, cy - s), (cx + s * 0.62, cy), (cx, cy + s), (cx - s * 0.62, cy)], outline=(140, 104, 40))
        if grande:
            for dx in (-1, 1):
                d.ellipse((cx + dx * 18 - 9, cy - 22, cx + dx * 18 + 9, cy - 4), fill=(118, 34, 48))
                d.ellipse((cx + dx * 18 - 9, cy + 4, cx + dx * 18 + 9, cy + 22), fill=(118, 34, 48))
            d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(150, 112, 42))
        else:
            d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(150, 112, 42))
    return _rumore(img, 8, 1)


def img_parquet():
    w = h = 512
    rnd = random.Random(11)
    img = Image.new("RGB", (w, h), (70, 44, 26))
    d = ImageDraw.Draw(img)
    for riga in range(8):
        y0 = riga * 64
        x = -rnd.randint(0, 200)
        while x < w:
            lung = rnd.randint(140, 280)
            base = (rnd.randint(78, 104), rnd.randint(48, 64), rnd.randint(28, 38))
            d.rectangle((x, y0, x + lung, y0 + 63), fill=base)
            for k in range(14):
                yy = y0 + 3 + k * 4 + rnd.randint(-1, 1)
                scuro = tuple(max(0, v - rnd.randint(8, 22)) for v in base)
                pts = [(xx, yy + 1.5 * math.sin(xx / rnd.uniform(18, 40) + k)) for xx in range(x, x + lung, 8)]
                if len(pts) > 1:
                    d.line(pts, fill=scuro, width=1)
            d.line([(x, y0), (x, y0 + 63)], fill=(26, 16, 10), width=2)
            x += lung
        d.line([(0, y0), (w, y0)], fill=(24, 14, 8), width=2)
    return _rumore(img, 10, 2)


def img_legno(base=(64, 38, 22), seme=3):
    w = h = 256
    rnd = random.Random(seme)
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    for _ in range(120):
        x = rnd.randint(0, w)
        k = rnd.randint(6, 26)
        col = tuple(max(0, v - k) for v in base)
        pts = [(x + 3 * math.sin(y / rnd.uniform(14, 30)), y) for y in range(0, h + 8, 8)]
        d.line(pts, fill=col, width=rnd.choice((1, 1, 2)))
    return _rumore(img, 6, seme)


def img_boiserie():
    w, h = 512, 256
    img = img_legno((74, 46, 27), 5).resize((w, h))
    d = ImageDraw.Draw(img)
    for x0 in (24, 280):
        r = (x0, 30, x0 + 208, 226)
        d.rectangle(r, outline=(40, 24, 14), width=4)
        d.line([(r[0] + 6, r[1] + 6), (r[2] - 6, r[1] + 6)], fill=(112, 76, 46), width=3)
        d.line([(r[0] + 6, r[1] + 6), (r[0] + 6, r[3] - 6)], fill=(112, 76, 46), width=3)
        d.line([(r[0] + 6, r[3] - 6), (r[2] - 6, r[3] - 6)], fill=(36, 20, 12), width=3)
        d.line([(r[2] - 6, r[1] + 6), (r[2] - 6, r[3] - 6)], fill=(36, 20, 12), width=3)
    return img


def img_pietra():
    w = h = 256
    rnd = random.Random(21)
    img = Image.new("RGB", (w, h), (60, 58, 58))
    d = ImageDraw.Draw(img)
    for riga in range(6):
        y0 = riga * 43
        off = 0 if riga % 2 else -40
        for x0 in range(off, w, 80):
            t = rnd.randint(-14, 14)
            d.rectangle((x0 + 2, y0 + 2, x0 + 78, y0 + 41), fill=(112 + t, 108 + t, 104 + t))
    return _rumore(img, 16, 22)


def img_pergamena(w, h, bordo=True, seme=1860):
    img = _gradiente(w, h, (240, 228, 198), (206, 186, 146))
    img = _macchie(img, 26, (150, 116, 70), w // 40, w // 12, 40, seme)
    # bordi bruciati
    strato = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(strato)
    for i in range(22):
        d.rectangle((i, i, w - 1 - i, h - 1 - i), outline=(96, 60, 24, int(90 * (1 - i / 22) ** 2)))
    img.alpha_composite(strato)
    if bordo:
        d = ImageDraw.Draw(img)
        d.rectangle((10, 10, w - 11, h - 11), outline=(120, 24, 40), width=6)
        d.rectangle((24, 24, w - 25, h - 25), outline=(140, 108, 30), width=2)
        for (x, y, sx, sy) in ((34, 34, 1, 1), (w - 35, 34, -1, 1), (34, h - 35, 1, -1), (w - 35, h - 35, -1, -1)):
            d.line([(x, y), (x + sx * 40, y)], fill=(120, 24, 40), width=4)
            d.line([(x, y), (x, y + sy * 40)], fill=(120, 24, 40), width=4)
            d.ellipse((x + sx * 10 - 4, y + sy * 10 - 4, x + sx * 10 + 4, y + sy * 10 + 4), fill=(120, 24, 40))
    return img


ITALIA = [(0.18, 0.12), (0.30, 0.06), (0.45, 0.09), (0.58, 0.05), (0.67, 0.10), (0.62, 0.17),
          (0.60, 0.23), (0.63, 0.31), (0.70, 0.42), (0.79, 0.51), (0.86, 0.55), (0.90, 0.54),
          (0.89, 0.60), (0.96, 0.67), (0.99, 0.74), (0.93, 0.72), (0.85, 0.66), (0.81, 0.69),
          (0.83, 0.77), (0.77, 0.87), (0.72, 0.84), (0.74, 0.75), (0.67, 0.65), (0.57, 0.57),
          (0.47, 0.47), (0.39, 0.37), (0.33, 0.29), (0.27, 0.24), (0.22, 0.25), (0.15, 0.27),
          (0.12, 0.20)]
SICILIA = [(0.56, 0.86), (0.66, 0.87), (0.75, 0.86), (0.72, 0.96), (0.60, 0.92)]
SARDEGNA = [(0.26, 0.51), (0.32, 0.51), (0.34, 0.60), (0.32, 0.72), (0.27, 0.71), (0.25, 0.61)]
CORSICA = [(0.28, 0.38), (0.31, 0.37), (0.32, 0.44), (0.29, 0.48), (0.27, 0.43)]


def img_mappa():
    w, h = 1024, 720
    img = img_pergamena(w, h, bordo=False, seme=7)
    d = ImageDraw.Draw(img)
    area = (40, 40, 680, 680)

    def P(pts):
        return [(area[0] + x * (area[2] - area[0]), area[1] + y * (area[3] - area[1])) for x, y in pts]

    for isola in (ITALIA, SICILIA, SARDEGNA, CORSICA):
        for k in range(4, 0, -1):     # tratteggio costiero
            d.polygon(P(isola), outline=(150, 136, 110))
        d.polygon(P(isola), fill=(200, 172, 122), outline=(60, 40, 26))
    for nome, (x, y) in (("Torino", (0.14, 0.17)), ("Genova", (0.22, 0.25)), ("Roma", (0.50, 0.45)),
                         ("Napoli", (0.62, 0.56)), ("Palermo", (0.64, 0.87)), ("Marsala", (0.565, 0.885))):
        px, py = P([(x, y)])[0]
        d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(60, 40, 26))
        d.text((px + 8, py - 10), nome, font=font_pil("i", 20), fill=(60, 40, 26))
    # rotta dei Mille: Quarto -> Talamone -> Marsala
    tappe = P([(0.23, 0.27), (0.36, 0.33), (0.41, 0.39), (0.42, 0.55), (0.47, 0.72), (0.54, 0.84), (0.565, 0.88)])
    punti = []
    for i in range(len(tappe) - 1):
        for s in range(12):
            u = s / 12
            punti.append((tappe[i][0] + (tappe[i + 1][0] - tappe[i][0]) * u,
                          tappe[i][1] + (tappe[i + 1][1] - tappe[i][1]) * u))
    for i in range(0, len(punti) - 1, 2):
        d.line([punti[i], punti[i + 1]], fill=(150, 24, 36), width=4)
    qx, qy = tappe[0]
    d.ellipse((qx - 9, qy - 9, qx + 9, qy + 9), outline=(150, 24, 36), width=3)
    d.text((qx - 90, qy + 4), "Quarto", font=font_pil("b", 22), fill=(150, 24, 36))
    d.text(P([(0.08, 0.55)])[0], "Mar Tirreno", font=font_pil("i", 24), fill=(90, 80, 70))
    d.text(P([(0.74, 0.30)])[0], "Mar\nAdriatico", font=font_pil("i", 22), fill=(90, 80, 70))
    # cartiglio
    d.rectangle((712, 60, 990, 300), outline=(120, 24, 40), width=4)
    d.rectangle((722, 70, 980, 290), outline=(140, 108, 30), width=1)
    d.text((851, 110), "ITALIA", font=font_pil("b", 44), fill=(68, 12, 24), anchor="mm")
    d.text((851, 160), "Anno 1860", font=font_pil("i", 28), fill=(60, 40, 26), anchor="mm")
    d.text((851, 215), "La Spedizione", font=font_pil("r", 24), fill=(60, 40, 26), anchor="mm")
    d.text((851, 248), "dei Mille", font=font_pil("r", 24), fill=(60, 40, 26), anchor="mm")
    # nave
    nx, ny = 850, 420
    d.polygon([(nx - 80, ny), (nx + 80, ny), (nx + 55, ny + 34), (nx - 55, ny + 34)], fill=(60, 40, 26))
    for mx in (nx - 30, nx + 30):
        d.line([(mx, ny), (mx, ny - 110)], fill=(60, 40, 26), width=4)
        d.polygon([(mx + 3, ny - 104), (mx + 48, ny - 60), (mx + 3, ny - 30)], fill=(236, 226, 200), outline=(60, 40, 26))
    d.line([(nx - 30, ny - 110), (nx - 30, ny - 130)], fill=(60, 40, 26), width=2)
    for i, c in enumerate(((0, 146, 70), (244, 245, 240), (206, 43, 55))):
        d.rectangle((nx - 30 + i * 10, ny - 132, nx - 20 + i * 10, ny - 118), fill=c)
    d.text((nx, ny + 64), "Piroscafi «Piemonte» e «Lombardo»", font=font_pil("i", 19), fill=(60, 40, 26), anchor="mm")
    # rosa dei venti
    rc = (860, 590)
    for k in range(8):
        ang = k * math.pi / 4
        lung = 70 if k % 2 == 0 else 38
        punta = (rc[0] + math.cos(ang) * lung, rc[1] + math.sin(ang) * lung)
        l1 = (rc[0] + math.cos(ang + 0.35) * 14, rc[1] + math.sin(ang + 0.35) * 14)
        l2 = (rc[0] + math.cos(ang - 0.35) * 14, rc[1] + math.sin(ang - 0.35) * 14)
        d.polygon([punta, l1, rc, l2], fill=(150, 24, 36) if k == 6 else (60, 40, 26))
    d.text((rc[0], rc[1] - 90), "N", font=font_pil("b", 26), fill=(150, 24, 36), anchor="mm")
    d.rectangle((12, 12, w - 13, h - 13), outline=(60, 40, 26), width=5)
    d.rectangle((24, 24, w - 25, h - 25), outline=(60, 40, 26), width=1)
    return img


def img_ritratto():
    w, h = 512, 640
    img = _gradiente(w, h, (74, 44, 34), (22, 14, 14))
    d = ImageDraw.Draw(img)
    # drappo
    d.polygon([(0, 0), (150, 0), (110, 260), (40, 640), (0, 640)], fill=(96, 18, 30))
    for k in range(6):
        d.line([(20 + k * 22, 0), (10 + k * 14, 640)], fill=(70, 10, 20), width=5)
    cx = w // 2
    # busto in uniforme
    d.ellipse((cx - 230, 470, cx + 230, 900), fill=(28, 34, 66))
    d.polygon([(cx - 150, 520), (cx + 170, 700), (cx + 120, 720), (cx - 170, 560)], fill=(110, 160, 220))  # fascia azzurra
    for sx in (-1, 1):
        d.ellipse((cx + sx * 170 - 55, 470, cx + sx * 170 + 55, 520), fill=(212, 175, 55))
        for k in range(7):
            d.line([(cx + sx * 170 - 48 + k * 16, 505), (cx + sx * 170 - 52 + k * 16, 548)], fill=(212, 175, 55), width=4)
    d.polygon([(cx - 36, 450), (cx + 36, 450), (cx, 540)], fill=(236, 232, 220))
    for i, mx in enumerate((cx - 110, cx - 70, cx + 60)):
        d.ellipse((mx - 13, 600, mx + 13, 626), fill=(212, 175, 55) if i != 1 else (200, 200, 210))
        d.rectangle((mx - 8, 580, mx + 8, 600), fill=(206, 43, 55) if i != 1 else (0, 120, 70))
    # collo e testa
    d.rectangle((cx - 40, 380, cx + 40, 470), fill=(170, 124, 94))
    d.ellipse((cx - 100, 170, cx + 100, 430), fill=(198, 152, 116))
    d.ellipse((cx - 70, 190, cx + 40, 330), fill=(212, 170, 134))
    d.ellipse((cx - 108, 140, cx + 108, 250), fill=(42, 30, 22))          # capelli
    d.rectangle((cx - 108, 196, cx - 88, 300), fill=(42, 30, 22))
    d.rectangle((cx + 88, 196, cx + 108, 300), fill=(42, 30, 22))
    for sx in (-1, 1):
        d.ellipse((cx + sx * 42 - 16, 268, cx + sx * 42 + 16, 286), fill=(250, 244, 236))
        d.ellipse((cx + sx * 42 - 7, 270, cx + sx * 42 + 7, 284), fill=(40, 28, 20))
        d.line([(cx + sx * 20, 250), (cx + sx * 66, 246)], fill=(42, 30, 22), width=7)
    d.polygon([(cx - 8, 290), (cx + 8, 290), (cx + 18, 340), (cx - 16, 340)], fill=(176, 128, 96))
    # i celebri baffoni all'insù e il pizzetto
    for sx in (-1, 1):
        d.polygon([(cx, 352), (cx + sx * 40, 344), (cx + sx * 110, 318), (cx + sx * 150, 270),
                   (cx + sx * 138, 316), (cx + sx * 80, 366), (cx + sx * 20, 372)], fill=(40, 28, 20))
    d.polygon([(cx - 26, 380), (cx + 26, 380), (cx + 12, 440), (cx, 456), (cx - 12, 440)], fill=(40, 28, 20))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    # pennellate e craquelure
    rnd = random.Random(1849)
    strato = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ds = ImageDraw.Draw(strato)
    for _ in range(900):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        ang = rnd.uniform(0, math.pi)
        l = rnd.randint(6, 18)
        ds.line([(x, y), (x + math.cos(ang) * l, y + math.sin(ang) * l)],
                fill=(255, 240, 210, 12) if rnd.random() < .5 else (0, 0, 0, 16), width=2)
    for _ in range(60):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        pts = [(x, y)]
        for _ in range(4):
            x += rnd.randint(-22, 22)
            y += rnd.randint(-22, 22)
            pts.append((x, y))
        ds.line(pts, fill=(20, 12, 8, 40), width=1)
    img = img.convert("RGBA")
    img.alpha_composite(strato)
    # vignettatura
    v = Image.new("L", (w, h), 0)
    ImageDraw.Draw(v).ellipse((-60, -40, w + 60, h + 40), fill=255)
    v = v.filter(ImageFilter.GaussianBlur(70))
    nero = Image.new("RGBA", (w, h), (8, 4, 4, 255))
    return Image.composite(img, nero, v)


def img_spartito():
    w, h = 384, 256
    img = img_pergamena(w, h, bordo=False, seme=3)
    d = ImageDraw.Draw(img)
    d.text((w // 2, 28), "Va, pensiero", font=font_pil("i", 30), fill=(44, 30, 22), anchor="mm")
    d.text((w - 30, 56), "G. V.", font=font_pil("i", 16), fill=(44, 30, 22), anchor="rm")
    rnd = random.Random(5)
    for s in range(3):
        y0 = 80 + s * 58
        for k in range(5):
            d.line([(24, y0 + k * 8), (w - 24, y0 + k * 8)], fill=(80, 60, 44), width=1)
        for x in range(50, w - 30, 26):
            yy = y0 + rnd.randint(-1, 8) * 4
            d.ellipse((x - 5, yy - 4, x + 5, yy + 4), fill=(30, 20, 14))
            d.line([(x + 4, yy), (x + 4, yy - 26)], fill=(30, 20, 14), width=2)
    return img


def img_lettera():
    w, h = 320, 420
    img = img_pergamena(w, h, bordo=False, seme=9)
    d = ImageDraw.Draw(img)
    d.text((34, 40), "Mon cher ami,", font=font_pil("i", 30), fill=(40, 30, 50))
    rnd = random.Random(8)
    for r in range(10):
        y = 100 + r * 26
        x = 34 + (30 if r == 0 else 0)
        fine = w - 34 - rnd.randint(0, 60)
        pts = []
        while x < fine:
            pts.append((x, y + 5 * math.sin(x * 0.35 + r) + rnd.uniform(-1.5, 1.5)))
            x += 4
        d.line(pts, fill=(50, 40, 70), width=2)
    d.text((w - 50, h - 60), "C.", font=font_pil("i", 34), fill=(40, 30, 50), anchor="mm")
    d.ellipse((40, h - 90, 100, h - 30), fill=(130, 20, 36))
    d.ellipse((52, h - 78, 88, h - 42), outline=(90, 10, 22), width=3)
    return img


def img_tappeto():
    w, h = 640, 440
    img = Image.new("RGB", (w, h), (92, 18, 30))
    d = ImageDraw.Draw(img)
    for i, (c, lw) in enumerate((((22, 18, 20), 34), ((170, 128, 50), 8), ((40, 22, 26), 20), ((170, 128, 50), 4))):
        o = sum(x[1] for x in (((22, 18, 20), 34), ((170, 128, 50), 8), ((40, 22, 26), 20), ((170, 128, 50), 4))[:i])
        d.rectangle((o, o, w - 1 - o, h - 1 - o), outline=c, width=lw)
    for x in range(40, w - 40, 36):
        d.polygon([(x, 12), (x + 12, 24), (x, 36), (x - 12, 24)], fill=(150, 110, 44))
        d.polygon([(x, h - 36), (x + 12, h - 24), (x, h - 12), (x - 12, h - 24)], fill=(150, 110, 44))
    cx, cy = w // 2, h // 2
    for k, c in enumerate(((170, 128, 50), (40, 22, 26), (120, 30, 44), (170, 128, 50))):
        s = 140 - k * 30
        d.polygon([(cx, cy - s * 0.8), (cx + s * 1.3, cy), (cx, cy + s * 0.8), (cx - s * 1.3, cy)], fill=c)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * 220, cy + sy * 120
            d.ellipse((px - 22, py - 22, px + 22, py + 22), fill=(170, 128, 50))
            d.ellipse((px - 12, py - 12, px + 12, py + 12), fill=(40, 22, 26))
    return _rumore(img, 14, 4)


def img_quadrante():
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, s - 4, s - 4), fill=(236, 226, 200), outline=(140, 108, 30), width=12)
    romani = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for i, r in enumerate(romani):
        a = i * math.pi / 6 - math.pi / 2
        d.text((s / 2 + math.cos(a) * 92, s / 2 + math.sin(a) * 92), r, font=font_pil("r", 22),
               fill=(44, 30, 22), anchor="mm")
    return img


def img_radiale(s, col=(255, 255, 255), esponente=1.8, forza=1.0):
    img = Image.new("RGBA", (s, s), col + (0,))
    px = img.load()
    c = (s - 1) / 2
    for y in range(s):
        for x in range(s):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1 - d) ** esponente
            px[x, y] = col + (int(255 * a * forza),)
    return img


def img_fiamma():
    w, h = 64, 128
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            u = (x - w / 2) / (w / 2)
            v = y / h                         # 0 = punta, 1 = base
            largh = 0.15 + 0.85 * math.sin(min(1.0, v * 1.1) * math.pi * 0.62)
            d = abs(u) / max(0.01, largh)
            if d < 1 and v > 0.02:
                a = (1 - d ** 2) * min(1.0, (1 - v) * 6) * min(1.0, v * 3)
                t = min(1.0, d + (1 - v) * 0.5)
                col = _mescola((255, 250, 210), (255, 120, 20), t)
                px[x, y] = col + (int(255 * max(0.0, a)),)
    return img


def img_vignetta():
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = img.load()
    c = (s - 1) / 2
    for y in range(s):
        for x in range(s):
            d = math.hypot((x - c) / c, (y - c) / c) / 1.25
            px[x, y] = (0, 0, 0, int(235 * min(1.0, max(0.0, (d - 0.35) / 0.65)) ** 1.6))
    return img


def img_titolo_oro(testo, w, h):
    """Scritta dorata con ombra e bagliore, come immagine con trasparenza."""
    f = font_pil("b", int(h * .78))
    maschera = Image.new("L", (w, h), 0)
    ImageDraw.Draw(maschera).text((w / 2, h / 2), testo, font=f, fill=255, anchor="mm")
    oro = _gradiente(w, h, (255, 236, 160), (176, 120, 30)).convert("RGBA")
    oro.putalpha(maschera)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bagliore = Image.new("RGBA", (w, h), (255, 220, 130, 0))
    bagliore.putalpha(maschera.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * .8)))
    img.alpha_composite(bagliore)
    ombra = Image.new("RGBA", (w, h), (30, 16, 4, 0))
    ombra.putalpha(maschera.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * .7)))
    img.alpha_composite(ombra, (5, 6))
    img.alpha_composite(oro)
    return img


def img_targa():
    w, h = 512, 112
    img = _gradiente(w, h, (240, 210, 130), (150, 110, 36))
    d = ImageDraw.Draw(img)
    d.rectangle((4, 4, w - 5, h - 5), outline=(96, 70, 20), width=5)
    d.rectangle((14, 14, w - 15, h - 15), outline=(200, 160, 70), width=2)
    for x in (30, w - 30):
        d.ellipse((x - 7, h / 2 - 7, x + 7, h / 2 + 7), fill=(110, 80, 26))
    d.text((w / 2 + 2, h / 2 + 2), "PORTA USCITA", font=font_pil("b", 54), fill=(250, 226, 150), anchor="mm")
    d.text((w / 2, h / 2), "PORTA USCITA", font=font_pil("b", 54), fill=(52, 34, 10), anchor="mm")
    return img


def img_sigillo(spunta=False):
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(24):
        a = i * math.tau / 24
        r = 118 * (1 + 0.06 * math.sin(i * 2.7))
        pts.append((s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r))
    d.polygon(pts, fill=(78, 12, 24))
    d.ellipse((24, 24, s - 24, s - 24), fill=(128, 22, 40))
    d.ellipse((40, 40, s - 40, s - 40), outline=(92, 14, 28), width=5)
    d.ellipse((60, 52, 100, 92), fill=(170, 50, 66))
    if spunta:
        d.line([(80, 132), (114, 168), (180, 88)], fill=(244, 218, 138), width=18, joint="curve")
    return img.filter(ImageFilter.GaussianBlur(0.8))


def img_coccarda():
    s = 128
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, s - 2, s - 2), fill=(212, 175, 55))
    d.ellipse((7, 7, s - 7, s - 7), fill=(206, 43, 55))
    d.ellipse((24, 24, s - 24, s - 24), fill=(244, 245, 240))
    d.ellipse((42, 42, s - 42, s - 42), fill=(0, 146, 70))
    return img


def img_pannello(w, h, alto=(30, 22, 26), basso=(8, 6, 8), bordo=(212, 175, 55)):
    img = _gradiente(w, h, alto, basso).convert("RGBA")
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 6, fill=255)
    img.putalpha(m)
    ImageDraw.Draw(img).rounded_rectangle((3, 3, w - 4, h - 4), radius=h // 6, outline=bordo, width=4)
    return img


def img_raggi():
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    for k in range(18):
        a = k * math.tau / 18
        d.polygon([(c, c), (c + math.cos(a - 0.08) * s, c + math.sin(a - 0.08) * s),
                   (c + math.cos(a + 0.08) * s, c + math.sin(a + 0.08) * s)], fill=(255, 214, 120, 60))
    return img.filter(ImageFilter.GaussianBlur(3))


# --------------------------------------------------------------------------
# Shader con più luci di candela (GLSL)
# --------------------------------------------------------------------------
_VERTEX = """#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
out vec2 uv;
out vec3 wpos;
out vec3 wnorm;
out vec4 vcol;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wnorm = transpose(inverse(mat3(p3d_ModelMatrix))) * p3d_Normal;
    uv = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    vcol = p3d_Color;
}
"""

_FRAGMENT = """#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 luci_pos[%d];
uniform vec3 luci_col[%d];
uniform vec3 ambiente;
uniform vec3 cam_pos;
uniform float lucido;
uniform vec3 emissione;
in vec2 uv;
in vec3 wpos;
in vec3 wnorm;
in vec4 vcol;
out vec4 fragColor;
void main() {
    vec4 base = texture(p3d_Texture0, uv) * vcol * p3d_ColorScale;
    if (base.a < 0.02) discard;
    vec3 V = normalize(cam_pos - wpos);
    bool haNormale = length(wnorm) > 0.0001;
    vec3 n = haNormale ? normalize(wnorm) : V;
    if (dot(n, V) < 0.0) n = -n;
    vec3 diff = ambiente;
    vec3 spec = vec3(0.0);
    for (int i = 0; i < %d; i++) {
        vec3 L = luci_pos[i] - wpos;
        float d = length(L);
        L /= d;
        float att = 1.0 / (1.0 + 0.10 * d + 0.28 * d * d);
        float nd = max(dot(n, L), 0.0);
        diff += luci_col[i] * nd * att;
        vec3 H = normalize(L + V);
        spec += luci_col[i] * pow(max(dot(n, H), 0.0), 40.0) * att * lucido;
    }
    vec3 col = base.rgb * diff + spec + emissione * base.rgb;
    float dist = length(cam_pos - wpos);
    col *= 1.0 - smoothstep(6.0, 14.0, dist) * 0.5;
    col = vec3(1.0) - exp(-col * 1.35);
    fragColor = vec4(col, base.a);
}
""" % (N_LUCI, N_LUCI, N_LUCI)


def crea_shader_stanza():
    return Shader(language=Shader.GLSL, vertex=_VERTEX, fragment=_FRAGMENT,
                  default_input={"texture_scale": Vec2(1, 1), "texture_offset": Vec2(0, 0)})


# --------------------------------------------------------------------------
# Audio sintetizzato (WAV generati al volo in una cartella temporanea)
# --------------------------------------------------------------------------
class Suoni:
    FREQ = 22050

    def __init__(self):
        self.attivo = True
        self.sfx = {}
        self.cartella = tempfile.mkdtemp(prefix="carbonaro_")
        try:
            self._genera()
        except Exception as ex:          # l'audio non è indispensabile
            print("Audio non disponibile:", ex)
            self.sfx = {}

    def _scrivi(self, nome, durata, f, volume=0.55):
        n = int(self.FREQ * durata)
        dati = array("h")
        for i in range(n):
            v = max(-1.0, min(1.0, f(i / self.FREQ))) * volume
            fade = min(1.0, (n - i) / (self.FREQ * 0.01))
            dati.append(int(v * fade * 32767))
        percorso = os.path.join(self.cartella, nome + ".wav")
        with wave.open(percorso, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.FREQ)
            w.writeframes(dati.tobytes())
        suono = loader.loadSfx(Filename.fromOsSpecific(percorso))
        self.sfx[nome] = suono
        return suono

    def _genera(self):
        tau = math.tau
        rnd = random.Random(1860)

        def note(seq, decad=5.0, timbro=1.0):
            def f(t):
                v = 0.0
                for inizio, fr, vol in seq:
                    if t >= inizio:
                        dt = t - inizio
                        env = math.exp(-dt * decad) * min(1.0, dt * 200)
                        v += vol * env * (math.sin(tau * fr * dt) + timbro * 0.35 * math.sin(tau * 2 * fr * dt)
                                          + timbro * 0.15 * math.sin(tau * 3 * fr * dt))
                return v
            return f

        self._scrivi("click", 0.06, lambda t: 0.5 * math.sin(tau * 880 * t) * math.exp(-t * 70))
        self._scrivi("giusto", 1.2, note([(0.0, 523.25, .3), (.11, 659.25, .3), (.22, 783.99, .3), (.33, 1046.5, .35)]))
        self._scrivi("sbagliato", 0.38, lambda t: math.exp(-t * 7) * (
            0.35 * (1 if math.sin(tau * 98 * t) > 0 else -1) + 0.3 * math.sin(tau * 104 * t)))
        self._scrivi("bloccato", 0.5, lambda t: (
            (rnd.random() * 2 - 1) * 0.5 * math.exp(-t * 30) + 0.45 * math.sin(tau * 196 * t) * math.exp(-t * 9)
            + 0.3 * math.sin(tau * 587 * t) * math.exp(-t * 14) + 0.2 * math.sin(tau * 1244 * t) * math.exp(-t * 18)))
        self._scrivi("catene", 1.3, lambda t: sum(
            0.35 * math.sin(tau * f0 * (t - s)) * math.exp(-(t - s) * 16) if t > s else 0.0
            for s, f0 in ((0.0, 1480), (0.12, 1210), (0.25, 1660), (0.4, 990), (0.62, 1320), (0.85, 1100), (1.0, 180))))
        self._scrivi("tick", 0.05, lambda t: 0.5 * math.sin(tau * 1760 * t) * math.exp(-t * 110))
        self._scrivi("vittoria", 2.8, note([(0.0, 392.0, .25), (.16, 523.25, .25), (.32, 659.25, .25), (.48, 783.99, .28),
                                            (.72, 1046.5, .3), (.72, 523.25, .2), (.72, 659.25, .18)], decad=1.6))
        self._scrivi("porta", 2.0, lambda t: 0.3 * math.sin(tau * (140 + 90 * t + 12 * math.sin(t * 30)) * t)
                     * min(1.0, t * 4) * math.exp(-t * 0.8) + (rnd.random() * 2 - 1) * 0.06)
        self._scrivi("sconfitta", 1.8, lambda t: (
            (rnd.random() * 2 - 1) * 0.9 * math.exp(-t * 7) + 0.5 * math.sin(tau * (70 - 18 * t) * t) * math.exp(-t * 1.5)
            + (0.25 * math.sin(tau * 233 * (t - .5)) * math.exp(-(t - .5) * 3) if t > .5 else 0)
            + (0.25 * math.sin(tau * 220 * (t - .9)) * math.exp(-(t - .9) * 2) if t > .9 else 0)))
        crepitii = sorted(rnd.uniform(0, 4) for _ in range(40))

        def fuoco(t):
            v = (rnd.random() * 2 - 1) * 0.05
            for c in crepitii:
                if 0 <= t - c < 0.03:
                    v += (rnd.random() * 2 - 1) * 0.6 * (1 - (t - c) / 0.03)
            return v
        amb = self._scrivi("fuoco", 4.0, fuoco, volume=0.35)
        amb.setLoop(True)
        amb.setVolume(0.45)

    def suona(self, nome):
        if self.attivo and nome in self.sfx:
            self.sfx[nome].play()

    def ambiente(self, acceso):
        s = self.sfx.get("fuoco")
        if s is None:
            return
        if acceso and self.attivo:
            if s.status() != s.PLAYING:
                s.play()
        else:
            s.stop()

    def pulisci(self):
        shutil.rmtree(self.cartella, ignore_errors=True)


# --------------------------------------------------------------------------
# Aiuti per costruire la scena
# --------------------------------------------------------------------------
def blocco(parent, pos, scala, col=None, texture=None, rot=(0, 0, 0), tex_scale=None, model="cube"):
    e = Entity(parent=parent, model=model, position=pos, scale=scala, rotation=rot)
    if texture is not None:
        e.texture = texture
    if col is not None:
        e.color = col
    if tex_scale is not None:
        e.texture_scale = tex_scale
    return e


def sprite_luminoso(parent, pos, scala, texture, col):
    """Quad sempre rivolto alla camera, in fusione additiva (fiamme, aloni)."""
    e = Entity(parent=parent, model="quad", texture=texture, position=pos, scale=scala,
               color=col, shader=unlit_shader, billboard=True)
    e.setTransparency(TransparencyAttrib.MAlpha)
    e.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    e.setDepthWrite(False)
    e.setBin("fixed", 20)
    return e


def avvolgi(testo, caratteri):
    """Va a capo ogni ~'caratteri' caratteri senza spezzare le parole."""
    righe = []
    for paragrafo in testo.split("\n"):
        riga = ""
        for parola in paragrafo.split(" "):
            if riga and len(riga) + 1 + len(parola) > caratteri:
                righe.append(riga)
                riga = parola
            else:
                riga = (riga + " " + parola).strip()
        righe.append(riga)
    return "\n".join(righe)


def testo_ui(parent, t, pos=(0, 0), scala=1.0, col=PERGAMENA, tipo="r", origin=(0, 0), wordwrap=0, z=0):
    if wordwrap:
        t = avvolgi(t, wordwrap)
    kw = dict(parent=parent, text=t, position=pos, scale=scala, color=col, origin=origin, z=z)
    f = font_ui(tipo)
    if f:
        kw["font"] = f
    return Text(**kw)


def quad_ui(parent, pos, scala, col=color.white, texture=None, z=0):
    e = Entity(parent=parent, model="quad", position=pos, scale=scala, color=col, z=z)
    if texture is not None:
        e.texture = texture
    return e


def pulsante(parent, etichetta, pos, scala, primario=True, azione=None):
    b = Button(parent=parent, text=etichetta, position=pos, scale=scala,
               color=BORDEAUX if primario else C(34, 32, 38),
               highlight_color=BORDEAUX_CHIARO if primario else C(60, 56, 64),
               pressed_color=BORDEAUX_SCURO if primario else C(20, 18, 22),
               text_color=ORO_CHIARO if primario else PERGAMENA)
    f = font_ui("b" if primario else "r")
    if f:
        b.text_entity.font = f
    b.text_entity.scale *= 1.1
    b.on_click = azione
    return b


# --------------------------------------------------------------------------
# Campo di testo per le risposte
# --------------------------------------------------------------------------
class CampoTesto(Entity):
    def __init__(self, parent, pos, larghezza, su_invio):
        super().__init__(parent=parent, position=pos)
        self.valore = ""
        self.attivo = False
        self.su_invio = su_invio
        self.larghezza = larghezza
        quad_ui(self, (0, 0), (larghezza + .012, .082), BORDEAUX, z=.01)
        self.sfondo = quad_ui(self, (0, 0), (larghezza, .07), C(252, 246, 232))
        self.etichetta = testo_ui(self, "La tua risposta:", (-larghezza / 2, .062), .9, C(110, 84, 60), "i", (-.5, 0))
        self.segnaposto = testo_ui(self, "Scrivi qui la risposta…", (-larghezza / 2 + .02, 0), 1.3,
                                   C(170, 150, 128), "i", (-.5, 0), z=-.01)
        self.testo = testo_ui(self, "", (-larghezza / 2 + .02, 0), 1.45, INCHIOSTRO, "r", (-.5, 0), z=-.01)
        self.cursore = quad_ui(self, (-larghezza / 2 + .02, 0), (.003, .045), INCHIOSTRO, z=-.01)

    def svuota(self):
        self.valore = ""
        self._aggiorna()

    def _aggiorna(self):
        self.testo.text = self.valore
        self.segnaposto.enabled = not self.valore
        w = self.testo.width if self.valore else 0
        self.cursore.x = -self.larghezza / 2 + .022 + w

    def text_input(self, key):
        if self.attivo and len(self.valore) < MAX_INPUT and key.isprintable():
            self.valore += key
            self._aggiorna()

    def input(self, key):
        if not self.attivo:
            return
        if key in ("backspace", "backspace hold"):
            self.valore = self.valore[:-1]
            self._aggiorna()
        elif key in ("enter", "numpad enter"):
            self.su_invio()

    def update(self):
        self.cursore.visible = self.attivo and int(time.monotonic() * 2) % 2 == 0


# --------------------------------------------------------------------------
# Il gioco
# --------------------------------------------------------------------------
class Gioco(Entity):
    def __init__(self):
        super().__init__()
        self.suoni = Suoni()
        self._crea_texture()
        self.shader_stanza = crea_shader_stanza()
        self.mondo = Entity(shader=self.shader_stanza)
        self.mondo.set_shader_input("lucido", 0.15)
        self.mondo.set_shader_input("emissione", Vec3(0, 0, 0))
        self.luci = []
        self.fiamme = []
        self.ostacoli = []
        self.interattivi = {}          # id -> radice dell'oggetto
        self._costruisci_stanza()
        self._prepara_luci()
        self._costruisci_hud()
        self._costruisci_modale()
        self._costruisci_schermate()
        self.polvere = [self._crea_granello() for _ in range(40)]
        camera.fov = 75
        self.stato = "intro"
        self._reset()
        self._mostra_intro()

    # ------------------------------------------------------------------ texture
    def _crea_texture(self):
        self.t_parati = tex(img_carta_da_parati())
        self.t_parquet = tex(img_parquet())
        self.t_legno = tex(img_legno())
        self.t_legno_chiaro = tex(img_legno((110, 70, 40), 7))
        self.t_boiserie = tex(img_boiserie())
        self.t_pietra = tex(img_pietra())
        self.t_mappa = tex(img_mappa())
        self.t_ritratto = tex(img_ritratto())
        self.t_spartito = tex(img_spartito())
        self.t_lettera = tex(img_lettera())
        self.t_tappeto = tex(img_tappeto())
        self.t_quadrante = tex(img_quadrante())
        self.t_alone = tex(img_radiale(128), "bilinear")
        self.t_fiamma = tex(img_fiamma(), "bilinear")
        self.t_vignetta = tex(img_vignetta(), "bilinear")
        self.t_sigillo = tex(img_sigillo(), "bilinear")
        self.t_coccarda = tex(img_coccarda(), "bilinear")
        self.t_pergamena_modale = tex(img_pergamena(1100, 760), "bilinear")
        self.t_pergamena_larga = tex(img_pergamena(1300, 440, seme=77), "bilinear")
        self.t_pannello = tex(img_pannello(420, 170), "bilinear")
        self.t_slot = tex(img_pergamena(220, 100, bordo=False, seme=5), "bilinear")
        self.t_raggi = tex(img_raggi(), "bilinear")
        self.t_targa = tex(img_targa())
        self.t_obbedisco = tex(img_titolo_oro("OBBEDISCO", 1100, 200), "bilinear")
        self.t_sigillo_ok = tex(img_sigillo(spunta=True), "bilinear")
        self.t_oro = tex(_gradiente(64, 256, (120, 80, 20), (20, 12, 6)), "bilinear")
        self.t_rosso = tex(_gradiente(64, 256, (110, 8, 16), (16, 2, 4)), "bilinear")

    # ------------------------------------------------------------------ stanza
    def _costruisci_stanza(self):
        m = self.mondo
        # pavimento, tappeto, soffitto
        blocco(m, (0, 0, 0), (8, 1, 8), texture=self.t_parquet, tex_scale=(3, 3), model="plane")
        blocco(m, (0, .006, .2), (3.6, 1, 2.5), texture=self.t_tappeto, model="plane")
        blocco(m, (0, 3.4, 0), (8, 1, 8), col=C(40, 26, 18), texture=self.t_legno, tex_scale=(4, 4),
               model="plane", rot=(180, 0, 0))
        for x in (-2.7, -.9, .9, 2.7):
            blocco(m, (x, 3.3, 0), (.22, .2, 8), col=C(70, 44, 26), texture=self.t_legno)
        # pareti: carta da parati sopra, boiserie sotto
        for (pos, scala, rot) in (((0, 1.7, 4.1), (8.4, 3.4, .2), 0), ((0, 1.7, -4.1), (8.4, 3.4, .2), 0),
                                  ((4.1, 1.7, 0), (.2, 3.4, 8.4), 0), ((-4.1, 1.7, 0), (.2, 3.4, 8.4), 0)):
            blocco(m, pos, scala, texture=self.t_parati, tex_scale=(10, 4))
        for lato in range(4):
            nodo = Entity(parent=m, rotation_y=lato * 90)
            # sulla parete nord la boiserie si interrompe in corrispondenza della porta
            tratti = [(-2.36, 3.28), (2.36, 3.28)] if lato == 0 else [(0, 8)]
            for (cx, lw) in tratti:
                blocco(nodo, (cx, .5, 3.97), (lw, 1.0, .06), texture=self.t_boiserie, tex_scale=(lw * .75, 1))
                blocco(nodo, (cx, 1.02, 3.95), (lw, .06, .1), col=LEGNO_SCURO, texture=self.t_legno)
                blocco(nodo, (cx, .06, 3.94), (lw, .12, .08), col=LEGNO_SCURO)
            blocco(nodo, (0, 3.33, 3.96), (8, .14, .1), col=C(60, 38, 22), texture=self.t_legno)
        self.ostacoli += [(-1.15, -4.2, 1.15, -3.45), (-3.3, -4.2, -1.7, -3.5), (1.7, -4.2, 3.3, -3.5)]
        self._costruisci_porta()
        self._costruisci_pianoforte()
        self._costruisci_scrivania()
        self._costruisci_ritratto()
        self._costruisci_mappa()
        self._costruisci_camino()
        for x in (-2.5, 2.5):
            self._costruisci_libreria((x, 0, -3.78))
        self._costruisci_lampadario()

    def _candela(self, parent, pos, altezza=.16, scala_fiamma=1.0, luce=None):
        blocco(parent, (pos[0], pos[1] + altezza / 2, pos[2]), (.035, altezza, .035), col=CERA, model=Cylinder(10, start=-.5))
        punta = (pos[0], pos[1] + altezza + .03 * scala_fiamma, pos[2])
        f = sprite_luminoso(parent, punta, (.035 * scala_fiamma, .07 * scala_fiamma), self.t_fiamma, C(255, 230, 180))
        a = sprite_luminoso(parent, punta, (.35 * scala_fiamma, .35 * scala_fiamma), self.t_alone, C(255, 170, 80, 110))
        self.fiamme.append([f, a, f.scale, a.scale, random.uniform(0, 10)])
        if luce is not None:
            luce["nodo"] = f
            self.luci.append(luce)
        return f

    def _costruisci_porta(self):
        r = Entity(parent=self.mondo, position=(0, 0, 3.92))
        self.porta_radice = r
        # cornice in pietra
        for x in (-.86, .86):
            blocco(r, (x, 1.35, 0), (.32, 2.7, .3), texture=self.t_pietra, tex_scale=(.6, 3))
        blocco(r, (0, 2.82, 0), (2.04, .36, .32), texture=self.t_pietra, tex_scale=(3, .6))
        blocco(r, (0, 3.07, 0), (2.2, .1, .36), col=C(120, 116, 112), texture=self.t_pietra)
        # luce "esterna" dietro l'anta (visibile quando la porta si apre)
        self.luce_esterna = Entity(parent=r, model="quad", position=(0, 1.32, .0), scale=(1.42, 2.64),
                                   color=C(255, 236, 180), shader=unlit_shader)
        # anta con cardine a sinistra
        self.anta = Entity(parent=r, position=(-.7, 0, -.08))
        rnd = random.Random(1848)
        blocco(self.anta, (.7, 1.32, .05), (1.4, 2.64, .02), col=C(30, 18, 10))      # controfodera
        for i in range(5):
            t = rnd.uniform(.85, 1.1)
            blocco(self.anta, (.14 + i * .28, 1.32, 0), (.285, 2.64, .09),
                   col=C(int(96 * t), int(60 * t), int(36 * t)), texture=self.t_legno, tex_scale=(.3, 2))
        for y in (.45, 1.35, 2.25):
            blocco(self.anta, (.7, y, -.055), (1.4, .1, .02), col=FERRO)
            for k in range(6):
                blocco(self.anta, (.12 + k * .232, y, -.068), (.03, .03, .01), col=C(110, 110, 118))
        blocco(self.anta, (1.2, 1.2, -.06), (.1, .22, .02), col=ORO_SCURO)
        blocco(self.anta, (1.2, 1.26, -.09), (.05, .05, .06), col=ORO, model="sphere")
        blocco(self.anta, (1.2, 1.15, -.075), (.02, .05, .01), col=C(10, 8, 6))
        # catene incrociate e lucchetto
        self.catene = Entity(parent=r, position=(0, 0, -.2))
        for (x1, y1, x2, y2) in ((-.8, 2.2, .8, .7), (.8, 2.2, -.8, .7)):
            passi = 26
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            for k in range(passi + 1):
                u = k / passi
                blocco(self.catene, (x1 + (x2 - x1) * u, y1 + (y2 - y1) * u, -.01 * (k % 2)),
                       (.085, .04, .02) if k % 2 else (.085, .04, .04), col=C(150, 150, 160),
                       rot=(0 if k % 2 else 90, 0, -ang))
        lucchetto = Entity(parent=self.catene, position=(0, 1.45, -.04))
        blocco(lucchetto, (0, 0, 0), (.22, .2, .08), col=ORO)
        blocco(lucchetto, (-.07, .15, 0), (.035, .14, .035), col=C(170, 170, 180))
        blocco(lucchetto, (.07, .15, 0), (.035, .14, .035), col=C(170, 170, 180))
        blocco(lucchetto, (0, .22, 0), (.175, .035, .035), col=C(170, 170, 180))
        blocco(lucchetto, (0, -.01, -.045), (.03, .06, .01), col=C(20, 14, 8))
        self.catene.set_shader_input("lucido", 0.9)
        # targa
        targa = blocco(r, (0, 2.82, -.17), (.9, .2, .03), texture=self.t_targa)
        targa.set_shader_input("lucido", 0.8)
        # applique ai lati della porta
        for x in (-1.45, 1.45):
            blocco(r, (x, 1.95, -.06), (.08, .2, .06), col=ORO_SCURO)
            blocco(r, (x, 2.0, -.16), (.03, .03, .2), col=ORO_SCURO)
            blocco(r, (x, 2.02, -.25), (.1, .02, .1), col=ORO_SCURO, model=Cylinder(10))
            self._candela(r, (x, 2.03, -.25), .14, 1.0,
                          {"col": Vec3(1.3, .78, .4), "tremolio": .25})
        self.interattivi["porta"] = r
        Entity(parent=r, model="cube", collider="box", position=(0, 1.4, -.25), scale=(2.0, 2.9, .5), visible=False,
               id_oggetto="porta")

    def _costruisci_pianoforte(self):
        r = Entity(parent=self.mondo, position=(-1.95, 0, 2.2), rotation_y=-90)
        self.interattivi["pianoforte"] = r
        cassa = Entity(parent=r)
        cassa.set_shader_input("lucido", 1.0)
        blocco(cassa, (0, .86, .45), (1.5, .3, 1.2), col=NERO_LACCA)
        blocco(cassa, (.12, .86, 1.2), (1.2, .3, 1.2), col=NERO_LACCA, model=Cylinder(24, start=-.5))
        # coperchio aperto
        coperchio = Entity(parent=cassa, position=(.75, 1.02, .5), rotation_z=-32)
        blocco(coperchio, (-.72, 0, .4), (1.45, .03, 1.9), col=C(20, 18, 22))
        blocco(cassa, (.45, 1.25, .6), (.025, .5, .025), col=C(20, 18, 22), rot=(0, 0, -20))
        # tastiera
        blocco(r, (0, .76, -.28), (1.5, .06, .36), col=NERO_LACCA)
        n = 26
        for i in range(n):
            x = -.68 + i * (1.36 / n)
            blocco(r, (x + .026, .8, -.36), (.049, .025, .2), col=C(236, 230, 214))
            if i % 7 not in (2, 6) and i < n - 1:
                blocco(r, (x + .052, .82, -.32), (.028, .03, .12), col=C(10, 8, 8))
        blocco(r, (0, .86, -.14), (1.5, .14, .06), col=NERO_LACCA)
        # leggio con spartito
        blocco(r, (0, 1.12, -.07), (.62, .4, .02), col=C(20, 16, 18), rot=(-15, 0, 0))
        blocco(r, (0, 1.13, -.085), (.56, .36, .005), texture=self.t_spartito, rot=(-15, 0, 0))
        # gambe e pedali
        for (x, z) in ((-.65, -.1), (.65, -.1), (.1, 1.6)):
            blocco(r, (x, .37, z), (.1, .74, .1), col=NERO_LACCA, model=Cylinder(10, start=-.5))
            blocco(r, (x, .02, z), (.12, .04, .12), col=ORO_SCURO, model=Cylinder(10, start=-.5))
        blocco(r, (0, .08, -.05), (.26, .14, .06), col=NERO_LACCA)
        blocco(r, (0, .04, -.12), (.2, .02, .1), col=ORO_SCURO)
        # candelabro sul pianoforte
        blocco(r, (-.5, 1.02, -.02), (.12, .02, .12), col=ORO, model=Cylinder(10, start=-.5))
        blocco(r, (-.5, 1.1, -.02), (.025, .16, .025), col=ORO)
        blocco(r, (-.5, 1.17, -.02), (.26, .02, .02), col=ORO)
        for dx in (-.12, 0, .12):
            self._candela(r, (-.5 + dx, 1.18, -.02), .12, .9,
                          {"col": Vec3(1.2, .72, .36), "tremolio": .3} if dx == 0 else None)
        # sgabello
        blocco(r, (0, .5, -.85), (.8, .08, .38), col=C(40, 26, 18), texture=self.t_legno)
        blocco(r, (0, .56, -.85), (.76, .05, .34), col=BORDEAUX)
        for sx in (-1, 1):
            for sz in (-1, 1):
                blocco(r, (sx * .34, .25, -.85 + sz * .14), (.05, .5, .05), col=C(40, 26, 18))
        Entity(parent=r, model="cube", collider="box", position=(0, .9, .6), scale=(1.7, 1.8, 2.3), visible=False,
               id_oggetto="pianoforte")
        self.ostacoli += [(-3.75, 1.4, -1.55, 3.0), (-1.3, 1.75, -.95, 2.65)]

    def _costruisci_scrivania(self):
        r = Entity(parent=self.mondo, position=(2.85, 0, 2.2), rotation_y=90)
        self.interattivi["scrivania"] = r
        blocco(r, (0, .78, 0), (1.6, .06, .8), texture=self.t_legno_chiaro)
        blocco(r, (0, .79, -.02), (1.4, .005, .6), col=C(30, 70, 44))            # panno verde
        for sx in (-1, 1):
            blocco(r, (sx * .52, .45, .0), (.5, .6, .74), texture=self.t_legno)   # cassettiere
            for k in range(3):
                blocco(r, (sx * .52, .66 - k * .2, -.375), (.44, .16, .01), col=C(80, 50, 30), texture=self.t_legno)
                blocco(r, (sx * .52, .66 - k * .2, -.385), (.04, .04, .02), col=ORO, model="sphere")
            blocco(r, (sx * .52, .08, 0), (.52, .16, .76), col=LEGNO_SCURO)
        # oggetti sul piano
        blocco(r, (.05, .815, -.05), (.34, .005, .44), texture=self.t_lettera, rot=(0, 12, 0))
        blocco(r, (.45, .84, .1), (.1, .08, .1), col=C(16, 16, 24), model=Cylinder(12, start=-.5))
        blocco(r, (.45, .885, .1), (.05, .02, .05), col=ORO_SCURO, model=Cylinder(10, start=-.5))
        penna = Entity(parent=r, position=(.45, .9, .1), rotation=(0, 20, -25))
        blocco(penna, (.0, .16, 0), (.012, .34, .012), col=C(230, 222, 204))
        blocco(penna, (.0, .24, 0), (.06, .2, .006), col=C(240, 236, 226))
        for k, c in enumerate((C(92, 18, 30), C(22, 60, 40), C(40, 34, 70))):
            blocco(r, (-.45, .83 + k * .05, .18), (.34 - k * .03, .05, .24), col=c, rot=(0, k * 8, 0))
        blocco(r, (-.6, .81, -.15), (.14, .02, .14), col=ORO, model=Cylinder(12, start=-.5))
        self._candela(r, (-.6, .82, -.15), .22, 1.1, {"col": Vec3(1.5, .9, .45), "tremolio": .35})
        # sedia
        blocco(r, (0, .45, -.7), (.5, .06, .48), col=C(60, 38, 22), texture=self.t_legno)
        blocco(r, (0, .49, -.7), (.44, .04, .42), col=BORDEAUX)
        blocco(r, (0, .8, -.93), (.5, .62, .05), col=C(60, 38, 22), texture=self.t_legno)
        for sx in (-1, 1):
            for sz in (-1, 1):
                blocco(r, (sx * .21, .22, -.7 + sz * .2), (.04, .44, .04), col=C(50, 30, 18))
        Entity(parent=r, model="cube", collider="box", position=(0, .8, -.1), scale=(1.8, 1.6, 1.2), visible=False,
               id_oggetto="scrivania")
        self.ostacoli += [(2.4, 1.35, 3.35, 3.05), (1.85, 1.9, 2.4, 2.5)]

    def _costruisci_ritratto(self):
        r = Entity(parent=self.mondo, position=(-3.93, 1.85, -.7), rotation_y=-90)
        self.interattivi["ritratto"] = r
        cornice = Entity(parent=r)
        cornice.set_shader_input("lucido", 0.9)
        for (pos, sc) in (((0, .66, 0), (1.12, .14, .08)), ((0, -.66, 0), (1.12, .14, .08)),
                          ((-.52, 0, 0), (.14, 1.46, .08)), ((.52, 0, 0), (.14, 1.46, .08))):
            blocco(cornice, pos, sc, col=ORO)
        for (pos, sc) in (((0, .6, -.03), (.94, .03, .04)), ((0, -.6, -.03), (.94, .03, .04)),
                          ((-.46, 0, -.03), (.03, 1.2, .04)), ((.46, 0, -.03), (.03, 1.2, .04))):
            blocco(cornice, pos, sc, col=ORO_SCURO)
        blocco(r, (0, 0, .01), (.9, 1.16, .01), texture=self.t_ritratto)
        corona = Entity(parent=cornice, position=(0, .84, -.02))
        blocco(corona, (0, 0, 0), (.32, .08, .06), col=ORO)
        for dx, h in ((-.13, .12), (0, .17), (.13, .12)):
            blocco(corona, (dx, h / 2, 0), (.05, h, .05), col=ORO)
            blocco(corona, (dx, h + .02, 0), (.05, .05, .05), col=ORO_CHIARO, model="sphere")
        blocco(corona, (0, .01, -.035), (.05, .05, .02), col=C(200, 30, 40), model="sphere")
        # lampada da quadro
        blocco(r, (0, .86, -.14), (.5, .05, .06), col=ORO_SCURO, model=Cylinder(10, start=-.5, direction=(1, 0, 0)))
        Entity(parent=r, model="cube", collider="box", position=(0, 0, -.2), scale=(1.3, 1.9, .4), visible=False,
               id_oggetto="ritratto")

    def _costruisci_mappa(self):
        r = Entity(parent=self.mondo, position=(3.93, 1.8, -.7), rotation_y=90)
        self.interattivi["mappa"] = r
        blocco(r, (0, 0, 0), (1.5, 1.05, .01), texture=self.t_mappa)
        for y in (.56, -.56):
            blocco(r, (0, y, -.02), (1.64, .07, .07), col=C(90, 58, 34), texture=self.t_legno,
                   model=Cylinder(12, start=-.5, direction=(1, 0, 0)))
            for x in (-.84, .84):
                blocco(r, (x, y, -.02), (.08, .1, .1), col=ORO, model="sphere")
        blocco(r, (-.4, .82, -.01), (.01, .5, .01), col=C(120, 90, 60), rot=(0, 0, -58))
        blocco(r, (.4, .82, -.01), (.01, .5, .01), col=C(120, 90, 60), rot=(0, 0, 58))
        blocco(r, (0, 1.03, -.02), (.05, .05, .05), col=ORO_SCURO, model="sphere")
        # mobiletto con mappamondo sotto la carta
        mob = Entity(parent=self.mondo, position=(3.7, 0, -.7), rotation_y=90)
        blocco(mob, (0, .4, 0), (1.1, .8, .45), texture=self.t_legno)
        blocco(mob, (0, .81, 0), (1.2, .03, .5), col=LEGNO_SCURO)
        blocco(mob, (-.3, .9, 0), (.12, .16, .12), col=ORO_SCURO, model=Cylinder(10, start=-.5))
        globo = blocco(mob, (-.3, 1.12, 0), (.3, .3, .3), col=C(170, 150, 110), model="sphere")
        globo.rotation = (0, 0, 23)
        self.globo = globo
        Entity(parent=r, model="cube", collider="box", position=(0, 0, -.2), scale=(1.8, 1.4, .4), visible=False,
               id_oggetto="mappa")
        self.ostacoli.append((3.35, -1.35, 4.2, -.05))

    def _costruisci_camino(self):
        r = Entity(parent=self.mondo, position=(0, 0, -3.95), rotation_y=180)
        for x in (-.9, .9):
            blocco(r, (x, .62, 0), (.36, 1.24, .5), texture=self.t_pietra, tex_scale=(.7, 2))
        blocco(r, (0, 1.36, 0), (2.3, .24, .6), texture=self.t_pietra, tex_scale=(3, .5))
        blocco(r, (0, 1.52, -.02), (2.5, .08, .7), col=LEGNO_SCURO, texture=self.t_legno)
        blocco(r, (0, .62, .12), (1.44, 1.24, .3), col=C(10, 8, 8))
        blocco(r, (0, .02, -.25), (1.9, .04, .5), texture=self.t_pietra)
        for k, (x, rot) in enumerate(((-.25, 20), (.2, -15), (0, 90))):
            blocco(r, (x, .12 + (k == 2) * .08, .05), (.5, .1, .1), col=C(70, 44, 26),
                   rot=(0, rot, 0), model=Cylinder(8, start=-.5, direction=(1, 0, 0)))
        for i in range(5):
            x = -.3 + i * .15
            f = sprite_luminoso(r, (x, .32 + (i % 2) * .05, .05), (.22, .42), self.t_fiamma, C(255, 180, 90))
            self.fiamme.append([f, None, f.scale, None, random.uniform(0, 10)])
        brace = sprite_luminoso(r, (0, .2, .05), (1.4, .8), self.t_alone, C(255, 110, 40, 140))
        self.fiamme.append([brace, None, brace.scale, None, 1.0])
        self.luci.append({"nodo": brace, "col": Vec3(2.4, 1.1, .45), "tremolio": .45, "offset": Vec3(0, .25, 0)})
        # orologio da camino e sciabole incrociate
        blocco(r, (.75, 1.72, -.05), (.32, .32, .16), col=C(60, 38, 22), texture=self.t_legno)
        blocco(r, (.75, 1.72, -.135), (.24, .24, .01), texture=self.t_quadrante, model="quad")
        self.lancette = []
        for lung, spess in ((.08, .012), (.1, .007)):
            perno = Entity(parent=r, position=(.75, 1.72, -.15))
            blocco(perno, (0, lung / 2, 0), (spess, lung, .004), col=C(20, 14, 10))
            self.lancette.append(perno)
        for i in range(2):
            self._candela(r, (-.85 + i * .25, 1.56, -.05), .2 - i * .05, .9)
        for s in (-1, 1):
            sciabola = Entity(parent=r, position=(0, 2.35, -.12), rotation=(0, 180, s * 38))
            blocco(sciabola, (0, 0, 0), (.035, 1.1, .01), col=C(190, 190, 200))
            blocco(sciabola, (0, -.58, 0), (.16, .03, .03), col=ORO)
            blocco(sciabola, (0, -.66, 0), (.035, .14, .035), col=C(40, 26, 18))
            sciabola.set_shader_input("lucido", 1.0)

    def _costruisci_libreria(self, pos):
        r = Entity(parent=self.mondo, position=pos, rotation_y=180)
        blocco(r, (0, 1.2, .12), (1.5, 2.4, .04), texture=self.t_legno)
        for x in (-.73, .73):
            blocco(r, (x, 1.2, -.05), (.05, 2.4, .38), texture=self.t_legno)
        rnd = random.Random(int(pos[0] * 10))
        libri = Entity(parent=r)
        colori = [(92, 18, 30), (22, 60, 40), (40, 34, 70), (96, 60, 30), (30, 26, 24), (120, 90, 40), (70, 20, 20)]
        for k in range(6):
            y = .08 + k * .44
            blocco(r, (0, y, -.05), (1.42, .04, .36), texture=self.t_legno)
            if k == 5:
                continue
            x = -.68
            while x < .64:
                lw = rnd.uniform(.035, .07)
                lh = rnd.uniform(.26, .36)
                c = rnd.choice(colori)
                t = rnd.uniform(.8, 1.15)
                inclinato = rnd.random() < .06
                Entity(parent=libri, model="cube", position=(x + lw / 2, y + .02 + lh / 2, -.06),
                       scale=(lw, lh, rnd.uniform(.22, .28)), rotation_z=12 if inclinato else 0,
                       color=C(*(min(255, int(v * t)) for v in c)))
                if rnd.random() < .5:
                    Entity(parent=libri, model="cube", position=(x + lw / 2, y + .02 + lh * .75, -.2),
                           scale=(lw + .002, .012, .01), color=ORO_SCURO)
                x += lw + (.04 if inclinato else .002)
        libri.combine()

    def _costruisci_lampadario(self):
        r = Entity(parent=self.mondo, position=(0, 2.75, .3))
        blocco(r, (0, .33, 0), (.02, .65, .02), col=FERRO)
        blocco(r, (0, 0, 0), (.9, .03, .9), col=FERRO, model=Cylinder(24, start=-.5))
        blocco(r, (0, .005, 0), (.82, .04, .82), col=C(30, 30, 34), model=Cylinder(24, start=-.5))
        for i in range(6):
            a = i * math.tau / 6
            self._candela(r, (math.cos(a) * .4, .03, math.sin(a) * .4), .12, .8,
                          {"col": Vec3(1.0, .65, .36), "tremolio": .2} if i == 0 else None)

    def _prepara_luci(self):
        self.luci_pos = PTA_LVecBase3f.emptyArray(N_LUCI)
        self.luci_col = PTA_LVecBase3f.emptyArray(N_LUCI)
        self.luci = self.luci[:N_LUCI]
        for i, l in enumerate(self.luci):
            p = l["nodo"].world_position + l.get("offset", Vec3(0, 0, 0))
            l["pos"] = Vec3(p.x, p.y, p.z)
            l["base"] = Vec3(*l["col"])
            l["fase"] = random.uniform(0, 100)
            self.luci_pos[i] = LVecBase3f(p.x, p.y, p.z)
        for i in range(len(self.luci), N_LUCI):
            self.luci_pos[i] = LVecBase3f(0, -100, 0)
            self.luci_col[i] = LVecBase3f(0, 0, 0)
        scene.set_shader_input("luci_pos", self.luci_pos)
        scene.set_shader_input("luci_col", self.luci_col)
        scene.set_shader_input("ambiente", Vec3(.07, .06, .07))
        scene.set_shader_input("cam_pos", camera.world_position)
        self.indice_luce_porta = [i for i, l in enumerate(self.luci) if l["nodo"].parent == self.porta_radice]

    def _crea_granello(self):
        g = sprite_luminoso(self.mondo, (random.uniform(-3.5, 3.5), random.uniform(.3, 3), random.uniform(-3.5, 3.5)),
                            (.012, .012), self.t_alone, C(255, 220, 160, 150))
        g.vel = Vec3(random.uniform(-.03, .03), random.uniform(-.02, .03), random.uniform(-.03, .03))
        return g

    # ------------------------------------------------------------------ interfaccia
    def _costruisci_hud(self):
        ui = camera.ui
        self.vignetta = quad_ui(ui, (0, 0), (3, 1.05), color.white, self.t_vignetta, z=5)
        self.hud = Entity(parent=ui)
        self.coccarda = quad_ui(self.hud, (0, .445), (.075, .075), color.white, self.t_coccarda)
        self.titolo = testo_ui(self.hud, "IL SEGRETO DEL CARBONARO", (0, .458), 1.55, ORO, "b", (-.5, 0))
        self.sottotitolo = testo_ui(self.hud, "", (0, .42), .95, PERGAMENA, "i", (-.5, 0))
        self.pannello_timer = quad_ui(self.hud, (0, .43), (.32, .12), color.white, self.t_pannello)
        self.etichetta_timer = testo_ui(self.hud, "I GENDARMI ENTRERANNO TRA", (0, .469), .52, PERGAMENA_SCURA, "b")
        self.testo_timer = testo_ui(self.hud, "45:00", (0, .42), 2.9, ORO_CHIARO, "b", z=-.01)
        self.barra_tempo = quad_ui(self.hud, (0, .364), (.3, .008), ORO)
        # frammenti
        quad_ui(self.hud, (0, -.425), (.84, .15), color.white, self.t_pergamena_larga)
        testo_ui(self.hud, "FRAMMENTI DELLA CHIAVE", (0, -.375), .75, BORDEAUX_SCURO, "b", z=-.01)
        self.slot = []
        for i, e in enumerate(ENIGMI):
            x = -.285 + i * .19
            quad_ui(self.hud, (x, -.432), (.16, .065), color.white, self.t_slot, z=-.01)
            t = testo_ui(self.hud, "? ? ?", (x, -.43), 1.3, C(150, 124, 90), "b", z=-.02)
            testo_ui(self.hud, e["nome"], (x, -.478), .6, C(110, 84, 60), "i", z=-.02)
            self.slot.append(t)
            if i < 3:
                testo_ui(self.hud, "+", (x + .095, -.43), 1.6, BORDEAUX, "b", z=-.02)
        # mirino e suggerimenti
        self.mirino = Entity(parent=self.hud, model=Circle(16), scale=.008, color=C(240, 230, 210, 180))
        self.mirino_anello = Entity(parent=self.hud, model=Circle(24, mode="line", thickness=2), scale=.03,
                                    color=ORO_CHIARO, enabled=False)
        self.sugg_sfondo = quad_ui(self.hud, (0, -.066), (.1, .07), C(8, 6, 8, 150), z=.01)
        self.suggerimento = testo_ui(self.hud, "", (0, -.05), 1.05, ORO_CHIARO, "b")
        self.suggerimento2 = testo_ui(self.hud, "", (0, -.085), .85, PERGAMENA, "i")
        self.toast = testo_ui(self.hud, "", (0, -.3), 1.15, ORO_CHIARO, "b", z=-.02)
        self.toast_sfondo = quad_ui(self.hud, (0, -.3), (.1, .05), C(10, 6, 8, 200), z=-.01)
        self.toast_t0 = -100
        self.aiuto = testo_ui(self.hud, "WASD: muoviti  ·  Mouse: guarda  ·  Clic: esamina\n"
                              "Esc: pausa  ·  M: audio  ·  F11: schermo intero",
                              (0, -.49), .65, C(190, 170, 140), "i", (.5, -.5))
        self.pausa = Entity(parent=ui, enabled=False, z=-3)
        quad_ui(self.pausa, (0, 0), (4, 1.2), C(0, 0, 0, 170))
        testo_ui(self.pausa, "IN PAUSA", (0, .06), 3, ORO, "b", z=-.01)
        testo_ui(self.pausa, "Clicca per riprendere  ·  il tempo continua a scorrere!", (0, -.02), 1.1,
                 PERGAMENA, "i", z=-.01)
        self.velo_colore = quad_ui(ui, (0, 0), (4, 1.2), C(255, 240, 200, 0), z=-9)

    def _costruisci_modale(self):
        ui = camera.ui
        self.modale = Entity(parent=ui, enabled=False, z=-4)
        quad_ui(self.modale, (0, 0), (4, 1.2), C(6, 4, 6, 190), z=.2)
        self.pannello = Entity(parent=self.modale)
        p = self.pannello
        quad_ui(p, (0, 0), (1.2, .83), color.white, self.t_pergamena_modale, z=.1)
        self.m_titolo = testo_ui(p, "", (0, .32), 2.4, BORDEAUX_SCURO, "b")
        quad_ui(p, (0, .265), (.44, .003), BORDEAUX)
        quad_ui(p, (0, .265), (.018, .018), BORDEAUX).rotation_z = 45
        self.m_domanda = testo_ui(p, "", (0, .17), 1.3, INCHIOSTRO, "i")
        self.m_frammenti = testo_ui(p, "", (0, .045), 2.2, BORDEAUX, "b")
        self.campo = CampoTesto(p, (0, -.07), .64, self._conferma)
        self.m_errore = testo_ui(p, "", (0, -.14), 1.05, C(190, 30, 40), "b")
        self.b_conferma = pulsante(p, "Conferma", (-.15, -.27), (.26, .075), True, self._conferma)
        self.b_chiudi = pulsante(p, "Chiudi", (.16, -.27), (.22, .075), False, self.chiudi_modale)
        self.gruppo_domanda = [self.m_domanda, self.m_frammenti, self.campo, self.m_errore, self.b_conferma, self.b_chiudi]
        # ricompensa
        self.r_sottotitolo = testo_ui(p, "Hai trovato un frammento della chiave finale", (0, .215), 1.1, INCHIOSTRO, "i")
        self.r_sigillo = quad_ui(p, (0, .09), (.24, .24), color.white, self.t_sigillo)
        self.r_frammento = testo_ui(p, "", (0, .09), 2.6, ORO_CHIARO, "b", z=-.01)
        self.r_curiosita_t = testo_ui(p, "Curiosità storica", (0, -.04), 1.3, BORDEAUX, "b")
        self.r_curiosita = testo_ui(p, "", (0, -.11), 1.2, INCHIOSTRO, "i")
        self.b_continua = pulsante(p, "Continua", (0, -.29), (.28, .075), True, self.chiudi_modale)
        self.gruppo_ricompensa = [self.r_sottotitolo, self.r_sigillo, self.r_frammento, self.r_curiosita_t,
                                  self.r_curiosita, self.b_continua]
        self.enigma_aperto = None
        self.fase_modale = None
        self.scuoti = 0.0

    def _costruisci_schermate(self):
        ui = camera.ui
        # introduzione
        self.intro = Entity(parent=ui, enabled=False, z=-6)
        quad_ui(self.intro, (0, 0), (4, 1.2), C(4, 3, 4, 150), z=.3)
        quad_ui(self.intro, (0, .385), (.1, .1), color.white, self.t_coccarda)
        testo_ui(self.intro, "IL SEGRETO DEL CARBONARO", (0, .29), 3.4, ORO, "b")
        quad_ui(self.intro, (0, .235), (.6, .003), ORO_SCURO)
        testo_ui(self.intro, "Torino  ·  4 maggio 1860", (0, .2), 1.4, PERGAMENA, "i")
        quad_ui(self.intro, (0, -.02), (1.3, .38), color.white, self.t_pergamena_larga, z=.1)
        testo_ui(self.intro, TRAMA, (0, -.02), 1.25, INCHIOSTRO, "i", wordwrap=72)
        testo_ui(self.intro, "WASD per muoverti · mouse per guardarti intorno · clic sugli oggetti per esaminarli",
                 (0, -.255), .9, PERGAMENA_SCURA, "i")
        self.b_inizia = pulsante(self.intro, "Inizia la fuga", (0, -.35), (.34, .085), True, self.avvia)
        # vittoria
        self.vittoria_ui = Entity(parent=ui, enabled=False, z=-7)
        quad_ui(self.vittoria_ui, (0, 0), (4, 1.2), color.white, self.t_oro, z=.3)
        self.raggi = quad_ui(self.vittoria_ui, (0, .28), (2.6, 2.6), color.white, self.t_raggi, z=.25)
        quad_ui(self.vittoria_ui, (0, .28), (1.2, 1.2), C(255, 220, 140, 120), self.t_alone, z=.2)
        for i, c in enumerate(TRICOLORE):
            quad_ui(self.vittoria_ui, (-1 + i * .667 + .333, .49), (.667, .02), c)
            quad_ui(self.vittoria_ui, (-1 + i * .667 + .333, -.49), (.667, .02), c)
        testo_ui(self.vittoria_ui, "SEI FUGGITO!", (0, .43), 1.8, PERGAMENA, "b")
        self.v_titolo = quad_ui(self.vittoria_ui, (0, .305), (1.1, .2), color.white, self.t_obbedisco, z=-.02)
        testo_ui(self.vittoria_ui, "La parola d'ordine era giusta: l'uscita segreta si apre sui vicoli di Torino.",
                 (0, .19), 1.1, PERGAMENA, "i")
        self.v_tempo = testo_ui(self.vittoria_ui, "", (0, .15), 1.15, ORO_CHIARO, "b")
        quad_ui(self.vittoria_ui, (0, -.1), (1.3, .38), color.white, self.t_pergamena_larga, z=.1)
        testo_ui(self.vittoria_ui, "Curiosità finale: il telegramma di Garibaldi", (0, .035), 1.45, BORDEAUX_SCURO, "b")
        testo_ui(self.vittoria_ui, CURIOSITA_FINALE, (0, -.105), 1.15, INCHIOSTRO, "i", wordwrap=80)
        testo_ui(self.vittoria_ui, "R: gioca ancora   ·   Esc: esci   ·   F11: schermo intero", (0, -.42), 1.0,
                 PERGAMENA_SCURA, "i")
        self.coriandoli = []
        for _ in range(110):
            c = quad_ui(self.vittoria_ui, (random.uniform(-.9, .9), random.uniform(.5, 1.6)),
                        (random.uniform(.006, .012), random.uniform(.012, .02)),
                        random.choice(TRICOLORE + [ORO]), z=-.05)
            c.vel = Vec2(random.uniform(-.05, .05), -random.uniform(.12, .3))
            c.rot = random.uniform(-300, 300)
            self.coriandoli.append(c)
        # game over
        self.sconfitta_ui = Entity(parent=ui, enabled=False, z=-7)
        quad_ui(self.sconfitta_ui, (0, 0), (4, 1.2), color.white, self.t_rosso, z=.3)
        quad_ui(self.sconfitta_ui, (0, .15), (1.4, 1.4), C(255, 60, 40, 70), self.t_alone, z=.2)
        testo_ui(self.sconfitta_ui, "GAME OVER", (0, .3), 1.9, C(255, 190, 180), "b")
        testo_ui(self.sconfitta_ui, "I gendarmi hanno sfondato la porta!", (0, .19), 3.2, C(250, 244, 236), "b")
        quad_ui(self.sconfitta_ui, (0, .125), (.6, .003), C(255, 160, 150))
        testo_ui(self.sconfitta_ui, "Il tempo è scaduto: sei stato arrestato e il messaggio per Garibaldi non partirà mai.",
                 (0, .08), 1.2, C(255, 214, 206), "i")
        self.s_frammenti = testo_ui(self.sconfitta_ui, "", (0, -.02), 1.4, ORO_CHIARO, "b")
        self.s_lista = testo_ui(self.sconfitta_ui, "", (0, -.09), 2.0, PERGAMENA, "b")
        testo_ui(self.sconfitta_ui, "R: riprova   ·   Esc: esci", (0, -.33), 1.2, C(255, 200, 190), "i")

    # ------------------------------------------------------------------ stato di gioco
    def _reset(self):
        self.risolti = set()
        self.inizio = None
        self.tempo_congelato = None
        self.ultimo_secondo = None
        self.mirato = None
        self.t_chiusura = 0.0
        self.pos = Vec3(0, 0, -1.9)
        self.yaw, self.pitch = 0.0, 0.0
        self.passo = 0.0
        self.t_evento = 0.0
        self.anta.rotation_y = 0
        self.catene.enabled = True
        self.catene.position = (0, 0, -.2)
        self.catene.rotation = (0, 0, 0)
        self.luce_esterna.color = C(255, 236, 180)
        for oid, radice in self.interattivi.items():
            radice.set_shader_input("emissione", Vec3(0, 0, 0))
        for e in getattr(self, "etichette_risolte", []):
            destroy(e)
        self.etichette_risolte = []
        for i, t in enumerate(self.slot):
            t.text = "? ? ?"
            t.color = C(150, 124, 90)
            t.scale = 1.3
        self.velo_colore.color = C(255, 240, 200, 0)
        self.vittoria_ui.enabled = self.sconfitta_ui.enabled = False
        self.modale.enabled = False
        self.pausa.enabled = False

    def _mostra_intro(self):
        self.stato = "intro"
        self.intro.enabled = True
        self.hud.enabled = False
        mouse.locked = False
        mouse.visible = True
        self.suoni.ambiente(True)

    def avvia(self):
        self.suoni.suona("click")
        self._reset()
        self.stato = "gioco"
        self.intro.enabled = False
        self.hud.enabled = True
        self.inizio = time.monotonic()
        self._blocca_mouse(True)
        self.mostra_toast("Il tempo scorre: esamina gli oggetti dello studio.")
        self.suoni.ambiente(True)

    def tempo_rimasto(self):
        if self.tempo_congelato is not None:
            return self.tempo_congelato
        if self.inizio is None:
            return float(TEMPO_TOTALE)
        return max(0.0, TEMPO_TOTALE - (time.monotonic() - self.inizio))

    def _blocca_mouse(self, blocca):
        mouse.locked = blocca
        mouse.visible = not blocca

    def mostra_toast(self, msg, col=ORO_CHIARO):
        self.toast.text = msg
        self.toast.color = col
        self.toast_sfondo.scale_x = self.toast.width + .06
        self.toast_t0 = time.monotonic()

    # ------------------------------------------------------------------ interazione
    def interagisci(self):
        oid = self.mirato
        if oid is None:
            return
        if oid == "porta":
            if len(self.risolti) < len(ENIGMI):
                self.suoni.suona("bloccato")
                self.scuoti = .5
                self.mostra_toast("La porta è sbarrata! Risolvi prima tutti gli enigmi (%d/4)." % len(self.risolti),
                                  ROSSO_ALLARME)
            else:
                self.apri_modale(None)
        elif oid in self.risolti:
            self.mostra_toast("Hai già svelato il segreto: frammento «%s»." % ENIGMI_PER_ID[oid]["frammento"], PERGAMENA)
        else:
            self.apri_modale(ENIGMI_PER_ID[oid])

    def apri_modale(self, enigma):
        self.suoni.suona("click")
        self.enigma_aperto = enigma
        self.fase_modale = "domanda"
        self.modale.enabled = True
        self.pannello.x = 0
        self.pannello.y = -.03
        self.pannello.animate_y(0, duration=.18, curve=curve.out_quad)
        for e in self.gruppo_domanda:
            e.enabled = True
        for e in self.gruppo_ricompensa:
            e.enabled = False
        if enigma is None:
            self.m_titolo.text = "La Porta Uscita"
            self.m_domanda.text = avvolgi("«Inserisci la parola d'ordine unendo i 4 frammenti di chiave trovati.»", 56)
            self.m_frammenti.text = "  ·  ".join(e["frammento"] for e in ENIGMI)
            self.m_titolo.color = BORDEAUX_SCURO
        else:
            self.m_titolo.text = enigma["titolo"]
            self.m_domanda.text = avvolgi("«" + enigma["domanda"] + "»", 56)
            self.m_frammenti.text = ""
            self.m_titolo.color = BORDEAUX_SCURO
        self.m_domanda.y = .17 if enigma else .18
        self.m_errore.text = ""
        self.campo.svuota()
        self.campo.attivo = True
        self._blocca_mouse(False)

    def chiudi_modale(self):
        if not self.modale.enabled:
            return
        self.suoni.suona("click")
        self.modale.enabled = False
        self.campo.attivo = False
        self.enigma_aperto = None
        self.t_chiusura = time.monotonic()      # evita che lo stesso clic riapra subito l'oggetto
        if self.stato == "gioco":
            self._blocca_mouse(True)

    def _conferma(self):
        if self.fase_modale != "domanda" or not self.modale.enabled:
            return
        risposta = self.campo.valore
        if not normalizza(risposta):
            self._errore("Scrivi una risposta prima di confermare.", suono=False)
            return
        enigma = self.enigma_aperto
        if enigma is None:
            if normalizza(risposta) == PAROLA_ORDINE:
                self.modale.enabled = False
                self.campo.attivo = False
                self.fuga()
            else:
                self._errore("Parola d'ordine errata! I gendarmi colpiscono la porta…")
            return
        if risposta_corretta(enigma, risposta):
            self._risolvi(enigma)
        else:
            self._errore("Risposta errata. I passi dei gendarmi si avvicinano…")

    def _errore(self, msg, suono=True):
        self.m_errore.text = msg
        self.scuoti = .45
        self.campo.svuota()
        if suono:
            self.suoni.suona("sbagliato")

    def _risolvi(self, enigma):
        self.risolti.add(enigma["id"])
        self.suoni.suona("giusto")
        self.fase_modale = "ricompensa"
        self.campo.attivo = False
        for e in self.gruppo_domanda:
            e.enabled = False
        for e in self.gruppo_ricompensa:
            e.enabled = True
        self.m_titolo.text = "Enigma risolto!"
        self.m_titolo.color = VERDE_SCURO
        self.r_frammento.text = enigma["frammento"]
        self.r_frammento.scale = 2.0 if len(enigma["frammento"]) > 2 else 3.0
        self.r_curiosita.text = avvolgi(enigma["curiosita"], 58)
        self.r_sigillo.scale = .05
        self.r_sigillo.animate_scale(.24, duration=.35, curve=curve.out_back)
        # l'oggetto risolto si illumina di verde-oro e mostra il suo frammento
        radice = self.interattivi[enigma["id"]]
        radice.set_shader_input("emissione", Vec3(.06, .22, .09))
        i = ENIGMI.index(enigma)
        self.slot[i].text = enigma["frammento"]
        self.slot[i].color = BORDEAUX
        self.slot[i].scale = 1.55
        colli = [c for c in radice.children if getattr(c, "id_oggetto", None)]
        cima = colli[0].world_position + Vec3(0, colli[0].world_scale_y / 2 + .15, 0) if colli else radice.world_position
        alone = sprite_luminoso(self.mondo, cima, (.5, .5), self.t_alone, C(120, 255, 140, 120))
        sigillo = Entity(parent=self.mondo, model="quad", texture=self.t_sigillo_ok, position=cima, scale=.2,
                         shader=unlit_shader, billboard=True)
        sigillo.setTransparency(TransparencyAttrib.MAlpha)
        sigillo.y0 = cima.y
        alone.y0 = cima.y
        self.etichette_risolte += [sigillo, alone]
        if len(self.risolti) == len(ENIGMI):
            invoke(self._sblocca_porta, delay=.8)
            self.mostra_toast("Tutti i frammenti sono tuoi! Le catene della porta sono cadute…")
        else:
            self.mostra_toast("Frammento «%s» trovato! (%d/4)" % (enigma["frammento"], len(self.risolti)), VERDE_CHIARO)

    def _sblocca_porta(self):
        if self.stato != "gioco":
            return
        self.suoni.suona("catene")
        self.catene.animate_position(Vec3(0, -2.2, -.3), duration=.9, curve=curve.in_quad)
        self.catene.animate_rotation(Vec3(0, 0, 25), duration=.9, curve=curve.in_quad)
        invoke(setattr, self.catene, "enabled", False, delay=1.0)
        self.interattivi["porta"].set_shader_input("emissione", Vec3(.12, .1, .03))

    def fuga(self):
        """Parola d'ordine corretta: la porta si apre e si esce verso la luce."""
        self.tempo_congelato = self.tempo_rimasto()
        self.stato = "fuga"
        self.t_evento = time.monotonic()
        self._blocca_mouse(False)
        self.hud.enabled = False
        self.suoni.suona("porta")
        self.anta.animate_rotation_y(105, duration=2.2, curve=curve.in_out_sine)
        for i in self.indice_luce_porta:
            self.luci[i]["base"] = Vec3(3.0, 2.6, 1.8)

    def vittoria(self):
        self.stato = "vittoria"
        self.t_evento = time.monotonic()
        self.suoni.suona("vittoria")
        self.v_tempo.text = ("Tempo rimasto: %s  ·  Il messaggio raggiungerà Quarto prima che Garibaldi salpi!"
                             % formatta_tempo(self.tempo_congelato or 0))
        self.vittoria_ui.enabled = True
        self.v_titolo.scale = (1.8, .33)
        self.v_titolo.animate_scale(Vec3(1.1, .2, 1), duration=.8, curve=curve.out_back)
        for c in self.coriandoli:
            c.position = (random.uniform(-.9, .9), random.uniform(.55, 1.6))
        self.velo_colore.animate_color(C(255, 240, 200, 0), duration=.8)
        try:
            if not window.fullscreen:
                window.fullscreen = True
        except Exception:
            pass

    def irruzione(self):
        """Tempo scaduto: i gendarmi sfondano la porta."""
        self.tempo_congelato = 0.0
        self.stato = "irruzione"
        self.t_evento = time.monotonic()
        self.modale.enabled = False
        self.campo.attivo = False
        self.hud.enabled = False
        self._blocca_mouse(False)
        self.suoni.suona("sconfitta")
        self.catene.enabled = False
        self.anta.animate_rotation_y(100, duration=.25, curve=curve.out_expo)
        self.luce_esterna.color = C(255, 120, 60)
        for i in self.indice_luce_porta:
            self.luci[i]["base"] = Vec3(3.2, 1.2, .5)
        self.velo_colore.color = C(255, 30, 20, 190)
        self.velo_colore.animate_color(C(255, 30, 20, 0), duration=.9)

    def sconfitta(self):
        self.stato = "sconfitta"
        self.s_frammenti.text = "Frammenti della chiave recuperati: %d/4" % len(self.risolti)
        self.s_lista.text = "   ".join(e["frammento"] if e["id"] in self.risolti else "???" for e in ENIGMI)
        self.sconfitta_ui.enabled = True

    # ------------------------------------------------------------------ input
    def input(self, key):
        if key == "escape":
            if self.stato in ("vittoria", "sconfitta"):
                application.quit()
            elif self.modale.enabled:
                self.chiudi_modale()
            elif self.stato == "gioco" and mouse.locked:
                self._blocca_mouse(False)
            return
        if self.stato in ("vittoria", "sconfitta") and key == "r":
            if window.fullscreen and self.stato == "vittoria":
                window.fullscreen = False
            self.avvia()
            return
        if self.stato == "intro" and key in ("enter", "space"):
            self.avvia()
            return
        if self.stato != "gioco" or self.modale.enabled:
            return
        if key == "m":
            self.suoni.attivo = not self.suoni.attivo
            self.suoni.ambiente(self.suoni.attivo)
            self.mostra_toast("Audio " + ("attivato" if self.suoni.attivo else "disattivato"), PERGAMENA)
        elif key == "left mouse down":
            if not mouse.locked:
                self._blocca_mouse(True)
            elif time.monotonic() - self.t_chiusura > .3:
                self.interagisci()

    # ------------------------------------------------------------------ aggiornamento
    def update(self):
        dt = min(time.dt, .05)
        t = time.monotonic()
        self._aggiorna_luci(t)
        if self.stato == "intro":
            a = t * .08
            camera.position = (math.sin(a) * 2.2, 1.9, math.cos(a) * 2.2 - .3)
            camera.look_at(Vec3(0, 1.3, .3))
        elif self.stato == "gioco":
            rimasto = self.tempo_rimasto()
            if rimasto <= 0:
                self.irruzione()
            else:
                sec = int(math.ceil(rimasto))
                if sec != self.ultimo_secondo:
                    if self.ultimo_secondo is not None and sec <= 60:
                        self.suoni.suona("tick")
                    self.ultimo_secondo = sec
                if not self.modale.enabled and mouse.locked:
                    self._muovi(dt)
                self._applica_camera()
                self._aggiorna_mira()
        elif self.stato == "fuga":
            e = t - self.t_evento
            u = min(1.0, max(0.0, (e - .6) / 2.4))
            u = u * u * (3 - 2 * u)
            inizio = Vec3(self.pos.x, ALTEZZA_OCCHI, self.pos.z)
            camera.position = lerp(inizio, Vec3(0, 1.55, 3.6), u)
            camera.look_at(Vec3(0, 1.4, 4.5))
            if e > 2.2:
                self.velo_colore.color = C(255, 240, 200, int(255 * min(1.0, (e - 2.2) / .8)))
            if e > 3.1:
                self.vittoria()
        elif self.stato == "irruzione":
            e = t - self.t_evento
            forza = max(0.0, 1 - e / 1.2) * .06
            self._applica_camera()
            camera.position += Vec3(random.uniform(-forza, forza), random.uniform(-forza, forza), 0)
            if e > 1.6:
                self.sconfitta()
        elif self.stato == "vittoria":
            self.raggi.rotation_z += dt * 6
            for c in self.coriandoli:
                c.x += c.vel.x * dt
                c.y += c.vel.y * dt
                c.rotation_z += c.rot * dt
                if c.y < -.6:
                    c.y = random.uniform(.55, .7)
                    c.x = random.uniform(-.9, .9)
        self._aggiorna_hud(t, dt)
        self._aggiorna_ambiente(t, dt)

    def _muovi(self, dt):
        self.yaw += mouse.velocity[0] * SENSIBILITA_MOUSE
        self.pitch = max(-80, min(80, self.pitch - mouse.velocity[1] * SENSIBILITA_MOUSE))
        avanti = held_keys["w"] + held_keys["up arrow"] - held_keys["s"] - held_keys["down arrow"]
        lato = held_keys["d"] + held_keys["right arrow"] - held_keys["a"] - held_keys["left arrow"]
        if not avanti and not lato:
            return
        ry = math.radians(self.yaw)
        fwd = Vec3(math.sin(ry), 0, math.cos(ry))
        dx = Vec3(math.cos(ry), 0, -math.sin(ry))
        mov = (fwd * avanti + dx * lato)
        if mov.length() > 0:
            mov = mov.normalized() * VELOCITA * dt
        for asse in ("x", "z"):
            nuovo = Vec3(self.pos)
            setattr(nuovo, asse, getattr(nuovo, asse) + getattr(mov, asse))
            if self._libero(nuovo.x, nuovo.z):
                self.pos = nuovo
        self.passo += dt * 9

    def _libero(self, x, z, raggio=.28):
        if not (-3.72 < x < 3.72 and -3.5 < z < 3.55):
            return False
        for (x0, z0, x1, z1) in self.ostacoli:
            if x0 - raggio < x < x1 + raggio and z0 - raggio < z < z1 + raggio:
                return False
        return True

    def _applica_camera(self):
        camera.position = Vec3(self.pos.x, ALTEZZA_OCCHI + math.sin(self.passo) * .025, self.pos.z)
        camera.rotation = (self.pitch, self.yaw, 0)

    def _aggiorna_mira(self):
        mirato = None
        if not self.modale.enabled:
            hit = raycast(camera.world_position, camera.forward, distance=DISTANZA_INTERAZIONE)
            if hit.hit:
                mirato = getattr(hit.entity, "id_oggetto", None)
        if mirato != self.mirato:
            if self.mirato and self.mirato not in self.risolti:
                self.interattivi[self.mirato].set_shader_input(
                    "emissione", Vec3(.12, .1, .03) if (self.mirato == "porta" and len(self.risolti) == 4) else Vec3(0, 0, 0))
            if mirato and mirato not in self.risolti:
                self.interattivi[mirato].set_shader_input("emissione", Vec3(.22, .17, .08))
            self.mirato = mirato
        self.mirino_anello.enabled = mirato is not None
        self.sugg_sfondo.enabled = mirato is not None
        if mirato is None:
            self.suggerimento.text = self.suggerimento2.text = ""
        elif mirato == "porta":
            self.suggerimento.text = "Porta Uscita"
            self.suggerimento2.text = ("Clic per inserire la parola d'ordine" if len(self.risolti) == 4 else
                                       "Sbarrata  ·  %d/4 frammenti" % len(self.risolti))
        else:
            e = ENIGMI_PER_ID[mirato]
            self.suggerimento.text = e["nome"]
            self.suggerimento2.text = ("Risolto  ·  frammento «%s»" % e["frammento"] if mirato in self.risolti else
                                       "Clic per esaminare")
        if mirato is not None:
            self.sugg_sfondo.scale_x = max(self.suggerimento.width, self.suggerimento2.width) + .05

    def _aggiorna_luci(self, t):
        for i, l in enumerate(self.luci):
            k = 1 + l["tremolio"] * (.5 * math.sin(t * 9.1 + l["fase"]) + .3 * math.sin(t * 23.7 + l["fase"] * 2)
                                     + .2 * math.sin(t * 5.3 + l["fase"] * 3))
            c = l["base"] * k
            self.luci_col[i] = LVecBase3f(c.x, c.y, c.z)
        scene.set_shader_input("cam_pos", camera.world_position)

    def _aggiorna_ambiente(self, t, dt):
        for f in self.fiamme:
            spr, alone, s0, a0, fase = f
            k = 1 + .12 * math.sin(t * 13 + fase) + .08 * math.sin(t * 29 + fase)
            spr.scale = Vec3(s0.x * (2 - k), s0.y * k, 1)
            if alone is not None:
                alone.scale = a0 * (0.94 + .08 * math.sin(t * 7 + fase))
        for g in self.polvere:
            g.position += g.vel * dt
            if abs(g.x) > 3.8 or abs(g.z) > 3.8 or g.y < .1 or g.y > 3.2:
                g.position = (random.uniform(-3.5, 3.5), random.uniform(.3, 3), random.uniform(-3.5, 3.5))
        rimasto = self.tempo_rimasto()
        # le lancette dell'orologio da camino segnano il tempo che resta
        self.lancette[0].rotation_z = -(rimasto / 3600) * 360
        self.lancette[1].rotation_z = -(rimasto % 60) * 6
        self.globo.rotation_y += dt * 12
        for k, e in enumerate(self.etichette_risolte):
            e.y = e.y0 + .04 * math.sin(t * 2 + k // 2)

    def _aggiorna_hud(self, t, dt):
        a = window.aspect_ratio
        self.vignetta.scale_x = a * 1.06
        self.coccarda.x = -a / 2 + .06
        self.titolo.x = self.sottotitolo.x = -a / 2 + .11
        for e in (self.pannello_timer, self.etichetta_timer, self.testo_timer, self.barra_tempo):
            e.x = a / 2 - .18
        self.aiuto.x = a / 2 - .02
        self.sottotitolo.text = "Torino, 4 maggio 1860  ·  Studio segreto della Carboneria  ·  Enigmi risolti: %d/4" % len(self.risolti)
        rimasto = self.tempo_rimasto()
        self.testo_timer.text = formatta_tempo(rimasto)
        frac = rimasto / TEMPO_TOTALE
        self.barra_tempo.scale_x = .28 * frac
        self.barra_tempo.x = a / 2 - .18 - .14 * (1 - frac)
        if rimasto <= 60:
            self.testo_timer.color = lerp(ROSSO_ALLARME, C(255, 200, 190), (math.sin(t * 8) + 1) / 4)
            self.barra_tempo.color = ROSSO_ALLARME
        elif rimasto <= 300:
            self.testo_timer.color = C(236, 140, 60)
            self.barra_tempo.color = C(236, 140, 60)
        else:
            self.testo_timer.color = ORO_CHIARO
            self.barra_tempo.color = ORO
        eta = t - self.toast_t0
        vis = eta < 4.0
        self.toast.enabled = self.toast_sfondo.enabled = vis
        if vis:
            alpha = 1.0 if eta < 3.2 else (4.0 - eta) / .8
            self.toast.alpha = alpha
            self.toast_sfondo.alpha = .8 * alpha
        self.pausa.enabled = self.stato == "gioco" and not self.modale.enabled and not mouse.locked
        self.mirino.enabled = self.stato == "gioco" and not self.modale.enabled
        if self.scuoti > 0:
            self.scuoti = max(0.0, self.scuoti - dt)
            dx = math.sin(self.scuoti * 70) * .02 * (self.scuoti / .45)
            self.pannello.x = dx if self.modale.enabled else 0
            if not self.modale.enabled:
                self.anta.rotation_y = dx * 60 if self.stato == "gioco" and len(self.risolti) < 4 else self.anta.rotation_y


def main():
    app = Ursina(title="Il Segreto del Carbonaro", borderless=False, development_mode=False, vsync=True)
    window.color = color.black
    gioco = Gioco()
    try:
        app.run()
    finally:
        gioco.suoni.pulisci()


if __name__ == "__main__":
    main()
