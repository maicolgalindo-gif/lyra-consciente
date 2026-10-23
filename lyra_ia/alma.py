"""El alma: lo que Lyra sabe de esta empresa.

Reemplaza al antiguo «Lo que la IA debe saber del negocio», que habia que escribir
a mano. El alma se llena sola con lo que Lyra va conociendo:

- la empresa (nombre, NIT, pais);
- la entrevista del dueno, ya confirmada (Diagnostico Empresa), y como Lyra le dijo que lo ayudaria;
- como trabaja cada area por dentro, segun lo que conto su propia gente en las
  entrevistas: sin nombres y con el mismo minimo de personas que las metricas;
- lo que se vende (los productos mas vendidos de los ultimos 90 dias);
- el tamano de la base de clientes.

Empresa, ventas y clientes salen de ERPNext solo si esta instalado.

Se rehace cada dia y cada vez que se confirma un diagnostico. Las notas del
equipo Lyra (lo que no se puede aprender solo: tono, politicas) se suman al
final. Todo lo arma este codigo con datos reales: nada inventado ni escrito por
la IA, porque es justo lo que la IA va a usar como verdad.

Solo la ve el rol «Equipo Lyra»; el cliente no.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime, nowdate

DT = "Lyra Alma"
ROL = "Equipo Lyra"
CACHE = "lyra_alma_texto"


def _empresa() -> str:
	from lyra_ia.entorno import empresa

	return empresa()


def _de_la_empresa(fuentes: list) -> list[str]:
	from lyra_ia.entorno import hay_doctype

	nombre = _empresa()
	if not nombre:
		return []
	if not hay_doctype("Company") or not frappe.db.exists("Company", nombre):
		# Sin ERPNext: solo el nombre.
		fuentes.append(_("Nombre de la empresa"))
		return [_("Empresa: {0}.").format(nombre)]
	c = frappe.db.get_value("Company", nombre, ["company_name", "tax_id", "country"], as_dict=True)
	fuentes.append(_("Datos de la empresa"))
	linea = c.company_name
	if c.tax_id:
		linea += f" (NIT {c.tax_id})"
	if c.country:
		linea += f", {_(c.country)}"
	return [_("Empresa: {0}.").format(linea)]


def _del_diagnostico(fuentes: list) -> list[str]:
	if not frappe.db.exists("DocType", "Diagnostico Empresa"):
		return []
	d = frappe.get_all("Diagnostico Empresa", filters={"estado": "Confirmado"},
					   fields=["name", "mapa", "ayuda", "nombre_dueno", "nombre_negocio", "confirmado_el"], order_by="confirmado_el desc", limit=1)
	if not d:
		return []
	d = d[0]
	from lyra_ia.diagnostico.entrevista import TEMAS

	mapa = json.loads(d.mapa or "{}")
	fuentes.append(_("Entrevista con el dueño ({0})").format(frappe.utils.format_date(d.confirmado_el)))
	lineas = []
	if d.nombre_dueno or d.nombre_negocio:
		lineas.append(_("Dueño: {0}. Negocio: {1}.").format(d.nombre_dueno or _("sin nombre"), d.nombre_negocio or _("sin nombre")))
	lineas.append(_("Lo que contó el dueño en la entrevista:"))
	for t in TEMAS:
		datos = [x for x in (mapa.get(t["clave"]) or []) if x]
		if datos:
			lineas.append(f"- {t['nombre']}: {'; '.join(datos)}.")
	ayuda = json.loads(d.ayuda or "null")
	if ayuda and ayuda.get("puntos"):
		lineas.append(_("Lo que Lyra le dijo que haría para ayudarlo: {0}.").format("; ".join(p["titulo"] for p in ayuda["puntos"])))
	return lineas


def _de_como_trabajan(fuentes: list) -> list[str]:
	"""Como funciona la empresa por dentro, segun lo que conto su propia gente.

	Sale de las entrevistas a los funcionarios, pero NUNCA con nombres: por area
	y con el mismo minimo de personas que las metricas, porque un area de una o
	dos personas delata a quien lo conto. Sin esto, Lyra sabe que vende la
	empresa pero no como trabaja, que es justo lo que le contaron."""
	if not frappe.db.exists("DocType", "Diagnostico Funcionario"):
		return []
	filas = frappe.get_all("Diagnostico Funcionario", filters={"estado": "Confirmado"},
						   fields=["area", "cargo_nombre", "mapa"])
	if not filas:
		return []
	try:
		minimo = int(frappe.db.get_single_value("Sense Ajustes", "min_personas_area") or 3)
	except Exception:
		minimo = 3
	areas: dict = {}
	for f in filas:
		caja = areas.setdefault(f.area or _("Otras áreas"), {"personas": 0, "cargos": set(), "proceso": [], "dolores": [], "herramientas": []})
		caja["personas"] += 1
		if f.cargo_nombre:
			caja["cargos"].add(f.cargo_nombre)
		mapa = frappe.parse_json(f.mapa or "{}") or {}
		for clave in ("proceso", "dolores", "herramientas"):
			caja[clave].extend(x for x in (mapa.get(clave) or []) if x)
	lineas = [_("Cómo trabaja la empresa por dentro, según su propia gente:")]
	sueltas: dict = {"dolores": [], "herramientas": []}
	for nombre, c in sorted(areas.items(), key=lambda kv: -kv[1]["personas"]):
		if c["personas"] < minimo:
			# Area pequena: sus pasos y sus cargos dirian quien lo conto.
			for clave in sueltas:
				sueltas[clave].extend(c[clave])
			continue
		partes = [_("{0} ({1} personas)").format(nombre, c["personas"])]
		if c["proceso"]:
			partes.append(_("así trabajan: {0}").format("; ".join(dict.fromkeys(c["proceso"]))[:400]))
		if c["herramientas"]:
			partes.append(_("con qué: {0}").format("; ".join(dict.fromkeys(c["herramientas"]))[:200]))
		if c["dolores"]:
			partes.append(_("lo que les cuesta: {0}").format("; ".join(dict.fromkeys(c["dolores"]))[:300]))
		lineas.append("- " + partes[0] + ". " + ". ".join(x[0].upper() + x[1:] for x in partes[1:]) + ".")
	if any(sueltas.values()):
		trozos = []
		if sueltas["dolores"]:
			trozos.append(_("lo que les cuesta: {0}").format("; ".join(dict.fromkeys(sueltas["dolores"]))[:300]))
		if sueltas["herramientas"]:
			trozos.append(_("con qué: {0}").format("; ".join(dict.fromkeys(sueltas["herramientas"]))[:200]))
		lineas.append("- " + _("Otras áreas") + ". " + ". ".join(x[0].upper() + x[1:] for x in trozos) + ".")
	fuentes.append(_("Entrevistas a {0} personas de la empresa").format(len(filas)))
	return lineas if len(lineas) > 1 else []


def _de_lo_que_vende(fuentes: list) -> list[str]:
	from lyra_ia.entorno import hay_doctype

	if not hay_doctype("Sales Invoice Item") or not hay_doctype("Item"):
		return []
	filas = frappe.db.sql(
		"""SELECT sii.item_name, SUM(sii.qty) AS cantidad
		FROM `tabSales Invoice Item` sii JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1 AND si.posting_date >= %s
		GROUP BY sii.item_name ORDER BY cantidad DESC LIMIT 15""",
		add_days(nowdate(), -90), as_dict=True,
	)
	if filas:
		fuentes.append(_("Ventas de los últimos 90 días"))
		return [_("Lo que más se vende: {0}.").format(", ".join(f.item_name for f in filas))]
	productos = frappe.get_all("Item", filters={"disabled": 0, "is_sales_item": 1}, pluck="item_name",
							   order_by="modified desc", limit=15)
	if productos:
		fuentes.append(_("Productos registrados"))
		return [_("Productos que vende: {0}.").format(", ".join(productos))]
	return []


def _de_los_clientes(fuentes: list) -> list[str]:
	from lyra_ia.entorno import hay_doctype

	if not hay_doctype("Customer"):
		return []
	total = frappe.db.count("Customer", {"disabled": 0})
	if not total:
		return []
	fuentes.append(_("Clientes"))
	return [_("Tiene {0} clientes activos registrados.").format(total)]


def componer() -> tuple[str, list[str]]:
	"""El alma en texto, y de donde salio cada parte."""
	fuentes: list[str] = []
	lineas: list[str] = []
	for parte in (_de_la_empresa, _del_diagnostico, _de_como_trabajan, _de_lo_que_vende, _de_los_clientes):
		try:
			bloque = parte(fuentes)
		except Exception:
			frappe.log_error(title=f"Alma: no se pudo leer {parte.__name__}")
			continue
		if bloque:
			lineas.extend(bloque + [""])
	return "\n".join(lineas).strip(), fuentes


def _guardar() -> None:
	texto, fuentes = componer()
	frappe.db.set_single_value(DT, {"alma": texto, "fuentes": "\n".join(fuentes), "actualizada_el": now_datetime()})
	frappe.cache.delete_value(CACHE)


def texto() -> str:
	"""Lo que la IA recibe como contexto del negocio (alma + notas del equipo)."""
	guardado = frappe.cache.get_value(CACHE, expires=True)
	if guardado is not None:
		return guardado
	alma = (frappe.db.get_single_value(DT, "alma") or "").strip()
	notas = (frappe.db.get_single_value(DT, "notas_equipo") or "").strip()
	completo = "\n\n".join(x for x in (alma, notas) if x)
	frappe.cache.set_value(CACHE, completo, expires_in_sec=3600)
	return completo


def contexto_para_ia() -> str:
	"""El bloque listo para pegar al final de un mensaje de sistema."""
	t = texto()
	return f"\n\nLo que sabes de esta empresa:\n{t}" if t else ""


# ------------------------------------------------------------- disparadores
def al_confirmar_diagnostico(doc, method=None) -> None:
	"""doc_events de Diagnostico Empresa: al confirmar (o aprobar el plan), el alma aprende."""
	if doc.estado == "Confirmado":
		frappe.enqueue("lyra_ia.alma.actualizar_en_segundo_plano", queue="short", enqueue_after_commit=True)


def actualizar_en_segundo_plano() -> None:
	_guardar()
	frappe.db.commit()


def al_guardar_notas(doc, method=None) -> None:
	frappe.cache.delete_value(CACHE)


@frappe.whitelist(methods=["POST"])
def actualizar() -> dict:
	"""Boton «Actualizar ahora» del alma."""
	frappe.only_for(ROL)
	_guardar()
	return {"ok": True}
