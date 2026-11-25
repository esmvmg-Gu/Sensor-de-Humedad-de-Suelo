"""
Reporte de sensores -> Telegram
Genera una tarjeta visual por estación y la envía a un chat/grupo de Telegram.

Variables de entorno (en GitHub: Settings > Secrets and variables > Actions):
  TELEGRAM_TOKEN    token del bot (de @BotFather)            [obligatorio salvo SOLO_IMAGEN]
  TELEGRAM_CHAT_ID  id del chat o grupo (ej. -1001234567890) [obligatorio salvo SOLO_IMAGEN]
  MODO              "reporte" (todo) | "alertas" (solo envía si hay alertas)   por defecto: reporte
  DEMO              "1" usa los valores de ejemplo del JSON en lugar de Drive
  SOLO_IMAGEN       "1" solo genera las imágenes en ./salida sin enviarlas
"""
import io
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "estaciones.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CONFIG.get("zona_horaria", "America/Guatemala"))

# ---------- Paleta ----------
C = {
    "fondo":   "#F3EFE6",
    "header":  "#1E3B2C",
    "header2": "#2F5A41",
    "tarjeta": "#FFFFFF",
    "borde":   "#E4DED1",
    "texto":   "#1F2A24",
    "suave":   "#6B7A70",
    "riel":    "#ECE7DC",
    "banda":   "#CFE5D3",
    "ok":      "#2E9D5B",
    "warn":    "#E0A21B",
    "bad":     "#D2483C",
    "nd":      "#A8B0AA",
    "crema":   "#F7E9C8",
}
ESTADO_TXT = {"ok": "Óptimo", "warn": "Atención", "bad": "Alerta", "nd": "Sin dato"}
ESTADO_EMOJI = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}


# ================= DATOS =================
_cache_fuentes = {}


def leer_fuente(nombre):
    if nombre in _cache_fuentes:
        return _cache_fuentes[nombre]
    f = CONFIG["fuentes"][nombre]
    if f["tipo"] != "drive":
        raise ValueError(f"Tipo de fuente no soportado: {f['tipo']}")
    url = f"https://drive.google.com/uc?export=download&id={f['drive_file_id']}"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    if r.content[:15].lstrip().lower().startswith(b"<!doctype html") or b"<html" in r.content[:200].lower():
        raise RuntimeError(
            f"Drive no devolvió el archivo de '{nombre}'. Compártelo como "
            "'Cualquier persona con el enlace – Lector'."
        )
    contenido = io.BytesIO(r.content)
    if r.content[:2] == b"PK":   # xlsx
        df = pd.read_excel(contenido, sheet_name=f.get("hoja", 0))
    else:                         # csv
        df = pd.read_csv(contenido)
    df.columns = [str(c).strip() for c in df.columns]
    df[f["columna_fecha"]] = pd.to_datetime(df[f["columna_fecha"]], errors="coerce")
    _cache_fuentes[nombre] = (df, f)
    return df, f


def ultima_lectura(est):
    """Devuelve (fecha datetime con tz, dict columna->valor)."""
    if os.getenv("DEMO") == "1":
        d = dict(CONFIG["demo"][est["filtro"]])
        fecha = datetime.strptime(d.pop("fecha"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
        return fecha, d
    df, f = leer_fuente(est["fuente"])
    sub = df[df[f["columna_estacion"]].astype(str).str.strip() == str(est["filtro"])]
    sub = sub.dropna(subset=[f["columna_fecha"]])
    if sub.empty:
        return None, {}
    fila = sub.sort_values(f["columna_fecha"]).iloc[-1]
    fecha = fila[f["columna_fecha"]].to_pydatetime()
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=TZ)
    return fecha, fila.to_dict()


def num(v):
    try:
        v = float(str(v).replace(",", "."))
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def evaluar(valor, var):
    if valor is None:
        return "nd"
    lo, hi = var["optimo"]
    alo, ahi = var["alerta"]
    if lo <= valor <= hi:
        return "ok"
    if valor < alo or valor > ahi:
        return "bad"
    return "warn"


def fmt(valor, var):
    if valor is None:
        return "—"
    return f"{valor:,.{var['decimales']}f}"


# ================= TARJETA =================
W = 1080
TH, GAP, HEAD = 220, 28, 240


def caja(ax, x, y, w, h, color, r=26, ec=None, lw=0, z=1):
    ax.add_patch(FancyBboxPatch((x + r, y + r), w - 2 * r, h - 2 * r,
                                boxstyle=f"round,pad={r}", fc=color,
                                ec=ec or color, lw=lw, zorder=z))


def tarjeta(est, perfil, fecha, fila, conectado):
    n = len(perfil["variables"])
    filas = math.ceil(n / 2)
    H = HEAD + 40 + filas * TH + (filas - 1) * GAP + 150
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, fc=C["fondo"], zorder=0))

    # ---- Encabezado
    hdr = Rectangle((0, H - HEAD), W, HEAD, fc=C["header"], zorder=1)
    ax.add_patch(hdr)
    for i, a in enumerate([0.10, 0.07, 0.05]):           # ondas decorativas
        c = Circle((W - 60 + i * 40, H + i * 30), 260 + i * 90,
                   fc=C["header2"], alpha=a * 3, zorder=1)
        ax.add_patch(c); c.set_clip_path(hdr)
    ax.text(60, H - 58, f"{perfil['titulo']}  ·  {CONFIG['organizacion'].upper()}",
            color=C["crema"], fontsize=15, fontweight="bold", zorder=3)
    ax.text(60, H - 130, est["nombre"], color="white", fontsize=36,
            fontweight="bold", zorder=3)
    ax.text(60, H - 175, f"ID {est['id']}   ·   {est['equipo']}",
            color="#BFD3C5", fontsize=16, zorder=3)
    fecha_txt = fecha.astimezone(TZ).strftime("%d/%m/%Y  %H:%M") if fecha else "sin registros"
    ax.text(60, H - 215, f"Última lectura: {fecha_txt}", color="#BFD3C5", fontsize=16, zorder=3)

    # pill de conexión
    pc = C["ok"] if conectado else C["bad"]
    ptxt = "EN LÍNEA" if conectado else "SIN COMUNICACIÓN"
    pw = 190 if conectado else 300
    caja(ax, W - 60 - pw, H - 88, pw, 54, pc, r=27, z=3)
    ax.add_patch(Circle((W - 60 - pw + 30, H - 61), 8, fc="white", zorder=4))
    ax.text(W - 60 - pw + 50, H - 61, ptxt, color="white", fontsize=15,
            fontweight="bold", va="center", zorder=4)

    # ---- Mosaicos
    vars_ = perfil["variables"]
    m, gap, th = 50, GAP, TH
    top = H - HEAD - 40
    tw = (W - 2 * m - gap) / 2
    estados = []

    for i, var in enumerate(vars_):
        fi, co = divmod(i, 2)
        ancho = W - 2 * m if (i == n - 1 and n % 2 == 1) else tw
        x = m + co * (tw + gap)
        y = top - (fi + 1) * th - fi * gap
        val = num(fila.get(var["columna"]))
        est_v = evaluar(val, var)
        estados.append((var, val, est_v))
        col = C[est_v]

        caja(ax, x, y, ancho, th, C["tarjeta"], r=24, ec=C["borde"], lw=1.2, z=2)
        ax.add_patch(Rectangle((x, y + 24), 8, th - 48, fc=col, zorder=3))  # acento

        ax.text(x + 34, y + th - 46, var["etiqueta"].upper(), color=C["suave"],
                fontsize=14, fontweight="bold", zorder=4)
        # estado
        te = ax.text(x + ancho - 34, y + th - 40, ESTADO_TXT[est_v], color=col,
                     fontsize=14, fontweight="bold", va="center", ha="right", zorder=4)
        fig.canvas.draw()
        bx0 = te.get_window_extent().transformed(ax.transData.inverted()).x0
        ax.add_patch(Circle((bx0 - 18, y + th - 40), 9, fc=col, zorder=4))

        # valor grande + unidad
        t = ax.text(x + 34, y + th * 0.42, fmt(val, var),
                    color=C["texto"] if val is not None else C["nd"],
                    fontsize=46, fontweight="bold", zorder=4)
        fig.canvas.draw()
        bb = t.get_window_extent().transformed(ax.transData.inverted())
        ax.text(bb.x1 + 12, y + th * 0.42 + 6, var["unidad"], color=C["suave"],
                fontsize=20, zorder=4)

        # barra de rango
        bx, bw, by, bh = x + 34, ancho - 68, y + 44, 14
        e0, e1 = var["escala"]
        px = lambda v: bx + (min(max(v, e0), e1) - e0) / (e1 - e0) * bw
        caja(ax, bx, by, bw, bh, C["riel"], r=7, z=4)
        caja(ax, px(var["optimo"][0]), by, max(px(var["optimo"][1]) - px(var["optimo"][0]), 14),
             bh, C["banda"], r=7, z=5)
        if val is not None:
            ax.add_patch(Circle((px(val), by + bh / 2), 14, fc=col, ec="white", lw=3, zorder=6))
        ax.text(bx, by - 18, f"{e0:g}", color=C["suave"], fontsize=10, va="top", zorder=4)
        ax.text(bx + bw, by - 18, f"{e1:g}", color=C["suave"], fontsize=10, va="top",
                ha="right", zorder=4)

    # ---- Pie
    nb = sum(1 for _, _, e in estados if e == "bad")
    nw = sum(1 for _, _, e in estados if e == "warn")
    resumen = ("Todo en rango óptimo" if nb + nw == 0
               else f"{nb} en alerta · {nw} en atención")
    ax.text(60, 80, resumen, color=C["texto"], fontsize=17, fontweight="bold")
    ax.add_patch(Rectangle((W - 260, 74), 40, 14, fc=C["banda"]))
    ax.text(W - 210, 81, "rango óptimo", color=C["suave"], fontsize=13, va="center")
    ahora = datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    ax.text(60, 42, f"Generado {ahora}", color=C["suave"], fontsize=12)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf, estados


def leyenda(est, perfil, fecha, estados, conectado):
    fecha_txt = fecha.astimezone(TZ).strftime("%d/%m/%Y %H:%M") if fecha else "sin registros"
    lineas = [f"🌱 <b>{est['nombre']}</b>", f"<code>{est['id']}</code> · 🕐 {fecha_txt}", ""]
    if not conectado:
        lineas.insert(2, f"📡 <b>Sin comunicación</b> desde hace más de {CONFIG['horas_sin_datos']} h")
    for var, val, e in estados:
        lineas.append(f"{ESTADO_EMOJI[e]} {var['etiqueta']}: <b>{fmt(val, var)}</b> {var['unidad']}".rstrip())
    malas = [(v, x, e) for v, x, e in estados if e in ("bad", "warn")]
    if malas:
        lineas += ["", "⚠️ <b>Revisar:</b> " + ", ".join(v["etiqueta"] for v, _, _ in malas)]
    return "\n".join(lineas)[:1024]


# ================= TELEGRAM =================
def enviar(imagen, texto):
    token = os.environ["TELEGRAM_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data={"chat_id": chat, "caption": texto, "parse_mode": "HTML"},
        files={"photo": ("reporte.png", imagen, "image/png")},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"Telegram respondió {r.status_code}: {r.text}")


def main():
    modo = os.getenv("MODO", "reporte")
    solo_img = os.getenv("SOLO_IMAGEN") == "1"
    salida = BASE / "salida"; salida.mkdir(exist_ok=True)
    errores = 0
    for est in CONFIG["estaciones"]:
        if not est.get("activa", True):
            continue
        perfil = CONFIG["perfiles"][est["perfil"]]
        try:
            fecha, fila = ultima_lectura(est)
            ref = datetime.now(TZ) if os.getenv("DEMO") != "1" else datetime(2026, 11, 24, 22, 55, tzinfo=TZ)
            conectado = fecha is not None and (ref - fecha).total_seconds() < CONFIG["horas_sin_datos"] * 3600
            img, estados = tarjeta(est, perfil, fecha, fila, conectado)
            hay_alerta = (not conectado) or any(e in ("bad", "warn") for _, _, e in estados)
            if modo == "alertas" and not hay_alerta:
                print(f"✓ {est['nombre']}: sin alertas, no se envía")
                continue
            texto = leyenda(est, perfil, fecha, estados, conectado)
            (salida / f"{est['id'].replace(' ', '_')}.png").write_bytes(img.getvalue())
            if solo_img:
                print(f"🖼  {est['nombre']}: imagen guardada")
            else:
                enviar(img, texto)
                print(f"📨 {est['nombre']}: enviado")
        except Exception as ex:  # una estación con error no detiene a las demás
            errores += 1
            print(f"✗ {est['nombre']}: {ex}", file=sys.stderr)
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
