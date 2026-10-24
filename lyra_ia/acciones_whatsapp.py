"""Las dos cosas que Lyra puede hacer hoy en WhatsApp, siempre preguntando antes.

Son las primeras a propósito: es lo que más se pide («mándale un recordatorio a
ese cliente») y lo que más tiempo ahorra. Cada canal es su propia app, así que
la acción solo aparece si esa app está y si la persona puede ver ese chat.

Mandar un mensaje NO se puede deshacer: lo que salió, salió. Lyra lo dice antes,
no después.
"""

from __future__ import annotations

import frappe
from frappe import _

MAX = 900


def _app(nombre: str) -> bool:
	return nombre in frappe.get_installed_apps()


def _puede_chats() -> bool:
	if _app("lyra_whatsapp") and frappe.has_permission("WhatsApp Message", "read"):
		return True
	return bool(_app("lyra_waha") and frappe.db.exists("DocType", "WAHA Chat")
				and frappe.has_permission("WAHA Chat", "read"))


# ------------------------------------------------------------ mandar un mensaje
def _resumen_mensaje(numero: str, texto: str, canal: str = "auto") -> str:
	return _("Le escribiría esto al {0} por WhatsApp:\n\n«{1}»").format(numero, (texto or "").strip()[:MAX])


def _enviar_mensaje(numero: str, texto: str, canal: str = "auto") -> dict:
	texto = (texto or "").strip()[:MAX]
	if not texto:
		frappe.throw(_("No hay nada que mandar."))
	if canal in ("auto", "meta") and _app("lyra_whatsapp"):
		from lyra_whatsapp.conversaciones.api import enviar_texto

		return {"canal": "meta", **(enviar_texto(numero, texto) or {})}
	if canal in ("auto", "waha") and _app("lyra_waha"):
		from lyra_waha.waha import enviar_texto as enviar_waha

		return {"canal": "waha", **(enviar_waha(numero, texto) or {})}
	frappe.throw(_("No hay WhatsApp conectado para mandar ese mensaje."))


# ------------------------------------------------------------ poner etiquetas
def _resumen_etiquetas(chat: str, etiquetas: str, canal: str = "auto") -> str:
	return _("Le pondría al chat {0} las etiquetas: {1}.").format(chat, etiquetas)


def _poner_etiquetas(chat: str, etiquetas: str, canal: str = "auto") -> dict:
	if canal in ("auto", "meta") and _app("lyra_whatsapp"):
		from lyra_whatsapp.conversaciones.notas import poner_etiquetas

		return {"canal": "meta", **(poner_etiquetas(chat, etiquetas) or {})}
	if canal in ("auto", "waha") and _app("lyra_waha"):
		from lyra_waha.waha_crm import poner_etiquetas as poner_waha

		return {"canal": "waha", **(poner_waha(chat, etiquetas) or {})}
	frappe.throw(_("No hay dónde poner esas etiquetas."))


def _quitar_etiquetas(datos: dict, resultado: dict) -> None:
	"""Deshacer: dejar el chat sin esas etiquetas."""
	canal = (resultado or {}).get("canal", "auto")
	_poner_etiquetas(datos["chat"], "", canal)


def acciones() -> list[dict]:
	return [
		{
			"nombre": "enviar_whatsapp",
			"modulo": "WhatsApp",
			"descripcion": _("Escribirle un mensaje de WhatsApp a alguien. Redacta tú el texto completo, en español "
							 "de Colombia y con el tono de la empresa. Ojo: un mensaje enviado no se puede deshacer."),
			"parametros": {
				"type": "object",
				"properties": {
					"numero": {"type": "string", "description": _("El número o el chat al que se le escribe.")},
					"texto": {"type": "string", "description": _("El mensaje completo, listo para mandar.")},
					"canal": {"type": "string", "enum": ["auto", "meta", "waha"],
							  "description": _("Por cuál WhatsApp. «auto» si da igual.")},
				},
				"required": ["numero", "texto"],
			},
			"resumen": _resumen_mensaje,
			"ejecutar": _enviar_mensaje,
			"deshacer": None,      # lo que salió, salió
			"disponible": _puede_chats,
		},
		{
			"nombre": "etiquetar_chat",
			"modulo": "WhatsApp",
			"descripcion": _("Ponerle etiquetas a un chat para saber de qué se trataba."),
			"parametros": {
				"type": "object",
				"properties": {
					"chat": {"type": "string", "description": _("El número o el id del chat.")},
					"etiquetas": {"type": "string", "description": _("Las etiquetas, separadas por coma.")},
					"canal": {"type": "string", "enum": ["auto", "meta", "waha"]},
				},
				"required": ["chat", "etiquetas"],
			},
			"resumen": _resumen_etiquetas,
			"ejecutar": _poner_etiquetas,
			"deshacer": _quitar_etiquetas,
			"disponible": _puede_chats,
		},
	]
