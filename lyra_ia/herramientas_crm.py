"""Herramientas de consulta del CRM, ventas y WhatsApp para el asistente.

Cada una aparece solo si su app esta instalada y el usuario puede leer esos
documentos. Usan frappe.get_list (respeta permisos), nunca SQL sin filtrar
por permisos.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, fmt_money, nowdate

LIMITE = 15


def _app(nombre: str) -> bool:
	return nombre in frappe.get_installed_apps()


def _puede(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype)) and frappe.has_permission(doctype, "read")


def _dinero(v, moneda=None) -> str:
	return fmt_money(flt(v), currency=moneda or frappe.defaults.get_global_default("currency"))


# ------------------------------------------------------------------ CRM
TIPOS = {
	"cliente": ("Customer", ["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id"], "customer_name"),
	"cliente_potencial": ("Lead", ["name", "lead_name", "company_name", "status", "source", "mobile_no", "email_id", "lead_owner"], "lead_name"),
	"contacto": ("Contact", ["name", "full_name", "mobile_no", "email_id", "company_name"], "full_name"),
	"oportunidad": ("Opportunity", ["name", "title", "party_name", "status", "sales_stage", "opportunity_amount", "opportunity_owner", "expected_closing"], "title"),
	"cotizacion": ("Quotation", ["name", "party_name", "customer_name", "status", "grand_total", "transaction_date", "valid_till"], "customer_name"),
	"pedido": ("Sales Order", ["name", "customer", "customer_name", "status", "grand_total", "transaction_date", "delivery_date"], "customer_name"),
	"factura": ("Sales Invoice", ["name", "customer", "customer_name", "status", "grand_total", "outstanding_amount", "posting_date", "due_date"], "customer_name"),
}


def buscar_registros(tipo: str, texto: str | None = None, estado: str | None = None, limite: int = 10) -> dict:
	if tipo not in TIPOS:
		return {"error": f"Tipo no válido. Opciones: {', '.join(TIPOS)}"}
	doctype, campos, campo_nombre = TIPOS[tipo]
	frappe.has_permission(doctype, "read", throw=True)
	or_filtros = None
	if texto:
		or_filtros = {"name": ["like", f"%{texto}%"], campo_nombre: ["like", f"%{texto}%"]}
		if "mobile_no" in campos:
			or_filtros["mobile_no"] = ["like", f"%{texto[-10:]}%"]
	filtros = {"status": estado} if estado and "status" in campos else {}
	if doctype in ("Quotation", "Sales Order", "Sales Invoice"):
		filtros["docstatus"] = ["<", 2]
	filas = frappe.get_list(doctype, filters=filtros, or_filters=or_filtros, fields=campos, order_by="modified desc",
							limit_page_length=min(int(limite or 10), LIMITE))
	return {"tipo": tipo, "resultados": filas, "enlace_base": f"/app/{doctype.lower().replace(' ', '-')}"}


def ficha_cliente(cliente: str) -> dict:
	"""Datos, saldo y ultimos documentos de un cliente (nombre o codigo)."""
	frappe.has_permission("Customer", "read", throw=True)
	nombre = frappe.db.get_value("Customer", cliente, "name") or frappe.db.get_value("Customer", {"customer_name": ["like", f"%{cliente}%"]}, "name")
	if not nombre:
		return {"error": f"No encontré el cliente «{cliente}»."}
	c = frappe.get_list("Customer", filters={"name": nombre}, fields=["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id"])[0]
	salida = {"cliente": c}
	if _puede("Sales Invoice"):
		facturas = frappe.get_list("Sales Invoice", filters={"customer": nombre, "docstatus": 1},
								   fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "status"],
								   order_by="posting_date desc", limit_page_length=8)
		salida["saldo_pendiente"] = _dinero(sum(flt(f.outstanding_amount) for f in frappe.get_list(
			"Sales Invoice", filters={"customer": nombre, "docstatus": 1, "outstanding_amount": [">", 0]}, fields=["outstanding_amount"],
			limit_page_length=0)))
		salida["ultimas_facturas"] = facturas
	if _puede("Opportunity"):
		salida["oportunidades_abiertas"] = frappe.get_list(
			"Opportunity", filters={"party_name": nombre, "status": ["in", ["Open", "Replied", "Quotation"]]},
			fields=["name", "title", "sales_stage", "opportunity_amount", "status"], limit_page_length=8)
	if _puede("Quotation"):
		salida["cotizaciones"] = frappe.get_list("Quotation", filters={"party_name": nombre, "docstatus": ["<", 2]},
												 fields=["name", "transaction_date", "grand_total", "status"], order_by="transaction_date desc",
												 limit_page_length=5)
	return salida


def cartera_vencida(dias_minimos: int = 0) -> dict:
	"""Facturas con saldo cuya fecha de vencimiento ya paso, agrupadas por cliente."""
	frappe.has_permission("Sales Invoice", "read", throw=True)
	corte = add_days(nowdate(), -int(dias_minimos or 0))
	filas = frappe.get_list("Sales Invoice",
							filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", corte]},
							fields=["customer", "customer_name", "name", "due_date", "outstanding_amount"], limit_page_length=0)
	por_cliente: dict = {}
	for f in filas:
		c = por_cliente.setdefault(f.customer, {"cliente": f.customer_name or f.customer, "codigo": f.customer, "saldo": 0.0,
												 "facturas": 0, "vencimiento_mas_antiguo": f.due_date})
		c["saldo"] += flt(f.outstanding_amount)
		c["facturas"] += 1
		c["vencimiento_mas_antiguo"] = min(c["vencimiento_mas_antiguo"], f.due_date)
	lista = sorted(por_cliente.values(), key=lambda c: -c["saldo"])
	total = sum(c["saldo"] for c in lista)
	for c in lista:
		c["saldo"] = _dinero(c["saldo"])
	return {"total_vencido": _dinero(total), "clientes": len(lista), "detalle": lista[:20],
			"criterio": f"vencidas hace más de {dias_minimos} días" if dias_minimos else "vencidas"}


def embudo_ventas(solo_mias: bool = False) -> dict:
	frappe.has_permission("Opportunity", "read", throw=True)
	filtros = {"status": ["in", ["Open", "Replied", "Quotation"]]}
	if solo_mias:
		filtros["opportunity_owner"] = frappe.session.user
	filas = frappe.get_list("Opportunity", filters=filtros, fields=["sales_stage", "opportunity_amount"], limit_page_length=0)
	etapas: dict = {}
	for f in filas:
		e = etapas.setdefault(f.sales_stage or "Sin etapa", {"etapa": f.sales_stage or "Sin etapa", "cantidad": 0, "valor": 0.0})
		e["cantidad"] += 1
		e["valor"] += flt(f.opportunity_amount)
	lista = list(etapas.values())
	total = sum(e["valor"] for e in lista)
	for e in lista:
		e["valor"] = _dinero(e["valor"])
	return {"oportunidades_abiertas": len(filas), "valor_total": _dinero(total), "por_etapa": lista}


def ventas_del_periodo(dias: int = 30) -> dict:
	frappe.has_permission("Sales Invoice", "read", throw=True)
	desde = add_days(nowdate(), -int(dias or 30))
	filas = frappe.get_list("Sales Invoice", filters={"docstatus": 1, "posting_date": [">=", desde], "is_return": 0},
							fields=["customer_name", "grand_total"], limit_page_length=0)
	por_cliente: dict = {}
	for f in filas:
		por_cliente[f.customer_name] = por_cliente.get(f.customer_name, 0) + flt(f.grand_total)
	top = sorted(por_cliente.items(), key=lambda x: -x[1])[:10]
	return {"desde": desde, "facturas": len(filas), "total_facturado": _dinero(sum(flt(f.grand_total) for f in filas)),
			"mejores_clientes": [{"cliente": c, "total": _dinero(v)} for c, v in top]}


# ------------------------------------------------------------- WhatsApp
def _chats(canal: str, buscar: str | None, estado: str) -> list[dict]:
	salida = []
	if canal in ("meta", "todos") and frappe.has_permission("WhatsApp Message", "read"):
		from lyra_whatsapp.conversaciones.api import listar

		for c in (listar(buscar=buscar, vista="todos", estado="Resuelta" if estado == "resuelto" else "Abierta") or {}).get("chats", [])[:LIMITE]:
			salida.append({"canal": "meta", "id": c.get("numero"), "nombre": c.get("nombre"), "numero": c.get("numero"),
						   "ultimo": c.get("ultimo"), "ultimo_mensaje": c.get("resumen"), "sin_responder": c.get("sin_responder"),
						   "etiquetas": c.get("etiquetas")})
	if canal in ("waha", "todos") and frappe.db.exists("DocType", "WAHA Chat"):
		try:
			from lyra_whatsapp.waha_chat import listar as listar_waha

			for c in (listar_waha(buscar=buscar, vista="todos", estado="Resuelto" if estado == "resuelto" else "Abierto") or {}).get("chats", [])[:LIMITE]:
				salida.append({"canal": "waha", "id": c.get("chat_id"), "nombre": c.get("nombre"), "numero": c.get("numero"),
							   "ultimo": c.get("ultimo"), "ultimo_mensaje": c.get("resumen"), "sin_responder": c.get("sin_responder"),
							   "etiquetas": c.get("etiquetas")})
		except frappe.PermissionError:
			pass
	return salida


def buscar_chats(texto: str | None = None, canal: str = "todos", estado: str = "abierto") -> dict:
	return {"chats": _chats(canal, texto, estado)}


def chats_sin_responder(canal: str = "todos") -> dict:
	chats = [c for c in _chats(canal, None, "abierto") if c.get("sin_responder")]
	return {"total": len(chats), "chats": sorted(chats, key=lambda c: str(c.get("ultimo") or ""))}


def leer_chat(canal: str, id: str) -> dict:
	from lyra_ia.copiloto import _chat, _transcripcion

	datos = _chat(canal, id)
	return {"nombre": datos.get("nombre"), "numero": datos.get("numero"), "etiquetas": datos.get("etiquetas"),
			"estado": datos.get("estado_chat"), "responsable": datos.get("asignado_nombre"),
			"conversacion": _transcripcion(datos, True)}


# --------------------------------------------------------------- registro
def herramientas() -> list[dict]:
	erp = lambda: _app("erpnext")
	whatsapp = lambda: _app("lyra_whatsapp")
	return [
		{"nombre": "buscar_registros", "modulo": "CRM",
		 "descripcion": "Busca clientes, clientes potenciales, contactos, oportunidades, cotizaciones, pedidos o facturas por nombre, código o celular.",
		 "parametros": {"type": "object", "properties": {
			 "tipo": {"type": "string", "enum": list(TIPOS)},
			 "texto": {"type": "string", "description": "Nombre, código o celular a buscar. Vacío: los más recientes."},
			 "estado": {"type": "string", "description": "Estado exacto en el ERP (opcional), p. ej. Open, Overdue, Unpaid."},
			 "limite": {"type": "integer", "description": "Máximo de resultados (hasta 15)."}},
			 "required": ["tipo"]},
		 "funcion": buscar_registros, "disponible": erp},
		{"nombre": "ficha_cliente", "modulo": "CRM",
		 "descripcion": "Todo lo de un cliente: datos, saldo pendiente, últimas facturas, oportunidades y cotizaciones.",
		 "parametros": {"type": "object", "properties": {"cliente": {"type": "string", "description": "Nombre o código del cliente."}},
						"required": ["cliente"]},
		 "funcion": ficha_cliente, "disponible": lambda: erp() and _puede("Customer")},
		{"nombre": "cartera_vencida", "modulo": "Ventas",
		 "descripcion": "Quién debe: facturas vencidas con saldo, agrupadas por cliente, de mayor a menor deuda.",
		 "parametros": {"type": "object", "properties": {
			 "dias_minimos": {"type": "integer", "description": "Solo las vencidas hace más de estos días (0 = todas las vencidas)."}}},
		 "funcion": cartera_vencida, "disponible": lambda: erp() and _puede("Sales Invoice")},
		{"nombre": "embudo_ventas", "modulo": "CRM",
		 "descripcion": "Oportunidades abiertas por etapa del embudo, con cantidad y valor.",
		 "parametros": {"type": "object", "properties": {"solo_mias": {"type": "boolean", "description": "Solo las del usuario."}}},
		 "funcion": embudo_ventas, "disponible": lambda: erp() and _puede("Opportunity")},
		{"nombre": "ventas_del_periodo", "modulo": "Ventas",
		 "descripcion": "Total facturado en los últimos N días, número de facturas y mejores clientes.",
		 "parametros": {"type": "object", "properties": {"dias": {"type": "integer", "description": "Días hacia atrás (30 por defecto)."}}},
		 "funcion": ventas_del_periodo, "disponible": lambda: erp() and _puede("Sales Invoice")},
		{"nombre": "buscar_chats", "modulo": "WhatsApp",
		 "descripcion": "Busca chats de WhatsApp (API oficial «meta» y WAHA) por nombre, número o etiqueta.",
		 "parametros": {"type": "object", "properties": {
			 "texto": {"type": "string"}, "canal": {"type": "string", "enum": ["todos", "meta", "waha"]},
			 "estado": {"type": "string", "enum": ["abierto", "resuelto"]}}},
		 "funcion": buscar_chats, "disponible": whatsapp},
		{"nombre": "chats_sin_responder", "modulo": "WhatsApp",
		 "descripcion": "Chats abiertos donde el cliente escribió y nadie le ha respondido, los más antiguos primero.",
		 "parametros": {"type": "object", "properties": {"canal": {"type": "string", "enum": ["todos", "meta", "waha"]}}},
		 "funcion": chats_sin_responder, "disponible": whatsapp},
		{"nombre": "leer_chat", "modulo": "WhatsApp",
		 "descripcion": "Lee la conversación de un chat (para resumirla, analizarla o proponer una respuesta). Usa el canal y el id que da buscar_chats.",
		 "parametros": {"type": "object", "properties": {"canal": {"type": "string", "enum": ["meta", "waha"]}, "id": {"type": "string"}},
						"required": ["canal", "id"]},
		 "funcion": leer_chat, "disponible": whatsapp},
	]
