# Reporte de sensores → Telegram

Envía a Telegram una tarjeta visual por estación con la última lectura y semáforo por variable
(🟢 óptimo · 🟡 atención · 🔴 alerta), además de un aviso si un equipo deja de comunicar.

## Archivos
| Archivo | Para qué |
|---|---|
| `enviar_reporte.py` | Lee los datos, dibuja la tarjeta y la envía |
| `estaciones.json` | Estaciones, variables, unidades y **rangos óptimos/alerta** (edítalo aquí) |
| `.github/workflows/reporte_telegram.yml` | Horarios de envío en GitHub Actions |

## Puesta en marcha (10 min)

1. **Crear el bot:** en Telegram abre **@BotFather** → `/newbot` → copia el *token*.
2. **Obtener el chat_id:** agrega el bot a tu grupo y escribe cualquier mensaje. Luego abre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` y copia el número de `"chat":{"id": ...}`
   (en grupos empieza con `-100`).
3. **Subir esta carpeta** a un repositorio de GitHub (puede ser privado).
4. **Guardar los secretos:** en el repo, *Settings → Secrets and variables → Actions → New repository secret*:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. **Probar:** pestaña *Actions → Reporte de sensores a Telegram → Run workflow*, marca **demo** y ejecútalo.
   Te llegarán las tarjetas de ejemplo.

## Conectar los datos reales
El script lee la última fila de cada estación desde un archivo `.xlsx` o `.csv` en Google Drive.

1. Comparte el archivo como **"Cualquier persona con el enlace – Lector"**.
2. Copia su ID (lo que va entre `/d/` y `/view` en el enlace) en `estaciones.json` → `fuentes`.
3. Ajusta `columna_estacion`, `columna_fecha` y la `columna` de cada variable a los encabezados del archivo.
4. En `estaciones`, pon `"activa": true` en las que quieras recibir.

Cuando subas más datos al mismo archivo, el siguiente envío ya toma la lectura nueva.

> Ya viene configurada la fuente `drive_termometros` con tu archivo *TERMÓMETROS MONITOREO.xlsx*
> (estación *Cerro Papaa*, desactivada porque sus datos más recientes son de 2024).
> Para los sensores de suelo (vvm0000X) falta el ID del archivo donde exportes sus datos.

## Horarios (hora de Guatemala)
- 07:07 y 18:07 → reporte completo
- cada 2 h → **solo si hay alertas** (si todo está bien, no envía nada)

Para cambiarlos, edita las líneas `cron` (están en UTC: hora de Guatemala + 6).

## Ajustar los rangos
Cada variable tiene `optimo` [mín, máx] y `alerta` [mín, máx]. Dentro del óptimo es verde,
fuera del rango de alerta es rojo, y en medio es amarillo. Los valores incluidos son de referencia
general: ajústalos al cultivo y suelo de cada sitio.

## Probar en tu computadora
```bash
pip install -r requirements.txt
DEMO=1 SOLO_IMAGEN=1 python enviar_reporte.py   # genera las imágenes en ./salida
```
