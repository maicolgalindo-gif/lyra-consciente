#!/usr/bin/env bash
# La voz de Lyra, siempre encendida.
#
# Lyra habla con VoiceStudio, que corre fuera del contenedor (necesita la GPU de
# la maquina). Si VoiceStudio esta cerrado, Lyra se queda sin voz propia. Este
# script deja ese arranque instalado como servicio del sistema: se levanta solo
# al iniciar sesion y vuelve a levantarse si se cae.
#
# Vive aqui, en el repo, y no en la maquina de nadie: quien instale Lyra en otro
# equipo corre esto mismo y queda igual. Si VoiceStudio no esta, lo clona el.
#
# Por que no va dentro del contenedor de Lyra: la voz necesita la GPU y un
# contenedor de Linux no alcanza la GPU de un Mac (lo dice la propia
# documentacion de VoiceStudio). Metida ahi correria en CPU y cada frase pasaria
# de segundos a minutos. En un servidor Linux con GPU si tendria sentido, y ahi
# este mismo script instala el servicio con systemd.
#
#   bash scripts/voz-servicio.sh instalar    # la instala si falta, y la deja andando
#   bash scripts/voz-servicio.sh estado      # si esta vivo y responde
#   bash scripts/voz-servicio.sh quitar      # lo desinstala
#
# Donde esta VoiceStudio se busca solo; si lo tienes en otro lado:
#   VOICESTUDIO_HOME=/ruta/a/VoiceStudio bash scripts/voz-servicio.sh instalar

set -euo pipefail

# El nombre del servicio. Se puede cambiar para probar sin pisar el que esta
# andando: con la misma etiqueta, launchctl reemplaza al de verdad.
ETIQUETA="${LYRA_VOZ_ETIQUETA:-com.lyra.voicestudio}"
PUERTO="${LYRA_VOZ_PUERTO:-3900}"
URL="http://127.0.0.1:${PUERTO}"
# Por defecto suelta el modelo a los 5 min sin usarlo y la frase siguiente tarda
# el doble. Una hora cubre una jornada sin dejarlo ocupando memoria de noche.
IDLE="${LYRA_VOZ_IDLE:-3600}"

REPO_VOZ="${LYRA_VOZ_REPO:-https://github.com/debpalash/VoiceStudio.git}"
# Donde Lyra guarda su voz cuando se la instala ella misma. No va dentro del repo
# a proposito: son varios giga entre el codigo y los modelos, y meterlos en el
# repo de Lyra lo volveria inmanejable. El que manda sigue siendo este script.
CASA_VOZ="${LYRA_VOZ_CASA:-$HOME/.lyra/voz/VoiceStudio}"

buscar_voicestudio() {
	if [ -n "${VOICESTUDIO_HOME:-}" ]; then echo "$VOICESTUDIO_HOME"; return; fi
	for d in "$CASA_VOZ" "$HOME/VoiceStudio" "$HOME/VoiceStudio-clone/VoiceStudio" \
			 "$HOME/Developer/VoiceStudio" "$HOME/code/VoiceStudio"; do
		[ -f "$d/backend/main.py" ] && { echo "$d"; return; }
	done
	return 1
}

traer_voicestudio() {
	command -v git >/dev/null || { echo "Falta «git» para traer la voz." >&2; return 1; }
	echo "No tenías la voz instalada. La traigo de $REPO_VOZ" >&2
	echo "(son varios giga: código y, la primera vez que hable, los modelos)" >&2
	mkdir -p "$(dirname "$CASA_VOZ")"
	git clone --depth 1 "$REPO_VOZ" "$CASA_VOZ" >&2 || return 1
	echo "$CASA_VOZ"
}

buscar_uv() {
	command -v uv 2>/dev/null && return
	for p in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
		[ -x "$p" ] && { echo "$p"; return; }
	done
	return 1
}

# La voz de Lyra viaja con Lyra: voz/marcela.omnivoice es el perfil exportado de
# VoiceStudio (su audio de referencia y sus datos, 92 KB). Al instalar se mete en
# el VoiceStudio de esta maquina, asi que Marcela esta en cualquier equipo donde
# se instale Lyra, sin volver a clonarla a mano.
BUNDLE_VOZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voz/marcela.omnivoice"
NOMBRE_VOZ="${LYRA_VOZ_NOMBRE:-marcela!}"
VOZ_ID=""

id_de_la_voz() {
	curl -sf --max-time 10 "$URL/profiles" 2>/dev/null | NOMBRE="$NOMBRE_VOZ" python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
perfiles = d if isinstance(d, list) else (d.get("profiles") or [])
for p in perfiles:
    if isinstance(p, dict) and p.get("name") == os.environ["NOMBRE"]:
        print(p.get("id") or p.get("profile_id") or "")
        break
' 2>/dev/null
}

poner_la_voz() {
	VOZ_ID="$(id_de_la_voz || true)"
	if [ -n "$VOZ_ID" ]; then
		echo "La voz «${NOMBRE_VOZ}» ya estaba aquí: $VOZ_ID"
		return 0
	fi
	if [ ! -f "$BUNDLE_VOZ" ]; then
		echo "No encontré la voz en $BUNDLE_VOZ" >&2
		return 1
	fi
	echo "Instalando la voz «${NOMBRE_VOZ}» en VoiceStudio…"
	curl -sf --max-time 180 -X POST "$URL/marketplace/import" -F "file=@${BUNDLE_VOZ}" >/dev/null \
		|| { echo "No se pudo instalar la voz." >&2; return 1; }
	VOZ_ID="$(id_de_la_voz || true)"
	[ -n "$VOZ_ID" ] || { echo "La importé pero no la encuentro." >&2; return 1; }
	echo "Voz instalada: $VOZ_ID"
}

# Si Lyra corre en Docker en esta misma maquina, se le deja configurada la voz.
contarle_a_lyra() {
	local id="$1"
	local sitio="${LYRA_SITIO:-erp.local}"
	local contenedor="${LYRA_CONTENEDOR:-lyra-erx-bench}"
	[ -n "$id" ] || return 0
	command -v docker >/dev/null 2>&1 || return 0
	docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$contenedor" || return 0
	VOZ_ID="$id" SITIO="$sitio" PUERTO="$PUERTO" docker exec -i -e VOZ_ID -e SITIO -e PUERTO "$contenedor" \
		bash -lc 'cd /home/frappe/frappe-bench/sites && ../env/bin/python -c "
import os, frappe
frappe.init(site=os.environ[\"SITIO\"]); frappe.connect()
frappe.db.set_single_value(\"IA Ajustes\", \"voz_url\", \"http://host.docker.internal:\" + os.environ[\"PUERTO\"])
frappe.db.set_single_value(\"IA Ajustes\", \"voz_id\", os.environ[\"VOZ_ID\"])
frappe.db.set_single_value(\"IA Ajustes\", \"voz_activa\", 1)
frappe.db.commit(); frappe.clear_cache()
print(\"  Lyra ya sabe cuál es su voz.\")
"' 2>/dev/null || true
}

estado() {
	if curl -sf --max-time 3 "$URL/health" >/dev/null 2>&1; then
		echo "La voz de Lyra responde en $URL"
		curl -sf "$URL/health" && echo
	else
		echo "La voz de Lyra NO responde en $URL" >&2
		return 1
	fi
}

instalar_mac() {
	local casa="$1" uv="$2"
	local plist="$HOME/Library/LaunchAgents/${ETIQUETA}.plist"
	mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/Lyra"
	cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key><string>${ETIQUETA}</string>
	<key>ProgramArguments</key>
	<array>
		<string>${uv}</string><string>run</string><string>uvicorn</string>
		<string>main:app</string><string>--app-dir</string><string>backend</string>
		<string>--host</string><string>127.0.0.1</string>
		<string>--port</string><string>${PUERTO}</string>
	</array>
	<key>WorkingDirectory</key><string>${casa}</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key><string>$(dirname "$uv"):/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
		<key>HOME</key><string>${HOME}</string>
		<key>OMNIVOICE_SIDECAR_IDLE_TIMEOUT_S</key><string>${IDLE}</string>
	</dict>
	<key>RunAtLoad</key><true/>
	<key>KeepAlive</key><true/>
	<key>ProcessType</key><string>Adaptive</string>
	<key>StandardOutPath</key><string>${HOME}/Library/Logs/Lyra/voicestudio.log</string>
	<key>StandardErrorPath</key><string>${HOME}/Library/Logs/Lyra/voicestudio.log</string>
</dict>
</plist>
PLIST
	plutil -lint "$plist" >/dev/null
	launchctl unload "$plist" 2>/dev/null || true
	launchctl load "$plist"
	echo "Servicio instalado: $plist"
	echo "Registro: $HOME/Library/Logs/Lyra/voicestudio.log"
}

instalar_linux() {
	local casa="$1" uv="$2"
	local unidad="$HOME/.config/systemd/user/${ETIQUETA}.service"
	mkdir -p "$(dirname "$unidad")"
	cat > "$unidad" <<UNIT
[Unit]
Description=La voz de Lyra (VoiceStudio)
After=network.target

[Service]
WorkingDirectory=${casa}
Environment=OMNIVOICE_SIDECAR_IDLE_TIMEOUT_S=${IDLE}
ExecStart=${uv} run uvicorn main:app --app-dir backend --host 127.0.0.1 --port ${PUERTO}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
	systemctl --user daemon-reload
	systemctl --user enable --now "${ETIQUETA}.service"
	echo "Servicio instalado: $unidad"
}

quitar() {
	case "$(uname -s)" in
		Darwin)
			local plist="$HOME/Library/LaunchAgents/${ETIQUETA}.plist"
			launchctl unload "$plist" 2>/dev/null || true
			rm -f "$plist"
			echo "Servicio quitado. VoiceStudio ya no arranca solo." ;;
		Linux)
			systemctl --user disable --now "${ETIQUETA}.service" 2>/dev/null || true
			rm -f "$HOME/.config/systemd/user/${ETIQUETA}.service"
			systemctl --user daemon-reload
			echo "Servicio quitado. VoiceStudio ya no arranca solo." ;;
		*) echo "Sistema no soportado: $(uname -s)" >&2; exit 1 ;;
	esac
}

instalar() {
	local casa uv
	casa="$(buscar_voicestudio)" || casa="$(traer_voicestudio)" || {
		echo "No pude instalar la voz. Si ya la tienes en otro lado:" >&2
		echo "  VOICESTUDIO_HOME=/ruta/a/VoiceStudio bash scripts/voz-servicio.sh instalar" >&2
		exit 2
	}
	uv="$(buscar_uv)" || { echo "Falta «uv» (lo usa la voz para arrancar): https://docs.astral.sh/uv/" >&2; exit 3; }
	echo "VoiceStudio: $casa"
	case "$(uname -s)" in
		Darwin) instalar_mac "$casa" "$uv" ;;
		Linux)  instalar_linux "$casa" "$uv" ;;
		*) echo "Sistema no soportado: $(uname -s)" >&2; exit 1 ;;
	esac
	echo -n "Esperando a que responda"
	for _ in $(seq 1 40); do
		if curl -sf --max-time 2 "$URL/health" >/dev/null 2>&1; then
			echo; estado
			echo
			poner_la_voz || return 5
			contarle_a_lyra "$VOZ_ID"
			echo
			echo "Si Lyra no corre en Docker aquí, pon esto en IA Ajustes:"
			echo "  Dirección: http://127.0.0.1:${PUERTO}    Voz: ${VOZ_ID}"
			return 0
		fi
		echo -n "."; sleep 3
	done
	echo
	echo "No respondió todavía. Mira el registro." >&2
	return 4
}

case "${1:-}" in
	instalar) instalar ;;
	quitar)   quitar ;;
	estado)   estado ;;
	*) echo "Uso: bash scripts/voz-servicio.sh {instalar|estado|quitar}" >&2; exit 1 ;;
esac
