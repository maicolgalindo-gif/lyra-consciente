"""La voz de Lyra: convierte su texto en audio con ElevenLabs.

La clave vive cifrada en IA Ajustes (solo la ve el Equipo Lyra) y nunca sale al
navegador: el navegador pide el audio aqui y aqui se habla con ElevenLabs. Las
frases ya dichas se guardan en cache una semana, asi que repetir una pregunta
(o recargar la pagina) no se vuelve a cobrar. Cada audio nuevo queda en IA
Registro con sus caracteres, que es lo que ElevenLabs cobra.

Si la voz no esta activa o ElevenLabs falla, el navegador usa su propia voz.
"""

from __future__ import annotations

import base64
import hashlib
import time

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

URL = "https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_128"
MAX_CARACTERES = 700


def _ajustes():
	return frappe.get_cached_doc("IA Ajustes")


def lista() -> bool:
	a = _ajustes()
	return bool(a.voz_activa and a.voz_id and a.get_password("voz_clave", raise_exception=False))


def _sintetizar(texto: str, funcion: str) -> bytes:
	a = _ajustes()
	clave = a.get_password("voz_clave", raise_exception=False)
	modelo = a.voz_modelo or "eleven_multilingual_v2"
	inicio = time.monotonic()
	registro = {"doctype": "IA Registro", "funcion": funcion, "usuario": frappe.session.user, "proveedor": "ElevenLabs",
				"modelo": f"{modelo} / {a.voz_id}", "tokens_entrada": len(texto), "tokens_salida": 0, "costo": 0}
	try:
		r = requests.post(URL.format(voz=a.voz_id), headers={"xi-api-key": clave, "Accept": "audio/mpeg"},
						  json={"text": texto, "model_id": modelo, "language_code": "es"} if "flash" in modelo or "turbo" in modelo
						  else {"text": texto, "model_id": modelo}, timeout=30)
	except requests.RequestException:
		_registrar(registro, inicio, _("No se pudo conectar con ElevenLabs."))
		raise frappe.ValidationError(_("No se pudo conectar con ElevenLabs."))
	if r.status_code != 200:
		detalle = r.text[:200]
		mensaje = {401: _("ElevenLabs rechazó la clave (401). Revísala en IA Ajustes."),
				   404: _("ElevenLabs no encontró esa voz (404). Revisa el ID de la voz en IA Ajustes.")}.get(
			r.status_code, _("ElevenLabs respondió {0}: {1}").format(r.status_code, detalle))
		_registrar(registro, inicio, mensaje)
		raise frappe.ValidationError(mensaje)
	_registrar(registro, inicio)
	return r.content


def _registrar(registro: dict, inicio: float, error: str | None = None) -> None:
	registro.update(estado="Error" if error else "Ok", error=error, duracion_ms=int((time.monotonic() - inicio) * 1000))
	frappe.get_doc(registro).insert(ignore_permissions=True)
	if error:
		frappe.db.commit()


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
	clave_cache = "lyra_voz:" + hashlib.sha1(f"{a.voz_id}|{a.voz_modelo}|{texto}".encode()).hexdigest()
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
