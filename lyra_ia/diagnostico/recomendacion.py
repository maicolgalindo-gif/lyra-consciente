"""Despues de la entrevista: como Lyra va a ayudar al dueno.

Dos salidas distintas del mismo mapa confirmado (Diagnostico Empresa):

- Para el dueno, la AYUDA: en palabras simples, como Lyra lo va a ayudar a
  mejorar, cada punto atado a algo que el conto. Sin modulos, sin casillas y sin
  nada que aprobar.
- Para el Equipo Lyra, la RECOMENDACION de modulos (campo con permlevel 1, el
  dueno no lo ve). Quien decide que se activa es el equipo, no el dueno.

La recomendacion sale de reglas fijas que se leen aqui mismo. La IA, si esta
activa, solo redacta la ayuda a partir de esa recomendacion; si falla, la ayuda
se arma con textos fijos.
"""

from __future__ import annotations

import json
import unicodedata

import frappe
from frappe import _
from frappe.utils import now_datetime

from lyra_ia.diagnostico.entrevista import DT, _exigir

# Cada parte: a quien le sirve (palabras que la activan, buscadas en el mapa y
# en las respuestas), que apps la traen y para que sirve, dicho sin tecnicismos.
PARTES = [
	{"clave": "clientes", "nombre": "Clientes y ventas", "apps": ["erpnext"], "siempre": True, "prioridad": 1,
	 "para_que": "Tus clientes, cotizaciones y ventas en un solo lugar, con el seguimiento de cada uno.",
	 "senales": ["cliente", "venta", "vend", "cotiz", "pierden"]},
	{"clave": "whatsapp", "nombre": "WhatsApp de la empresa", "apps": ["frappe_whatsapp", "lyra_whatsapp"], "prioridad": 1,
	 "para_que": "Atender por WhatsApp desde Lyra, con el historial de cada cliente y mensajes automáticos.",
	 "senales": ["whatsapp", "redes", "instagram", "facebook", "chat", "mensaje"]},
	{"clave": "factura", "nombre": "Facturación electrónica", "apps": ["documentos_electronicos"], "prioridad": 1,
	 "para_que": "Facturar ante la DIAN desde la misma venta, sin pasar datos a otro programa.",
	 "senales": ["factur", "dian"], "colombia": True},
	{"clave": "inventario", "nombre": "Inventario", "apps": ["erpnext"], "prioridad": 2,
	 "para_que": "Saber qué tienes, qué se vende más y cuándo pedir, sin contar a mano.",
	 "senales": ["inventario", "bodega", "producto", "tienda", "stock", "mercanc", "maquillaje", "ropa", "repuesto", "vende"]},
	{"clave": "cobros", "nombre": "Cobros y cartera", "apps": ["erpnext"], "prioridad": 1,
	 "para_que": "Ver quién te debe, cuánto y desde cuándo, y recordarle a tiempo.",
	 "senales": ["deben", "cobr", "cartera", "credito", "fiado", "pagan"]},
	{"clave": "personas", "nombre": "Personas y nómina", "apps": ["hrms", "nomina_colombia"], "prioridad": 2,
	 "para_que": "Los datos de tu equipo, la nómina electrónica y las seguridades sociales.",
	 "senales": ["nomina", "empleado", "personas", "contador", "equipo"], "con_equipo": True},
	{"clave": "tablero", "nombre": "Cómo va el negocio", "apps": ["erpnext"], "prioridad": 2,
	 "para_que": "Ventas, gastos y lo que te deben, de un vistazo y al día.",
	 "senales": ["como va", "no se cuanto", "numeros", "ganancia", "reporte", "excel", "a mano", "cuaderno", "papel"]},
	{"clave": "sense", "nombre": "Lyra se da cuenta", "apps": ["lyra_ia"], "prioridad": 3,
	 "para_que": "Lyra revisa en segundo plano que no falten datos y le avisa en privado a quien los dejó.",
	 "senales": ["a mano", "se pierde", "olvid", "error", "desorden"], "con_equipo": True},
	{"clave": "mercadolibre", "nombre": "Ventas en MercadoLibre", "apps": ["mercadolibre_harmony"], "prioridad": 2,
	 "para_que": "Tus publicaciones y pedidos de MercadoLibre conectados con el inventario y la factura.",
	 "senales": ["mercadolibre", "mercado libre"]},
	{"clave": "salud", "nombre": "Pacientes y consultas", "apps": ["healthcare"], "prioridad": 1,
	 "para_que": "Historia clínica, citas y facturación del paciente.",
	 "senales": ["clinica", "consultorio", "ips", "paciente", "medic", "odontolog", "salud"]},
]


def _plano(texto: str) -> str:
	"""Minusculas y sin tildes, para buscar senales sin importar como se escribio."""
	t = unicodedata.normalize("NFKD", str(texto or "").lower())
	return "".join(c for c in t if not unicodedata.combining(c))


def _cita(mapa: dict, respuestas: list, senales: list[str]) -> str | None:
	"""El dato del dueno que activo la parte, para decirle el porque con sus palabras."""
	# Las senales van de la mas clara a la mas vaga: se busca la mas clara primero.
	for s in senales:
		for datos in mapa.values():
			for d in datos:
				if s in _plano(d):
					return d
	for s in senales:
		for r in respuestas:
			if s in _plano(r.get("respuesta")):
				return r["respuesta"][:80]
	return None


def _con_equipo(mapa: dict) -> bool:
	tam = _plano(" ".join(mapa.get("tamano") or []))
	return bool(tam) and "solo yo" not in tam


def _ya_factura(mapa: dict, respuestas: list) -> bool:
	texto = _plano(" ".join(mapa.get("obligaciones") or []) + " " +
				   " ".join(r["respuesta"] for r in respuestas if r.get("tema") == "obligaciones"))
	return ("facturo electr" in texto or "ya factur" in texto) and "no factur" not in texto


def proponer(mapa: dict, respuestas: list) -> list[dict]:
	instaladas = set(frappe.get_installed_apps())
	disponibles = set(_catalogo())
	partes = []
	for p in PARTES:
		cita = _cita(mapa, respuestas, p["senales"])
		porque = None
		if p["clave"] == "factura":
			obligaciones = _plano(" ".join(mapa.get("obligaciones") or []))
			if _ya_factura(mapa, respuestas):
				porque = _("Ya facturas electrónicamente: Lyra puede hacerlo desde la misma venta.")
			elif any(x in obligaciones for x in ("no sabe", "no se", "ni idea", "duda", "no tiene claro")):
				porque = _("No tienes claro qué te pide la DIAN.")
			else:
				porque = _("Aún no facturas electrónicamente y la DIAN lo exige.")
		elif cita:
			porque = _("Me dijiste «{0}».").format(cita)
		elif p.get("siempre"):
			porque = _("Es la base de todo lo demás.")
		if not porque:
			continue
		if p.get("con_equipo") and not _con_equipo(mapa):
			continue
		if not all(a in instaladas or a in disponibles for a in p["apps"]):
			continue
		partes.append({"clave": p["clave"], "nombre": p["nombre"], "para_que": p["para_que"], "porque": porque,
					   "prioridad": p["prioridad"], "instalada": all(a in instaladas for a in p["apps"]),
					   "elegida": p["prioridad"] < 3})
	# Lo que duele va primero: si una parte responde a un dolor, sube.
	for x in partes:
		p = next(p for p in PARTES if p["clave"] == x["clave"])
		dolor = next((d for d in (mapa.get("dolores") or []) if any(s in _plano(d) for s in p["senales"])), None)
		if dolor and x["clave"] != "sense":
			x.update(prioridad=0, dolor=True, elegida=True, porque=_("Me dijiste que te pesa «{0}».").format(dolor))
	partes.sort(key=lambda x: x["prioridad"])
	return partes


def _catalogo() -> list[str]:
	"""Las apps que esta instalacion sabe instalar (apps/catalog.json, junto al bench)."""
	import os

	ruta = os.path.join(frappe.utils.get_bench_path(), "apps", "catalog.json")
	try:
		with open(ruta) as f:
			apps = json.load(f).get("apps") or {}
		return list(apps.keys() if isinstance(apps, dict) else [a.get("name") for a in apps])
	except Exception:
		return []


NOMBRES_PROPIOS = ("excel", "whatsapp", "instagram", "facebook", "dian", "sg-sst", "siigo", "alegra", "world office", "mercadolibre")


def _min(dato: str) -> str:
	"""Pone en minuscula la primera letra, salvo que empiece por un nombre propio."""
	dato = dato.strip().rstrip(".")
	if not dato or _plano(dato).startswith(NOMBRES_PROPIOS) or dato[:2].isupper():
		return dato
	return dato[0].lower() + dato[1:]


def _resumen_simple(empresa: str, mapa: dict) -> str:
	def lista(clave, n=3):
		datos = [_min(d) for d in (mapa.get(clave) or []) if d.strip()][:n]
		if len(datos) < 2:
			return datos[0] if datos else ""
		return ", ".join(datos[:-1]) + " y " + datos[-1]

	partes = []
	for clave, molde in (("negocio", _("De {0} me quedo con esto: {1}.")), ("tamano", _("Son {1}.")),
						 ("herramientas", _("Hoy trabajan con {1}.")), ("dolores", _("Lo que más pesa: {1}."))):
		if lista(clave):
			partes.append(molde.format(empresa, lista(clave)))
	return " ".join(partes)


def _resumen(empresa: str, mapa: dict) -> str:
	simple = _resumen_simple(empresa, mapa)
	try:
		from lyra_ia import cerebro

		if not cerebro.lista():
			return simple
		texto = cerebro.completar(
			[{"role": "system", "content": (
				"Eres Lyra y acabas de entrevistar al dueño de una empresa colombiana. Escríbele en segunda persona, "
				"cálida y breve (máximo 3 frases, 60 palabras), lo que entendiste de su empresa. Usa solo los datos "
				"que te paso; nada inventado, sin tecnicismos ni palabras como 'módulo' o 'ERP'.")},
			 {"role": "user", "content": json.dumps({"empresa": empresa, "mapa": mapa}, ensure_ascii=False)}],
			funcion="diagnostico.resumen", max_tokens=200, temperatura=0.4,
		)
		return (texto or "").strip() or simple
	except Exception:
		return simple


# Como suena cada parte para el dueno: lo que Lyra va a hacer, no el nombre del modulo.
AYUDA = {
	"clientes": ("Tus ventas y clientes en orden", "Cada venta queda registrada con su cliente, sin cuaderno, y te recuerdo a quién hacerle seguimiento."),
	"whatsapp": ("Que nadie se quede sin respuesta", "Atiendes WhatsApp desde Lyra, con la historia de cada cliente y respuestas automáticas para lo de siempre."),
	"factura": ("Ponerte al día con la DIAN", "Te muestro qué te pide la DIAN y facturas electrónicamente desde la misma venta."),
	"inventario": ("Saber qué se mueve", "Te digo qué productos se venden más, cuáles no salen y cuándo te conviene pedir."),
	"cobros": ("Saber quién te debe", "Te muestro quién te debe, cuánto y desde cuándo, y te aviso a tiempo para cobrar."),
	"personas": ("Tu equipo en orden", "Los datos de tu equipo y su nómina en un solo lugar, al día con lo que exige la ley."),
	"tablero": ("Ver cómo va el negocio", "Cada semana te cuento en pocas palabras cómo te fue: ventas, gastos y qué cambió."),
	"sense": ("Que no se escapen detalles", "Reviso en segundo plano que no falten datos y le aviso a quien corresponda."),
	"mercadolibre": ("Tus ventas en MercadoLibre conectadas", "Tus pedidos de MercadoLibre llegan solos y se descuentan del inventario."),
	"salud": ("Tus pacientes en orden", "Historia clínica, citas y cobros de cada paciente en un solo lugar."),
}


def _ayuda_simple(nombre: str, resumen: str, partes: list[dict]) -> dict:
	puntos = []
	for p in partes:
		if p["clave"] not in AYUDA or len(puntos) >= 4:
			continue
		titulo, como = AYUDA[p["clave"]]
		puntos.append({"titulo": titulo, "como": como, "porque": p["porque"]})
	return {"titulo": _("Así te voy a ayudar, {0}.").format(nombre) if nombre else _("Así te voy a ayudar."),
			"resumen": resumen, "puntos": puntos,
			"primero": _("Empecemos por lo primero: {0}.").format(puntos[0]["titulo"].lower()) if puntos else ""}


def _ayuda(nombre: str, mapa: dict, partes: list[dict], resumen: str) -> dict:
	simple = _ayuda_simple(nombre, resumen, partes)
	try:
		from lyra_ia import cerebro

		if not cerebro.lista():
			return simple
		disponibles = [{"que_hace": AYUDA[p["clave"]][1], "motivo": p["porque"]} for p in partes if p["clave"] in AYUDA]
		datos = cerebro.completar_json(
			[{"role": "system", "content": (
				"Eres Lyra y acabas de conocer al dueño de una empresa colombiana. Ahora le dices cómo lo vas a ayudar a "
				"mejorar. En español de Colombia, en segunda persona, cálida y concreta, sin tecnicismos ni palabras como "
				"'módulo', 'ERP', 'sistema' o nombres de programas. Respeta cómo pidió que le hablaras (en el tema "
				"acuerdo del mapa). Solo puedes prometer lo que está en 'disponibles'; nada más. Devuelve SOLO un JSON:\n"
				'{"titulo": "...", "resumen": "...", "puntos": [{"titulo": "...", "como": "...", "porque": "..."}], '
				'"primero": "..."}\n'
				"- titulo: una frase corta dirigida a él por su nombre.\n"
				"- resumen: lo que entendiste de él y su empresa, máximo 3 frases, sin exagerar ni inventar.\n"
				"- puntos: de 2 a 4, del más urgente al menos. titulo de 2 a 6 palabras; como: qué vas a hacer tú en su "
				"día a día (máximo 25 palabras); porque: lo que él te contó que lo justifica, con sus palabras.\n"
				"- primero: una frase con lo primero que van a hacer juntos.")},
			 {"role": "user", "content": json.dumps({"nombre": nombre, "mapa": mapa, "disponibles": disponibles},
													ensure_ascii=False)}],
			funcion="diagnostico.ayuda", max_tokens=700, temperatura=0.4,
		)
		puntos = [{"titulo": str(x.get("titulo", ""))[:60], "como": str(x.get("como", ""))[:220],
				   "porque": str(x.get("porque", ""))[:160]} for x in (datos.get("puntos") or []) if isinstance(x, dict)][:4]
		if not puntos or not all(p["titulo"] and p["como"] for p in puntos):
			return simple
		return {"titulo": str(datos.get("titulo") or simple["titulo"])[:120], "resumen": str(datos.get("resumen") or resumen)[:600],
				"puntos": puntos, "primero": str(datos.get("primero") or "")[:240]}
	except Exception:
		return simple


@frappe.whitelist(methods=["POST"])
def plan(name: str, rehacer: int = 0) -> dict:
	"""Como Lyra va a ayudar al dueno (se guarda y se reutiliza). La recomendacion de
	modulos se guarda aparte, solo para el Equipo Lyra, y no se devuelve aqui."""
	_exigir()
	doc = frappe.get_doc(DT, name)
	if doc.estado != "Confirmado":
		frappe.throw(_("Primero confirma tu empresa."))
	guardado = json.loads(doc.ayuda or "null")
	if guardado and not int(rehacer):
		return guardado
	mapa = json.loads(doc.mapa or "{}")
	respuestas = json.loads(doc.respuestas or "[]")
	partes = proponer(mapa, respuestas)
	nombre = doc.nombre_negocio or doc.empresa
	from lyra_ia.diagnostico.entrevista import nombre_dueno

	ayuda = _ayuda(nombre_dueno(doc), mapa, partes, _resumen(nombre, mapa))
	doc.ayuda = json.dumps(ayuda, ensure_ascii=False)
	doc.recomendacion = json.dumps({"partes": partes}, ensure_ascii=False)
	doc.save(ignore_permissions=True)
	return ayuda


# --------------------------------------------- la mesa del Equipo Lyra
# Hasta aquí la recomendación se calculaba y se guardaba, pero no había dónde
# leerla: el diagnóstico terminaba en un campo JSON que nadie abría. Esto es la
# mesa donde el equipo la revisa y decide qué se activa. Decide el equipo, no
# Lyra y no el dueño.
def _estado_apps(partes: list[dict]) -> list[dict]:
	instaladas = set(frappe.get_installed_apps())
	salida = []
	for p in partes:
		base = next((x for x in PARTES if x["clave"] == p["clave"]), None)
		apps = base["apps"] if base else []
		salida.append({**p, "apps": apps,
					   "faltan": [a for a in apps if a not in instaladas]})
	return salida


@frappe.whitelist()
def para_el_equipo(name: str | None = None) -> dict:
	"""La recomendación de un diagnóstico, con lo ya decidido y lo que falta instalar."""
	frappe.only_for("Equipo Lyra")
	if not name:
		name = frappe.db.get_value(DT, {"estado": "Confirmado"}, "name", order_by="confirmado_el desc")
	if not name:
		return {"hay": False, "diagnosticos": []}
	doc = frappe.get_doc(DT, name)
	guardado = json.loads(doc.recomendacion or "null") or {}
	partes = guardado.get("partes")
	if not partes:
		partes = proponer(json.loads(doc.mapa or "{}"), json.loads(doc.respuestas or "[]"))
	decision = guardado.get("decision") or {}
	for p in partes:
		p["elegida"] = decision.get(p["clave"], p.get("elegida", False))
	return {
		"hay": True,
		"name": doc.name,
		"empresa": doc.nombre_negocio or doc.empresa,
		"dueno": doc.nombre_dueno,
		"confirmado_el": str(doc.confirmado_el or ""),
		"resumen": _resumen(doc.nombre_negocio or doc.empresa, json.loads(doc.mapa or "{}")),
		"partes": _estado_apps(partes),
		"decidido_el": guardado.get("decidido_el"),
		"decidido_por": guardado.get("decidido_por"),
		"diagnosticos": frappe.get_all(DT, filters={"estado": "Confirmado"},
									   fields=["name", "nombre_negocio", "confirmado_el"],
									   order_by="confirmado_el desc", limit=20),
	}


@frappe.whitelist(methods=["POST"])
def decidir(name: str, elegidas: str | list) -> dict:
	"""Guarda qué se activa. La decisión es del equipo y queda con fecha y firma."""
	frappe.only_for("Equipo Lyra")
	doc = frappe.get_doc(DT, name)
	claves = frappe.parse_json(elegidas) if isinstance(elegidas, str) else (elegidas or [])
	guardado = json.loads(doc.recomendacion or "null") or {}
	partes = guardado.get("partes") or proponer(json.loads(doc.mapa or "{}"), json.loads(doc.respuestas or "[]"))
	for p in partes:
		p["elegida"] = p["clave"] in claves
	guardado.update({"partes": partes, "decision": {p["clave"]: p["elegida"] for p in partes},
					 "decidido_el": str(now_datetime()), "decidido_por": frappe.session.user})
	doc.recomendacion = json.dumps(guardado, ensure_ascii=False)
	doc.save(ignore_permissions=True)
	elegidas_nombres = [p["nombre"] for p in partes if p["elegida"]]
	return {"ok": True, "elegidas": elegidas_nombres,
			"faltan_instalar": sorted({a for p in _estado_apps(partes) if p["elegida"] for a in p["faltan"]})}
