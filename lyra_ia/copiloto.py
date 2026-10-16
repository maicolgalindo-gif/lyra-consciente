"""Copiloto en los chats de WhatsApp (API de Meta y WAHA): resumir, sugerir
respuesta y clasificar.

Solo lee y propone: no envia nada ni cambia el chat por su cuenta. Lee la
conversacion con las mismas funciones que usa la pantalla, asi que respeta
los permisos de quien lo usa (un agente que no puede ver un chat, tampoco
puede pedirle a la IA que lo resuma).

canal: "meta" (id = numero) o "waha" (id = chat_id).
"""

from __future__ import annotations

import frappe
from frappe import _

from lyra_ia import cerebro, clasificador
from lyra_ia.cerebro import IAError

MAX_MENSAJES = 60


# ------------------------------------------------------------ preguntas
def preguntas_whatsapp() -> dict:
	"""Lo que se le pregunta a cada chat. Mismo formato que Laya."""
	if "lyra_whatsapp" not in frappe.get_installed_apps():
		return {}
	return {
		"whatsapp": {
			"modulo": "WhatsApp",
			"preguntas": {
				"intencion": {
					"type": "choice",
					"instructions": "¿Qué busca el cliente en esta conversación?",
					"criteria": {
						"precio": "pregunta precios, tarifas o pide cotización",
						"agendar": "quiere una cita, turno, reserva o saber horarios para ir",
						"compra": "ya decidió y quiere comprar, pagar o confirmar",
						"soporte": "tiene un problema con algo que ya compró o un servicio recibido",
						"queja": "está molesto, reclama o se queja",
						"documentos": "pide o envía certificados, facturas, soportes o requisitos",
						"informacion": "pregunta general: dónde están, qué ofrecen, cómo funciona",
						"otro": "nada de lo anterior, saludo sin contenido o spam",
					},
				},
				"urgencia": {
					"type": "score",
					"instructions": "¿Qué tan urgente es atenderlo?",
					"criteria": ["baja", "media", "alta"],
				},
				"sentimiento": {
					"type": "choice",
					"instructions": "¿Cómo se siente el cliente?",
					"criteria": {"positivo": "contento o agradecido", "neutral": "normal", "negativo": "molesto, frustrado o decepcionado"},
				},
				"venta": {"type": "noul", "instructions": "¿Hay una oportunidad de venta concreta en esta conversación?"},
				"pide_baja": {"type": "noul", "instructions": "¿Pide que no le escriban más o que lo saquen de la lista?"},
			},
		}
	}


# Etiqueta que se propone para el chat segun la clasificacion.
ETIQUETAS = {"precio": "cotización", "agendar": "agendar", "compra": "venta", "soporte": "soporte", "queja": "queja",
			 "documentos": "documentos", "informacion": "información"}


# ------------------------------------------------------------- lectura
def _chat(canal: str, ident: str) -> dict:
	if "lyra_whatsapp" not in frappe.get_installed_apps():
		raise IAError(_("El módulo de WhatsApp no está instalado."))
	if canal == "meta":
		from lyra_whatsapp.conversaciones.api import mensajes

		datos = mensajes(ident)
		datos["referencia"] = ("WhatsApp Conversacion", datos["numero"]) if frappe.db.exists("WhatsApp Conversacion", datos["numero"]) else None
	elif canal == "waha":
		from lyra_whatsapp.waha_chat import mensajes

		datos = mensajes(ident)
		datos["referencia"] = ("WAHA Chat", ident) if frappe.db.exists("WAHA Chat", ident) else None
	else:
		raise IAError(_("Canal no válido."))
	return datos


def _transcripcion(datos: dict, con_notas: bool) -> str:
	"""La conversacion como texto: «Cliente: ...» / «Empresa (Ana): ...»."""
	lineas = []
	for m in datos["mensajes"][-MAX_MENSAJES:]:
		hora = str(m.get("hora", ""))[:16]
		if m.get("nota"):
			if con_notas:
				lineas.append(f"[{hora}] Nota interna del equipo ({m.get('autor') or ''}): {m.get('texto')}")
			continue
		texto = (m.get("texto") or "").strip() or f"[{m.get('tipo') or 'archivo'}]"
		quien = f"Empresa ({m['autor']})" if m.get("saliente") and m.get("autor") else ("Empresa" if m.get("saliente") else "Cliente")
		lineas.append(f"[{hora}] {quien}: {texto}")
	if not lineas:
		raise IAError(_("Este chat todavía no tiene mensajes."))
	return "\n".join(lineas)


def _empresa() -> str:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company") or ""


def _contexto_negocio() -> str:
	ctx = (cerebro.ajustes().contexto_negocio or "").strip()
	return f"\n\nLo que sabes del negocio:\n{ctx}" if ctx else ""


# ------------------------------------------------------------ acciones
@frappe.whitelist(methods=["POST"])
def resumir(canal: str, ident: str) -> dict:
	datos = _chat(canal, ident)
	sistema = (
		f"Eres el asistente del equipo de atención de {_empresa()}. Resume la conversación de WhatsApp para un agente "
		"que la va a retomar. En español, breve, en viñetas con guion:\n"
		"- Quién es y qué quiere\n- Qué se le ha dicho u ofrecido\n- Qué está pendiente y de quién\n"
		"- Cómo se siente el cliente\nSi algo no se sabe, no lo inventes. Las notas internas son del equipo y "
		"el cliente no las ve."
	)
	texto = cerebro.completar(
		[{"role": "system", "content": sistema},
		 {"role": "user", "content": f"Cliente: {datos.get('nombre') or 'sin nombre'}\n\n{_transcripcion(datos, True)}"}],
		funcion=f"whatsapp.resumir.{canal}", referencia=datos["referencia"], max_tokens=500,
	)
	return {"resumen": texto.strip()}


@frappe.whitelist(methods=["POST"])
def sugerir(canal: str, ident: str, instruccion: str | None = None) -> dict:
	"""Un borrador de respuesta. No se envia: va al cuadro de texto para que el agente lo revise."""
	datos = _chat(canal, ident)
	agente = (frappe.utils.get_fullname(frappe.session.user) or "").split(" ")[0]
	sistema = (
		f"Eres {agente or 'un asesor'} y atiendes el WhatsApp de {_empresa()} en Colombia. Escribe la PRÓXIMA respuesta "
		"al cliente: en español, cordial, corta (como un mensaje de WhatsApp, sin saludos largos ni firma), "
		"sin inventar precios, horarios ni datos que no estén en la conversación o en lo que sabes del negocio; "
		"si falta un dato, pregúntalo o di que lo confirmas. Puedes usar *negrita* de WhatsApp. "
		"Devuelve solo el texto del mensaje." + _contexto_negocio()
	)
	pedido = _transcripcion(datos, True)
	if (instruccion or "").strip():
		pedido += f"\n\nIndicación del agente para esta respuesta: {instruccion.strip()}"
	texto = cerebro.completar(
		[{"role": "system", "content": sistema}, {"role": "user", "content": pedido}],
		funcion=f"whatsapp.sugerir.{canal}", referencia=datos["referencia"], max_tokens=400, temperatura=0.5,
	)
	return {"texto": texto.strip().strip('"')}


@frappe.whitelist(methods=["POST"])
def clasificar(canal: str, ident: str) -> dict:
	datos = _chat(canal, ident)
	respuestas = clasificador.clasificar("whatsapp", _transcripcion(datos, False), referencia=datos["referencia"])
	intencion = respuestas.get("intencion", {}).get("respuesta")
	sugeridas = [e for e in (
		ETIQUETAS.get(intencion),
		"urgente" if respuestas.get("urgencia", {}).get("respuesta") == "alta" else None,
		"venta" if respuestas.get("venta", {}).get("respuesta") == "si" and intencion != "compra" else None,
	) if e]
	return {"respuestas": respuestas, "etiquetas_sugeridas": sugeridas, "etiquetas_actuales": datos.get("etiquetas") or []}


@frappe.whitelist(methods=["POST"])
def guardar_clasificacion(canal: str, ident: str, revisadas: str | dict, etiquetas: str | None = None) -> dict:
	"""Lo que el agente aprobo: las respuestas revisadas (para entrenar a Laya) y las etiquetas del chat."""
	_chat(canal, ident)  # permisos
	clasificador.revisar(frappe.parse_json(revisadas) if isinstance(revisadas, str) else revisadas)
	if etiquetas is not None:
		if canal == "waha":
			from lyra_whatsapp.waha_crm import poner_etiquetas
		else:
			from lyra_whatsapp.conversaciones.notas import poner_etiquetas

		poner_etiquetas(ident, etiquetas)
	return {"ok": True}
