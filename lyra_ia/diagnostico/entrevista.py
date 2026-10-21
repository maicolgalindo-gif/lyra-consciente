"""Primer acercamiento: Lyra entrevista al dueno de la empresa.

Una pregunta a la vez. Con cada respuesta se extraen datos cortos que dibujan el
mapa de la empresa en la pantalla (www/lyra.html).

Primero la persona y despues el negocio: Lyra conoce al dueno (quien es, su
historia, como trabaja) y acuerdan como se van a ayudar; solo entonces pasa a la
empresa (negocio, tamaño, como trabajan hoy, lo que duele, obligaciones, equipo).

No hay un numero fijo de preguntas. Con la IA activa (lyra_ia.cerebro), Lyra
decide que preguntar despues y cuando ya sabe suficiente: a un negocio le
preguntara mas y a otro menos. La unica condicion es pasar por todos los temas.
Sin IA sigue un guion fijo, una pregunta por tema: la entrevista funciona igual.

Al final el dueno ve su mapa, lo corrige y lo confirma (Diagnostico Empresa).
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

DT = "Diagnostico Empresa"
TEMAS = [
	{"clave": "persona", "nombre": "Quién eres",
	 "pregunta": "Antes de hablar de tu empresa, quiero conocerte a ti. ¿Cómo te llamas, qué haces en la empresa y cómo llegaste hasta aquí?",
	 "sugerencias": []},
	{"clave": "acuerdo", "nombre": "Cómo nos ayudamos",
	 "pregunta": "Voy a trabajar a tu lado todos los días. ¿En qué te gustaría que te ayudara, y cómo prefieres que te hable: directo o con más detalle?",
	 "sugerencias": ["Que me avise lo importante", "Que me ahorre trabajo", "Directo y corto", "Con detalle"]},
	{"clave": "negocio", "nombre": "Negocio",
	 "pregunta": "Ahora sí, cuéntame de tu empresa: ¿a qué se dedica y qué le vendes a tus clientes?",
	 "sugerencias": []},
	{"clave": "tamano", "nombre": "Tamaño",
	 "pregunta": "¿Cuántas personas trabajan contigo y en cuántas sedes o puntos atienden?",
	 "sugerencias": ["Solo yo", "De 2 a 10 personas", "De 11 a 50 personas", "Más de 50"]},
	{"clave": "herramientas", "nombre": "Cómo trabajan hoy",
	 "pregunta": "¿Con qué llevan hoy el negocio? Ventas, facturas, clientes, inventario…",
	 "sugerencias": ["Excel", "Un software contable", "WhatsApp personal", "En papel", "Otro sistema"]},
	{"clave": "dolores", "nombre": "Lo que duele",
	 "pregunta": "Si pudieras arreglar una sola cosa del día a día mañana mismo, ¿cuál sería?",
	 "sugerencias": ["No sé cuánto me deben", "Se pierden clientes", "Mucho trabajo a mano", "No sé cómo va el negocio"]},
	{"clave": "obligaciones", "nombre": "Obligaciones",
	 "pregunta": "¿Ya facturas electrónicamente? ¿Y la nómina electrónica y el SG-SST, cómo los llevan?",
	 "sugerencias": ["Facturo electrónicamente", "La nómina la hace un contador", "Aún no tenemos SG-SST"]},
	{"clave": "equipo", "nombre": "Equipo",
	 "pregunta": "Por último, ¿qué cargos o áreas hay en tu empresa? Así sé a quién conocer después.",
	 "sugerencias": ["Ventas", "Facturación", "Atención al cliente", "Operación", "Administración"]},
]
CLAVES = [t["clave"] for t in TEMAS]
# No es un numero de preguntas: es un freno de seguridad por si la IA nunca da
# por terminada la entrevista. Nadie deberia llegar aqui en una conversacion normal.
TOPE_SEGURIDAD = 60
SALUDO = "Hola, soy Lyra. Voy a estar contigo en el día a día, así que primero quiero conocerte. Habla con calma: puedes responder hablando o escribiendo."


def _empresa() -> str:
	"""La empresa de ERPNext si esta instalado; si no, vacio (la entrevista funciona igual)."""
	from lyra_ia.entorno import hay_app

	if not hay_app("erpnext"):
		return ""
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company") or ""


def _voz_lista() -> bool:
	from lyra_ia import voz

	try:
		return voz.lista()
	except Exception:
		return False


def nombre_dueno(doc) -> str:
	"""Como llamar al dueno: como se presento; si no, su usuario (salvo Administrator)."""
	if doc.get("nombre_dueno"):
		return doc.nombre_dueno
	if frappe.session.user == "Administrator":
		return ""
	return (frappe.utils.get_fullname(frappe.session.user) or "").split(" ")[0]


def _exigir():
	frappe.only_for("System Manager")


def _actual(crear: bool = True):
	nombre = frappe.db.get_value(DT, {"empresa": _empresa(), "estado": "En curso"}, "name", order_by="modified desc")
	if nombre:
		return frappe.get_doc(DT, nombre)
	if not crear:
		return None
	doc = frappe.get_doc({"doctype": DT, "empresa": _empresa(), "entrevistado": frappe.session.user, "estado": "En curso",
						  "respuestas": "[]", "mapa": json.dumps({k: [] for k in CLAVES})})
	doc.insert(ignore_permissions=True)
	return doc


def _leer(doc) -> tuple[list, dict]:
	respuestas = json.loads(doc.respuestas or "[]")
	mapa = json.loads(doc.mapa or "{}")
	for k in CLAVES:
		mapa.setdefault(k, [])
	return respuestas, mapa


def _cubiertos(respuestas: list, mapa: dict | None = None) -> dict:
	"""Cuantas veces se toco cada tema. Tambien cuenta si ya tiene datos en el mapa,
	aunque salieran de una pregunta de otro tema: asi no se le pregunta al dueno
	algo que ya conto."""
	cuenta = {k: 0 for k in CLAVES}
	for r in respuestas:
		if r.get("tema") in cuenta:
			cuenta[r["tema"]] += 1
	for k, datos in (mapa or {}).items():
		if k in cuenta and datos and not cuenta[k]:
			cuenta[k] = 1
	return cuenta


def _pregunta_guion(respuestas: list, mapa: dict | None = None) -> dict | None:
	cuenta = _cubiertos(respuestas, mapa)
	tema = next((t for t in TEMAS if cuenta[t["clave"]] == 0), None)
	if not tema:
		return None
	return {"tema": tema["clave"], "pregunta": tema["pregunta"], "sugerencias": tema["sugerencias"]}


def _extraer_guion(tema: str, respuesta: str) -> list[str]:
	"""Sin IA: la respuesta misma, partida en piezas si es una lista."""
	texto = respuesta.strip().rstrip(".")
	if tema in ("herramientas", "equipo") and ("," in texto or " y " in texto):
		partes = [p.strip(" .") for p in texto.replace(" y ", ",").split(",")]
		return [p[:60] for p in partes if p][:8]
	return [texto[:90]] if texto else []


# Que significa cada tema, para que la IA no mezcle (en la prueba metio «muchos
# productos» en tamaño, que es de personas y sedes).
DEFINICIONES = {
	"persona": "quién es el dueño: nombre, su papel en la empresa, su historia, cómo trabaja",
	"acuerdo": "en qué quiere que Lyra lo ayude y cómo prefiere que le hable",
	"negocio": "a qué se dedica la empresa, qué vende, a quién, cómo se llama el negocio",
	"tamano": "cuántas personas trabajan y en cuántas sedes o puntos; volumen aproximado de ventas",
	"herramientas": "con qué llevan hoy ventas, cuentas, clientes e inventario",
	"dolores": "lo que le cuesta, le preocupa o le quita tiempo",
	"obligaciones": "facturación electrónica, nómina electrónica, impuestos, SG-SST: qué hace y qué no",
	"equipo": "qué cargos o áreas hay y qué hace cada persona",
}


def _fase(cuenta: dict) -> str:
	if not cuenta["persona"] or not cuenta["acuerdo"]:
		falta = [t["nombre"] for t in TEMAS[:2] if not cuenta[t["clave"]]]
		return ("PERSONA. Todavía no preguntes nada del negocio. Falta: " + ", ".join(falta) +
				". Si ya sabes su nombre, pregunta por su papel, su historia o cómo quiere que lo ayudes.")
	return "EMPRESA. Ya conoces a la persona; ahora entiende su empresa."


def _con_ia(respuestas: list, mapa: dict) -> dict | None:
	"""La IA ordena el mapa con la ultima respuesta y decide que preguntar despues."""
	from lyra_ia import cerebro

	if not cerebro.lista():
		return None
	cuenta = _cubiertos(respuestas, mapa)
	pendientes = [t["clave"] for t in TEMAS if cuenta[t["clave"]] == 0]
	temas = "\n".join(f"- {t['clave']} ({t['nombre']}): {DEFINICIONES[t['clave']]}" for t in TEMAS)
	sistema = (
		"Eres Lyra, la inteligencia de un ERP colombiano. Vas a trabajar todos los días al lado del dueño de esta "
		"empresa y lo estás conociendo por primera vez. Hablas en español de Colombia, cálida, cercana y natural, "
		"como una persona que de verdad escucha; sin tecnicismos ni palabras como 'módulo', 'ERP' o 'sistema'.\n\n"
		"Cómo conduces la conversación:\n"
		"1. Primero la PERSONA (persona y acuerdo) y después la EMPRESA. No mezcles: hasta conocerlo no preguntes "
		"del negocio.\n"
		"2. No hay un número fijo de preguntas. Profundiza donde haya algo importante y pasa rápido por lo que ya "
		"quedó claro. Tú decides cuántas.\n"
		"3. Cada pregunta nace de lo que te acaban de decir: retoma un detalle suyo. Una sola pregunta, máximo 30 "
		"palabras, ABIERTA (que no se responda con sí o no).\n"
		"4. Usa su nombre muy de vez en cuando (no al inicio de cada pregunta): suena a vendedor.\n"
		"5. Si una respuesta se contradice o queda vaga, pide que te aclare con naturalidad.\n"
		"6. No ofrezcas nada ni prometas ayudas ('¿quieres que revisemos…?'): ahora solo estás conociendo. "
		"Al final se le dirá cómo lo vas a ayudar.\n"
		"7. No termines solo porque ya tocaste todos los temas. Antes de terminar entiende bien lo que le duele: "
		"por qué pasa, desde cuándo, cuánto le afecta y qué ha intentado. Si una respuesta fue corta o vaga "
		"('no sé', 'sí'), vuelve sobre ella de otra forma.\n"
		"8. Termina (completo: true) cuando conozcas a la persona y entiendas su empresa lo suficiente para "
		"decirle cómo lo vas a ayudar.\n\n"
		f"Fase actual: {_fase(cuenta)}\n\n"
		f"Temas:\n{temas}\n"
		f"Temas sin tocar: {', '.join(pendientes) or 'ninguno'}.\n\n"
		"Recibes el mapa actual (lo que ya sabes, por tema) y la conversación. Devuelve SOLO un JSON:\n"
		'{"mapa": {"<tema>": ["dato", ...]}, "nombre_dueno": null, "nombre_negocio": null, "siguiente": {"tema": "<tema>", '
		'"pregunta": "...", "sugerencias": []}, "completo": false}\n'
		"- mapa: cada dato va en el tema que le corresponde según las definiciones, aunque la pregunta fuera de otro "
		"tema (si en una pregunta personal te dice en qué quiere ayuda, eso va en acuerdo). Un dato va en un solo tema.\n"
		"  Devuelve SOLO los temas que cambian con la última respuesta, cada uno con su lista COMPLETA ya ordenada: "
		"lo que había más lo nuevo, sin repetir ideas con otras palabras, máximo 6 datos de 2 a 8 palabras, en "
		"tercera persona. Si algo nuevo contradice lo anterior, deja lo más reciente. Nada inventado ni exagerado.\n"
		"- nombre_dueno: su nombre de pila si lo dijo (con mayúscula inicial); si no, null.\n"
		"- nombre_negocio: el nombre de su negocio si lo dijo; si no, null.\n"
		"- siguiente.tema: la clave del tema de tu pregunta.\n"
		"- sugerencias: de 0 a 4 respuestas cortas para tocar; ninguna en preguntas personales abiertas.\n"
		"- completo: true solo si no quedan temas sin tocar; entonces siguiente es null."
	)
	actual = {k: v for k, v in mapa.items() if v}
	entrevista = "\n".join(f"[{r['tema']}] Lyra: {r['pregunta']}\nDueño: {r['respuesta']}" for r in respuestas)
	datos = cerebro.completar_json(
		[{"role": "system", "content": sistema},
		 {"role": "user", "content": f"Mapa actual:\n{json.dumps(actual, ensure_ascii=False)}\n\nConversación:\n{entrevista}"}],
		funcion="diagnostico.entrevista", max_tokens=900, temperatura=0.5,
	)
	return datos if isinstance(datos, dict) else None


def _vista(doc, respuestas: list, mapa: dict, siguiente: dict | None) -> dict:
	cuenta = _cubiertos(respuestas, mapa)
	return {
		"name": doc.name,
		"empresa": doc.nombre_negocio or doc.empresa,
		"saludo": SALUDO if not respuestas else None,
		"temas": [{"clave": t["clave"], "nombre": t["nombre"], "listo": cuenta[t["clave"]] > 0} for t in TEMAS],
		"mapa": mapa,
		"siguiente": siguiente,
		"completo": siguiente is None,
		"estado": doc.estado,
		"nombre_usuario": nombre_dueno(doc),
		"voz": _voz_lista(),
	}


# ------------------------------------------------------------------- API
@frappe.whitelist(methods=["POST"])
def estado() -> dict:
	"""POST y no GET: puede crear la entrevista, y Frappe descarta lo que se guarda en un GET."""
	_exigir()
	doc = _actual()
	respuestas, mapa = _leer(doc)
	pendiente = frappe.cache.get_value(f"lyra_diag_siguiente:{doc.name}", expires=True)
	siguiente = pendiente if pendiente is not None else _pregunta_guion(respuestas, mapa)
	return _vista(doc, respuestas, mapa, siguiente)


@frappe.whitelist(methods=["POST"])
def responder(name: str, tema: str, pregunta: str, respuesta: str) -> dict:
	_exigir()
	respuesta = (respuesta or "").strip()
	if not respuesta:
		frappe.throw(_("Escribe o di tu respuesta."))
	if not frappe.db.exists(DT, name):
		frappe.throw(_("La entrevista no se encontró."), exc=frappe.DoesNotExistError, title="entrevista_perdida")
	doc = frappe.get_doc(DT, name)
	if doc.estado != "En curso":
		frappe.throw(_("Esta entrevista ya está confirmada."))
	respuestas, mapa = _leer(doc)
	respuestas.append({"tema": tema if tema in CLAVES else "negocio", "pregunta": pregunta, "respuesta": respuesta[:1500],
					   "hora": str(now_datetime())})
	nuevos: dict = {}
	siguiente = None
	motor = "Guion fijo"
	try:
		ia = _con_ia(respuestas, mapa)
	except Exception:
		ia = None
	if ia:
		motor = "IA"
		# La IA devuelve la lista completa y ordenada de cada tema que cambio: se
		# reemplaza (asi no se acumulan repetidos) y lo nuevo es lo que no estaba.
		for k, datos in (ia.get("mapa") or {}).items():
			if k in CLAVES and isinstance(datos, list):
				limpio = list(dict.fromkeys(str(d).strip().rstrip(".")[:80] for d in datos if str(d).strip()))[:6]
				antes = {d.lower() for d in mapa[k]}
				nuevos[k] = [d for d in limpio if d.lower() not in antes]
				mapa[k] = limpio
		if (ia.get("nombre_dueno") or "").strip():
			doc.nombre_dueno = str(ia["nombre_dueno"]).strip()[:40]
		if (ia.get("nombre_negocio") or "").strip():
			doc.nombre_negocio = str(ia["nombre_negocio"]).strip()[:80]
		sig = ia.get("siguiente")
		cuenta = _cubiertos(respuestas, mapa)
		# Primero la persona: si la IA quiere saltar al negocio antes de tiempo, se sigue con la persona.
		en_persona = not cuenta["persona"] or not cuenta["acuerdo"]
		if isinstance(sig, dict) and en_persona and sig.get("tema") not in ("persona", "acuerdo"):
			sig = None
		if not ia.get("completo") and isinstance(sig, dict) and sig.get("tema") in CLAVES and (sig.get("pregunta") or "").strip() \
				and len(respuestas) < TOPE_SEGURIDAD:
			siguiente = {"tema": sig["tema"], "pregunta": sig["pregunta"].strip()[:240],
						 "sugerencias": [str(x)[:40] for x in (sig.get("sugerencias") or [])][:4]}
		elif not ia.get("completo"):
			siguiente = _pregunta_guion(respuestas, mapa)
	else:
		piezas = _extraer_guion(respuestas[-1]["tema"], respuesta)
		ya = {d.lower() for d in mapa[respuestas[-1]["tema"]]}
		nuevos[respuestas[-1]["tema"]] = [d for d in piezas if d.lower() not in ya]
		mapa[respuestas[-1]["tema"]].extend(nuevos[respuestas[-1]["tema"]])
		siguiente = _pregunta_guion(respuestas, mapa)
	# Si la IA da por terminada la entrevista pero falta un tema, se pregunta igual.
	if siguiente is None:
		siguiente = _pregunta_guion(respuestas, mapa)
	doc.respuestas = json.dumps(respuestas, ensure_ascii=False)
	doc.mapa = json.dumps(mapa, ensure_ascii=False)
	doc.motor = motor
	doc.save(ignore_permissions=True)
	frappe.cache.set_value(f"lyra_diag_siguiente:{doc.name}", siguiente, expires_in_sec=7 * 24 * 3600)
	vista = _vista(doc, respuestas, mapa, siguiente)
	vista["nuevos"] = nuevos
	return vista


@frappe.whitelist(methods=["POST"])
def confirmar(name: str, mapa: str | dict) -> dict:
	"""El dueno reviso su mapa (y quizas lo corrigio): queda confirmado."""
	_exigir()
	doc = frappe.get_doc(DT, name)
	datos = frappe.parse_json(mapa) if isinstance(mapa, str) else mapa
	limpio = {k: [str(x).strip()[:90] for x in (datos.get(k) or []) if str(x).strip()][:12] for k in CLAVES}
	doc.mapa = json.dumps(limpio, ensure_ascii=False)
	doc.estado = "Confirmado"
	doc.confirmado_el = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.cache.delete_value(f"lyra_diag_siguiente:{doc.name}")
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def empezar_de_nuevo(name: str) -> dict:
	_exigir()
	doc = frappe.get_doc(DT, name)
	if doc.estado == "En curso":
		frappe.delete_doc(DT, name, ignore_permissions=True, force=True)
	frappe.cache.delete_value(f"lyra_diag_siguiente:{name}")
	return estado()
