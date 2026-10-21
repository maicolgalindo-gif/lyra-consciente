"""Lyra se da cuenta: metricas por area y reporte semanal al dueno.

Nunca por persona: se agrupa por area, y un area con menos personas que el
minimo (Sense Ajustes, 3 por defecto) se suma a «Otras áreas», porque con 1 o 2
personas la cifra diria quien fue.

Las cifras salen de los datos (Sense Evento, Sense Aviso). Si la IA esta activa,
solo las pone en palabras; si no, sale un resumen simple. Nunca inventa numeros.
"""

from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, nowdate

OTRAS = "Otras áreas"
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def calcular(desde=None, hasta=None) -> dict:
	"""Cifras por area entre dos fechas (por defecto, los ultimos 7 dias)."""
	hasta = getdate(hasta or nowdate())
	desde = getdate(desde or add_days(hasta, -6))
	rango = {"desde": f"{desde} 00:00:00", "hasta": f"{hasta} 23:59:59"}
	eventos = frappe.db.sql(
		"""SELECT IFNULL(area, 'General') AS area, COUNT(*) AS operaciones, COUNT(DISTINCT usuario) AS personas,
			SUM(accion = 'Crear') AS creados
		FROM `tabSense Evento` WHERE creation BETWEEN %(desde)s AND %(hasta)s GROUP BY area""",
		rango, as_dict=True,
	)
	avisos = frappe.db.sql(
		"""SELECT IFNULL(area, 'General') AS area, tipo, estado, COUNT(*) AS n
		FROM `tabSense Aviso` WHERE creation BETWEEN %(desde)s AND %(hasta)s GROUP BY area, tipo, estado""",
		rango, as_dict=True,
	)
	minimo = frappe.db.get_single_value("Sense Ajustes", "min_personas_area") or 3
	pequenas = {e.area for e in eventos if (e.personas or 0) < minimo}
	areas: dict = defaultdict(lambda: {"operaciones": 0, "creados": 0, "personas": 0, "avisos": 0, "corregidas": 0, "deshechas": 0})
	for e in eventos:
		a = areas[OTRAS if e.area in pequenas else e.area]
		a["operaciones"] += int(e.operaciones or 0)
		a["creados"] += int(e.creados or 0)
		a["personas"] += int(e.personas or 0)
	for x in avisos:
		a = areas[OTRAS if x.area in pequenas else x.area]
		if x.tipo == "Aviso":
			a["avisos"] += int(x.n)
		else:
			a["corregidas"] += int(x.n)
			if x.estado == "Deshecho":
				a["deshechas"] += int(x.n)
	# «Otras áreas» tambien debe juntar al menos el minimo; si no, no se muestra el
	# detalle (aunque sea la unica: con 1 o 2 personas, la fila diria quien fue).
	if OTRAS in areas and areas[OTRAS]["personas"] < minimo:
		areas[OTRAS]["oculta"] = True
	filas = []
	for nombre, a in sorted(areas.items(), key=lambda kv: (kv[0] == OTRAS, -kv[1]["operaciones"])):
		omisiones = a["avisos"] + a["corregidas"]
		efectividad = round(100 * (1 - omisiones / a["operaciones"]), 1) if a["operaciones"] else 100.0
		filas.append({"area": nombre, **a, "omisiones": omisiones, "efectividad": max(efectividad, 0)})
	total_op = sum(f["operaciones"] for f in filas)
	total_om = sum(f["omisiones"] for f in filas)
	return {
		"desde": str(desde), "hasta": str(hasta), "areas": filas,
		"total": {"operaciones": total_op, "omisiones": total_om,
				  "corregidas": sum(f["corregidas"] for f in filas), "deshechas": sum(f["deshechas"] for f in filas),
				  "avisos": sum(f["avisos"] for f in filas),
				  "efectividad": round(100 * (1 - total_om / total_op), 1) if total_op else 100.0},
		"minimo": minimo,
	}


def _texto_simple(c: dict) -> str:
	t = c["total"]
	lineas = [
		_("Resumen de la semana ({0} a {1})").format(frappe.utils.format_date(c["desde"]), frappe.utils.format_date(c["hasta"])),
		"",
		_("Operaciones registradas: {0}. Efectividad de los procesos: {1}%.").format(t["operaciones"], t["efectividad"]),
		_("Lyra detectó {0} omisiones: completó {1} sola (se deshicieron {2}) y avisó {3}.").format(
			t["omisiones"], t["corregidas"], t["deshechas"], t["avisos"]),
		"",
	]
	for a in c["areas"]:
		if a.get("oculta"):
			continue
		lineas.append(_("{0}: {1} operaciones, {2}% de efectividad, {3} omisiones.").format(
			a["area"], a["operaciones"], a["efectividad"], a["omisiones"]))
	return "\n".join(lineas).strip()


def redactar(c: dict) -> str:
	"""El reporte en palabras. Con IA si esta activa; si no (o si falla), el resumen simple."""
	simple = _texto_simple(c)
	if not frappe.db.get_single_value("Sense Ajustes", "redactar_con_ia"):
		return simple
	try:
		from lyra_ia import cerebro

		if not cerebro.lista():
			return simple
		texto = cerebro.completar(
			[{"role": "system", "content": (
				"Eres Lyra y le escribes al dueño de la empresa su resumen semanal por WhatsApp o correo. En español, "
				"cálido y breve (máximo 10 líneas). Usa SOLO las cifras que te paso, sin inventar ninguna, y nunca "
				"nombres de personas: todo es por área. Termina con una sugerencia concreta si los datos la dan.")},
			 # Los grupos ocultos (menos personas que el minimo) no se le pasan a la IA.
			 {"role": "user", "content": json.dumps({**c, "areas": [x for x in c["areas"] if not x.get("oculta")]},
													ensure_ascii=False)}],
			funcion="sense.reporte", max_tokens=500,
		)
		return texto.strip() or simple
	except Exception:
		return simple


def enviar_reporte(forzar: bool = False) -> dict | None:
	"""Arma, guarda y envia el reporte. Lo llama el programador cada hora (o «Enviar ahora»)."""
	a = frappe.get_single("Sense Ajustes")
	if not forzar:
		ahora = now_datetime()
		if not (a.activo and a.reporte_activo) or DIAS[ahora.weekday()] != a.reporte_dia or ahora.hour != int(a.reporte_hora or 7):
			return None
		if a.ultimo_reporte and getdate(a.ultimo_reporte) == getdate(nowdate()):
			return None
	cifras = calcular()
	texto = redactar(cifras)
	destinos = []
	correos = [c.strip() for c in (a.reporte_correos or "").split(",") if c.strip()]
	if correos:
		try:
			frappe.sendmail(recipients=correos, subject=_("Lyra: tu resumen de la semana"), message=texto.replace("\n", "<br>"),
							delayed=False)
			destinos.append(", ".join(correos))
		except Exception:
			frappe.log_error(title="Lyra se da cuenta: no se pudo enviar el reporte por correo")
	if a.reporte_waha and "lyra_waha" in frappe.get_installed_apps():
		try:
			from lyra_waha.waha import enviar_texto

			enviar_texto(a.reporte_waha, texto)
			destinos.append(f"WhatsApp {a.reporte_waha}")
		except Exception:
			frappe.log_error(title="Lyra se da cuenta: no se pudo enviar el reporte por WAHA")
	rep = frappe.get_doc({"doctype": "Sense Reporte", "semana": cifras["desde"], "texto": texto,
						  "enviado_a": "\n".join(destinos) or _("(sin destinatarios: solo quedó guardado)"),
						  "cifras": json.dumps(cifras, ensure_ascii=False, indent=1)})
	rep.insert(ignore_permissions=True)
	frappe.db.set_single_value("Sense Ajustes", "ultimo_reporte", nowdate())
	frappe.db.commit()
	return {"reporte": rep.name, "texto": texto, "enviado_a": destinos}


def tick() -> None:
	"""Programador, cada hora: envia el reporte el dia y la hora configurados."""
	enviar_reporte()


# ------------------------------------------------------------- pantalla
@frappe.whitelist()
def tablero() -> dict:
	frappe.only_for("System Manager")
	a = frappe.get_single("Sense Ajustes")
	return {
		"activo": bool(a.activo),
		"cifras": calcular(),
		"reglas": frappe.get_all("Sense Regla", fields=["name", "titulo", "ref_doctype", "campo", "modo", "activa", "veces"],
								 order_by="activa desc, veces desc", limit_page_length=50),
		"avisos": frappe.get_all("Sense Aviso", fields=["tipo", "estado", "mensaje", "area", "creation"],
								 order_by="creation desc", limit_page_length=15),
		"reportes": frappe.get_all("Sense Reporte", fields=["name", "semana", "enviado_a", "creation"],
								   order_by="creation desc", limit_page_length=5),
		"reporte": {"activo": bool(a.reporte_activo), "dia": a.reporte_dia, "hora": a.reporte_hora},
	}


@frappe.whitelist(methods=["POST"])
def enviar_ahora() -> dict:
	frappe.only_for("System Manager")
	return enviar_reporte(forzar=True)


SUGERIDAS = [
	{"titulo": "Chat de WhatsApp resuelto sin etiqueta", "ref_doctype": "WhatsApp Conversacion", "evento": "Al guardar",
	 "campo": "etiquetas", "condicion": 'doc.estado == "Resuelta"', "modo": "Avisar", "app": "lyra_whatsapp"},
	{"titulo": "Cliente potencial sin celular", "ref_doctype": "Lead", "evento": "Al crear", "campo": "mobile_no",
	 "modo": "Avisar", "app": "erpnext"},
	{"titulo": "Oportunidad sin responsable", "ref_doctype": "Opportunity", "evento": "Al crear", "campo": "opportunity_owner",
	 "modo": "Completar", "valor": "{usuario}", "app": "erpnext"},
	{"titulo": "Cotización sin fecha de validez", "ref_doctype": "Quotation", "evento": "Al guardar", "campo": "valid_till",
	 "modo": "Avisar", "app": "erpnext"},
]


@frappe.whitelist(methods=["POST"])
def crear_sugeridas() -> dict:
	"""Reglas de ejemplo, apagadas: se revisan y se encienden una por una."""
	frappe.only_for("System Manager")
	instaladas = frappe.get_installed_apps()
	creadas = 0
	for r in SUGERIDAS:
		if r["app"] not in instaladas or frappe.db.exists("Sense Regla", {"titulo": r["titulo"]}):
			continue
		datos = {k: v for k, v in r.items() if k != "app"}
		frappe.get_doc({"doctype": "Sense Regla", "activa": 0, **datos}).insert()
		creadas += 1
	return {"creadas": creadas}
