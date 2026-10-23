"""La voz de Lyra: convierte su texto en audio con VoiceStudio.

VoiceStudio corre en la misma maquina que Lyra, asi que no cobra por caracter y
el texto no sale de ahi. Habla el formato de OpenAI (POST {url}/v1/audio/speech),
de modo que cualquier otro servidor con ese mismo formato sirve cambiando la
direccion en IA Ajustes.

Un aviso que cuesta caro descubrir solo: Lyra corre dentro del contenedor, asi
que «localhost» ahi es el contenedor, no tu maquina. La direccion que sirve es
http://host.docker.internal:3900.

Sintetizar en local tarda mas que llamar a la nube (unos segundos por frase), por
eso la espera es larga y las frases ya dichas se guardan en cache una semana:
repetir una pregunta o recargar la pagina no vuelve a sintetizar. Cada audio
nuevo queda en IA Registro con sus caracteres.

Si la voz no esta activa o VoiceStudio no responde, el navegador usa su propia voz.
"""

from __future__ import annotations

import base64
import hashlib
import time

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

MAX_CARACTERES = 700
# Sintetizar en la maquina no es inmediato: una frase corta puede tardar varios
# segundos, bastante mas que una llamada a la nube.
ESPERA = 180


def _ajustes():
	return frappe.get_cached_doc("IA Ajustes")


def lista() -> bool:
	a = _ajustes()
	return bool(a.voz_activa and a.voz_id and a.get("voz_url"))


def _cuerpo(a, texto: str) -> dict:
	"""Lo que se le pide a VoiceStudio.

	num_step es lo que de verdad manda en la espera: cada paso es una pasada del
	modelo sobre la frase. Con 16 (lo que trae de fabrica) una pregunta tarda unos
	11 segundos y la persona ya leyo el texto hace rato; con 8 baja a unos 4. Si
	la voz suena rara, se sube en IA Ajustes."""
	cuerpo = {"input": texto, "voice": a.voz_id, "response_format": "mp3"}
	pasos = int(a.get("voz_pasos") or 0)
	if pasos > 0:
		cuerpo["num_step"] = max(1, min(128, pasos))
	return cuerpo


def _sintetizar(texto: str, funcion: str) -> bytes:
	a = _ajustes()
	url = (a.get("voz_url") or "").rstrip("/") + "/v1/audio/speech"
	inicio = time.monotonic()
	registro = {"doctype": "IA Registro", "funcion": funcion, "usuario": frappe.session.user,
				"proveedor": "VoiceStudio", "modelo": a.voz_id, "tokens_entrada": len(texto),
				"tokens_salida": 0, "costo": 0}
	cuerpo = _cuerpo(a, texto)
	cabeceras = {"Content-Type": "application/json", "X-OmniVoice-Client-Id": "lyra_ia"}
	r = None
	for intento in range(2):
		try:
			r = requests.post(url, headers=cabeceras, json=cuerpo, timeout=ESPERA)
		except requests.RequestException:
			mensaje = _("No se pudo conectar con VoiceStudio en {0}. ¿Está abierto?").format(a.get("voz_url"))
			_registrar(registro, inicio, mensaje)
			raise frappe.ValidationError(mensaje)
		# Si ya hay otra frase sintetizandose, VoiceStudio rechaza esta y dice que
		# se puede repetir tal cual en unos segundos: pasa cuando dos pantallas
		# piden voz a la vez. Se reintenta una sola vez.
		if r.status_code in (429, 503) or (r.status_code >= 400 and "saturat" in (r.text or "").lower()):
			if intento == 0:
				time.sleep(5)
				continue
		break
	if r.status_code != 200 or not r.content:
		mensaje = {404: _("VoiceStudio no encontró esa voz (404). Revisa el ID de la voz en IA Ajustes.")}.get(
			r.status_code, _("VoiceStudio respondió {0}: {1}").format(r.status_code, r.text[:200]))
		_registrar(registro, inicio, mensaje)
		raise frappe.ValidationError(mensaje)
	_registrar(registro, inicio)
	return r.content


def _registrar(registro: dict, inicio: float, error: str | None = None) -> None:
	registro.update(estado="Error" if error else "Ok", error=error, duracion_ms=int((time.monotonic() - inicio) * 1000))
	frappe.get_doc(registro).insert(ignore_permissions=True)
	if error:
		frappe.db.commit()


@frappe.whitelist()
def voces() -> list[dict]:
	"""Las voces que tiene VoiceStudio, para elegir una en IA Ajustes."""
	frappe.only_for("Equipo Lyra")
	a = _ajustes()
	url = (a.get("voz_url") or "").rstrip("/") + "/v1/audio/voices"
	try:
		r = requests.get(url, headers={"X-OmniVoice-Client-Id": "lyra_ia"}, timeout=20)
		datos = r.json() if r.status_code == 200 else {}
	except Exception:
		frappe.throw(_("No se pudo conectar con VoiceStudio en {0}. ¿Está abierto?").format(a.get("voz_url")))
	lista_voces = datos.get("voices") or datos.get("data") or []
	return [{"id": v.get("voice_id") or v.get("id"), "nombre": v.get("name") or v.get("id")}
			for v in lista_voces if isinstance(v, dict)]


# ------------------------------------------------------------------- API
@frappe.whitelist(methods=["POST"])
def hablar(texto: str) -> dict:
	"""El audio de una frase de Lyra, en base64 (mp3). Para las pantallas de Lyra."""
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	texto = (texto or "").strip()[:MAX_CARACTERES]
	if not texto or not lista():
		return {"audio": None}
	a = _ajustes()
	clave_cache = "lyra_voz:" + hashlib.sha1(f"{a.voz_id}|{a.get('voz_pasos')}|{texto}".encode()).hexdigest()
	audio = frappe.cache.get_value(clave_cache, expires=True)
	if not audio:
		audio = base64.b64encode(_sintetizar(texto, "voz")).decode()
		frappe.cache.set_value(clave_cache, audio, expires_in_sec=7 * 24 * 3600)
	return {"audio": audio, "tipo": "audio/mpeg"}


@frappe.whitelist(methods=["POST"])
def probar() -> dict:
	"""Boton «Probar voz» de IA Ajustes."""
	frappe.only_for("Equipo Lyra")
	try:
		audio = _sintetizar(_("Hola, soy Lyra. Así sueno."), "prueba de voz")
		estado, ok = _("{0}: la voz respondió bien.").format(now_datetime().strftime("%d-%m-%Y %H:%M")), True
	except frappe.ValidationError as e:
		audio, estado, ok = None, f"{now_datetime().strftime('%d-%m-%Y %H:%M')}: {e}", False
	frappe.db.set_single_value("IA Ajustes", "voz_estado", estado)
	return {"ok": ok, "estado": estado, "audio": base64.b64encode(audio).decode() if audio else None}
