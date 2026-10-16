"""El cerebro de Lyra: llamadas al modelo de lenguaje (DeepSeek u otro).

Habla el formato de OpenAI (POST {url}/chat/completions), que es el que usan
DeepSeek, OpenRouter, Together y casi todos: cambiar de proveedor es cambiar
la URL, la clave y el nombre del modelo en IA Ajustes, sin tocar codigo.

Cada llamada:
- se niega si la IA esta apagada o si ya se gasto el limite del mes;
- oculta correos, telefonos y documentos (privacidad.py) y los devuelve en la respuesta;
- queda en IA Registro (quien, para que, tokens, costo), tambien si falla.

Uso:
	from lyra_ia.cerebro import completar
	texto = completar([{"role": "user", "content": "Hola"}], funcion="prueba")
"""

from __future__ import annotations

import json
import time

import requests

import frappe
from frappe import _
from frappe.utils import get_first_day, now_datetime, nowdate

from lyra_ia import privacidad

AJUSTES = "IA Ajustes"
REGISTRO = "IA Registro"
TIMEOUT_S = 90
PROVEEDORES = {
	"DeepSeek": {"url": "https://api.deepseek.com", "chat": "deepseek-chat", "razonador": "deepseek-reasoner"},
	"OpenRouter": {"url": "https://openrouter.ai/api/v1", "chat": "deepseek/deepseek-chat", "razonador": "deepseek/deepseek-r1"},
	"Together": {"url": "https://api.together.xyz/v1", "chat": "deepseek-ai/DeepSeek-V3", "razonador": "deepseek-ai/DeepSeek-R1"},
}


class IAError(frappe.ValidationError):
	"""La IA no pudo responder; el mensaje esta en español, listo para mostrar."""


def ajustes():
	return frappe.get_cached_doc(AJUSTES)


def lista() -> bool:
	a = ajustes()
	return bool(a.activo and a.get_password("clave", raise_exception=False))


def gasto_del_mes() -> float:
	return frappe.db.sql(
		"SELECT IFNULL(SUM(costo), 0) FROM `tabIA Registro` WHERE creation >= %s",
		get_first_day(nowdate()),
	)[0][0]


def _costo(a, entrada: int, salida: int) -> float:
	return (entrada * (a.precio_entrada or 0) + salida * (a.precio_salida or 0)) / 1_000_000


def completar(
	mensajes: list[dict],
	funcion: str,
	referencia: tuple[str, str] | None = None,
	razonar: bool = False,
	json_salida: bool = False,
	max_tokens: int = 800,
	temperatura: float = 0.3,
) -> str:
	"""Envia la conversacion al modelo y devuelve el texto de la respuesta.

	funcion: para que se uso ("whatsapp.resumir"), sale en el registro.
	referencia: (doctype, name) del documento sobre el que se trabajo.
	json_salida: pide JSON valido (lo devuelve como texto; usa completar_json).
	"""
	mapa: dict = {}
	mensaje = llamar(mensajes, funcion, mapa, referencia=referencia, razonar=razonar, json_salida=json_salida,
					 max_tokens=max_tokens, temperatura=temperatura)
	return privacidad.mostrar(mensaje.get("content") or "", mapa)


def llamar(
	mensajes: list[dict],
	funcion: str,
	mapa: dict,
	referencia: tuple[str, str] | None = None,
	herramientas: list[dict] | None = None,
	razonar: bool = False,
	json_salida: bool = False,
	max_tokens: int = 800,
	temperatura: float = 0.3,
) -> dict:
	"""Una llamada al modelo. Devuelve el mensaje tal cual (content y, si pidio
	herramientas, tool_calls), con los datos personales todavia ocultos: quien
	llama usa el mismo mapa para leer los argumentos y la respuesta.
	"""
	a = ajustes()
	if not a.activo:
		raise IAError(_("La IA está apagada. Actívala en IA Ajustes."))
	clave = a.get_password("clave", raise_exception=False)
	if not clave:
		raise IAError(_("Falta la clave de la API en IA Ajustes."))
	if a.limite_mensual and gasto_del_mes() >= a.limite_mensual:
		raise IAError(_("Se llegó al límite de gasto de este mes (USD {0}). Súbelo en IA Ajustes o espera al próximo mes.")
					  .format(a.limite_mensual))

	if a.ocultar_datos:
		mensajes = [{**m, "content": privacidad.ocultar(m.get("content") or "", mapa)} if m.get("content") else m
					for m in mensajes]
	modelo = (a.modelo_razonador if razonar and a.modelo_razonador else a.modelo_chat) or "deepseek-chat"
	cuerpo = {"model": modelo, "messages": mensajes, "max_tokens": max_tokens, "temperature": temperatura, "stream": False}
	if json_salida:
		cuerpo["response_format"] = {"type": "json_object"}
	if herramientas:
		cuerpo["tools"] = herramientas

	inicio = time.monotonic()
	registro = {"funcion": funcion, "proveedor": a.proveedor, "modelo": modelo, "usuario": frappe.session.user,
				"referencia_doctype": referencia[0] if referencia else None,
				"referencia_name": referencia[1] if referencia else None,
				"enviado": json.dumps(mensajes, ensure_ascii=False, indent=1) if a.guardar_textos else None}
	try:
		r = requests.post(
			f"{(a.url_base or PROVEEDORES['DeepSeek']['url']).rstrip('/')}/chat/completions",
			json=cuerpo,
			headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
			timeout=TIMEOUT_S * (2 if razonar else 1),
		)
	except requests.Timeout:
		_registrar({**registro, "estado": "Error", "error": "timeout"}, inicio, falla=True)
		raise IAError(_("El modelo no respondió a tiempo. Intenta de nuevo."))
	except requests.RequestException as e:
		_registrar({**registro, "estado": "Error", "error": str(e)[:500]}, inicio, falla=True)
		raise IAError(_("No se pudo conectar con el proveedor de IA ({0}).").format(a.url_base))
	if not r.ok:
		_registrar({**registro, "estado": "Error", "error": f"{r.status_code}: {r.text[:500]}"}, inicio, falla=True)
		raise IAError(_mensaje_de_error(r))
	try:
		datos = r.json()
		mensaje = datos["choices"][0]["message"]
		texto = mensaje.get("content") or ""
	except (ValueError, KeyError, IndexError):
		_registrar({**registro, "estado": "Error", "error": r.text[:500]}, inicio, falla=True)
		raise IAError(_("El proveedor de IA devolvió una respuesta que no se entiende."))
	uso = datos.get("usage") or {}
	entrada, salida = int(uso.get("prompt_tokens") or 0), int(uso.get("completion_tokens") or 0)
	_registrar({**registro, "estado": "Ok", "tokens_entrada": entrada, "tokens_salida": salida,
				"costo": _costo(a, entrada, salida),
				"respuesta": (texto or json.dumps(mensaje.get("tool_calls"), ensure_ascii=False)) if a.guardar_textos else None}, inicio)
	return mensaje


def completar_json(mensajes: list[dict], funcion: str, **kw) -> dict:
	"""Como completar, pero devuelve el JSON ya leido."""
	texto = completar(mensajes, funcion, json_salida=True, **kw)
	limpio = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
	try:
		return json.loads(limpio)
	except ValueError:
		raise IAError(_("La IA no devolvió datos válidos. Intenta de nuevo."))


def _registrar(datos: dict, inicio: float, falla: bool = False) -> None:
	datos["duracion_ms"] = int((time.monotonic() - inicio) * 1000)
	frappe.get_doc({"doctype": REGISTRO, **datos}).insert(ignore_permissions=True)
	if falla:
		# Si la peticion termina en error se deshace todo; el registro del fallo se queda.
		frappe.db.commit()


def _mensaje_de_error(r: requests.Response) -> str:
	if r.status_code == 401:
		return _("El proveedor rechazó la clave de la API (401). Revísala en IA Ajustes.")
	if r.status_code == 402:
		return _("La cuenta del proveedor de IA no tiene saldo (402). Recárgala en su página.")
	if r.status_code == 404:
		return _("El proveedor no encontró el modelo o la URL (404). Revisa el nombre del modelo en IA Ajustes.")
	if r.status_code == 429:
		return _("El proveedor de IA está recibiendo demasiadas solicitudes (429). Intenta en un momento.")
	if r.status_code >= 500:
		return _("El proveedor de IA tuvo un error ({0}). Intenta en un momento.").format(r.status_code)
	return _("El proveedor de IA respondió {0}: {1}").format(r.status_code, r.text[:200])


# --------------------------------------------------------- configuracion
@frappe.whitelist(methods=["POST"])
def probar_conexion() -> dict:
	frappe.only_for("System Manager")
	inicio = time.monotonic()
	try:
		texto = completar([{"role": "user", "content": "Responde solo: OK"}], funcion="prueba de conexión", max_tokens=5)
		estado = _("Conectado {0}: respondió «{1}» en {2:.1f} s.").format(now_datetime().strftime("%d-%m-%Y %H:%M"), texto.strip()[:20],
																		   time.monotonic() - inicio)
		ok = True
	except IAError as e:
		estado, ok = f"{now_datetime().strftime('%d-%m-%Y %H:%M')}: {e}", False
	frappe.db.set_single_value(AJUSTES, "estado_conexion", estado)
	return {"ok": ok, "estado": estado}


@frappe.whitelist()
def resumen_gasto() -> dict:
	frappe.only_for("System Manager")
	a = ajustes()
	mes = get_first_day(nowdate())
	fila = frappe.db.sql(
		"""SELECT COUNT(*), IFNULL(SUM(costo), 0), IFNULL(SUM(tokens_entrada), 0), IFNULL(SUM(tokens_salida), 0),
			SUM(estado = 'Error') FROM `tabIA Registro` WHERE creation >= %s""", mes)[0]
	return {"llamadas": fila[0], "costo": float(fila[1]), "tokens_entrada": int(fila[2]), "tokens_salida": int(fila[3]),
			"errores": int(fila[4] or 0), "limite": a.limite_mensual or 0, "con_precios": bool(a.precio_entrada or a.precio_salida)}
