"""Lyra entrevista a cada funcionario: cómo trabaja y qué papeles usa.

Mismo estilo que con el dueño (diagnostico/entrevista.py): primero la persona,
después el trabajo. Pero aquí Lyra SOLO ENTREVISTA: no le ofrece ayuda a la
persona, no le promete nada y no le habla de lo que ella hará. Lo de «así te voy a
ayudar» es del dueño (diagnostico/recomendacion.py), no de cada funcionario.

Tres diferencias que importan:

- Lyra no sabe de antemano el cargo de nadie. Lo DEDUCE de la primera respuesta
  («¿qué haces aquí?») y lo confirma al preguntar lo siguiente. Si la persona la
  corrige en las primeras respuestas, se reajusta. Así nadie tiene que configurar
  nada antes de que la gente entre (ver cargos.py).
- Lyra PIDE los documentos: los formatos, manuales y plantillas con los que se
  trabaja de verdad. Lo que la persona comparte queda adjunto a su entrevista.

Lo que aquí se recoge es el TRABAJO, nunca a la persona: lo personal (estudios,
experiencia, qué quiere aprender) va aparte, en perfil.py, y al dueño no le llega
ni lo uno ni lo otro en bruto — solo consolidado por área (ver consolidado()).

Esta entrevista la hace cualquier persona de la empresa, no solo un System
Manager: cada quien ve y responde la suya (permiso if_owner del doctype).
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from lyra_ia.diagnostico import cargos

DT = "Diagnostico Funcionario"
CLAVES = cargos.CLAVES
# Freno de seguridad por si la IA nunca da por terminada la entrevista.
TOPE_SEGURIDAD = 60
# Mientras la entrevista sea mas corta que esto, una correccion de la persona
# todavia puede cambiar el cargo («no, yo soy de compras»).
VENTANA_CARGO = 3


def _empresa() -> str:
	from lyra_ia import entorno

	return entorno.empresa()


def _voz_lista() -> bool:
	from lyra_ia import voz

	try:
		return voz.lista()
	except Exception:
		return False


def _exigir():
	"""Cualquier persona de la empresa, no solo el dueno. Invitados no."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Entra con tu usuario para hablar con Lyra."), frappe.PermissionError)


def nombre_persona(doc) -> str:
	if doc.get("nombre_persona"):
		return doc.nombre_persona
	nombre = frappe.utils.get_fullname(doc.funcionario or frappe.session.user) or ""
	return "" if nombre.lower() in ("administrator", "guest") else nombre.split(" ")[0]


def _actual(crear: bool = True):
	nombre = frappe.db.get_value(DT, {"funcionario": frappe.session.user, "estado": "En curso"},
								 "name", order_by="modified desc")
	if nombre:
		return frappe.get_doc(DT, nombre)
	if not crear:
		return None
	doc = frappe.get_doc({"doctype": DT, "empresa": _empresa(), "funcionario": frappe.session.user,
						  "estado": "En curso", "respuestas": "[]", "documentos": "[]",
						  "mapa": json.dumps({k: [] for k in CLAVES})})
	doc.insert(ignore_permissions=True)
	return doc


def _leer(doc) -> tuple[list, dict, list]:
	respuestas = json.loads(doc.respuestas or "[]")
	mapa = json.loads(doc.mapa or "{}")
	documentos = json.loads(doc.documentos or "[]")
	for k in CLAVES:
		mapa.setdefault(k, [])
	return respuestas, mapa, documentos


def _cubiertos(respuestas: list, mapa: dict | None = None) -> dict:
	cuenta = {k: 0 for k in CLAVES}
	for r in respuestas:
		if r.get("tema") in cuenta:
			cuenta[r["tema"]] += 1
	for k, datos in (mapa or {}).items():
		if k in cuenta and datos and not cuenta[k]:
			cuenta[k] = 1
	return cuenta


def _pregunta_guion(doc, respuestas: list, mapa: dict | None = None) -> dict | None:
	"""Sin IA: el siguiente tema sin tocar, con la pregunta del cargo."""
	cuenta = _cubiertos(respuestas, mapa)
	for t in cargos.temas(doc.cargo):
		if cuenta[t["clave"]] == 0:
			pregunta = t["pregunta"]
			# La primera vez que se habla de trabajo, Lyra confirma el cargo.
			if t["clave"] not in cargos.FIJOS and doc.cargo and not _cargo_dicho(respuestas):
				pregunta = f"Entonces lo tuyo es {cargos.nombre(doc.cargo).lower()}, ¿cierto? {pregunta}"
			return {"tema": t["clave"], "pregunta": pregunta, "sugerencias": t["sugerencias"]}
	return None


def _cargo_dicho(respuestas: list) -> bool:
	"""Si Lyra ya nombro el cargo en alguna pregunta, no lo vuelve a confirmar."""
	return any("¿cierto?" in (r.get("pregunta") or "") for r in respuestas)


def _extraer_guion(tema: str, respuesta: str) -> list[str]:
	texto = respuesta.strip().rstrip(".")
	if tema in ("herramientas", "documentos", "traspaso") and ("," in texto or " y " in texto):
		partes = [p.strip(" .") for p in texto.replace(" y ", ",").split(",")]
		return [p[:60] for p in partes if p][:8]
	return [texto[:90]] if texto else []


def _fase(cuenta: dict, cargo: str | None) -> str:
	if not cuenta["persona"] or not cuenta["camino"]:
		return "PERSONA. Todavía no preguntes por su trabajo en detalle: primero conócela."
	return f"TRABAJO. Ya la conoces; ahora entiende cómo trabaja ({cargos.nombre(cargo)})."


def _con_ia(doc, respuestas: list, mapa: dict) -> dict | None:
	"""La IA ordena el mapa, deduce el cargo, anota los documentos y decide qué preguntar."""
	from lyra_ia import cerebro

	if not cerebro.lista():
		return None
	cuenta = _cubiertos(respuestas, mapa)
	lista_temas = cargos.temas(doc.cargo)
	pendientes = [t["clave"] for t in lista_temas if cuenta[t["clave"]] == 0]
	texto_temas = "\n".join(f"- {t['clave']} ({t['nombre']}): {t['definicion']}" for t in lista_temas)
	pedir = ", ".join(cargos.documentos(doc.cargo))
	sistema = (
		"Eres Lyra, la inteligencia de un ERP colombiano, y estás ENTREVISTANDO a una persona de la empresa "
		"para entender cómo trabaja. Hablas en español de Colombia, cálida, cercana y natural, como alguien que "
		"de verdad escucha; sin tecnicismos ni palabras como 'módulo', 'ERP' o 'sistema'.\n\n"
		"Cómo conduces la conversación:\n"
		"1. Primero la PERSONA (persona y camino) y después su TRABAJO. No mezcles.\n"
		"2. No hay un número fijo de preguntas. Profundiza donde haya algo importante y pasa rápido por lo que ya "
		"quedó claro. Tú decides cuántas.\n"
		"3. Cada pregunta nace de lo que te acaban de decir: retoma un detalle suyo. Una sola pregunta, máximo 30 "
		"palabras, ABIERTA.\n"
		"4. Usa su nombre muy de vez en cuando.\n"
		"5. Te interesa cómo se hace el trabajo DE VERDAD, no como dice el manual. Si algo suena a procedimiento "
		"ideal, pregunta qué pasa cuando sale mal o cuando hay afán.\n"
		"6. Pide los documentos con naturalidad cuando venga al caso: " + (pedir or "los formatos que use") + ". "
		"Nunca insistas si dice que no los tiene.\n"
		"7. No juzgues ni evalúes a la persona, y no le preguntes por su desempeño, su salario, su salud ni su "
		"vida privada. Esto es sobre el trabajo.\n"
		"8. SOLO ENTREVISTAS. Nunca ofrezcas ayuda, no preguntes en qué te gustaría ayudarle, no prometas "
		"nada y no hables de lo que tú vas a hacer por ella. Nada de «¿en qué te ayudo?», «voy a estar "
		"contigo» ni «te voy a avisar». Estás conociendo cómo trabaja, y punto.\n"
		"9. Termina (completo: true) cuando entiendas cómo trabaja: su día, su paso a paso, con qué lo hace, qué "
		"papeles usa, qué le quita tiempo y con quién se coordina.\n\n"
		f"Fase actual: {_fase(cuenta, doc.cargo)}\n"
		f"Cargo que crees que tiene: {cargos.nombre(doc.cargo)}\n\n"
		f"Temas:\n{texto_temas}\n"
		f"Temas sin tocar: {', '.join(pendientes) or 'ninguno'}.\n\n"
		"Devuelve SOLO un JSON:\n"
		'{"mapa": {"<tema>": ["dato", ...]}, "nombre_persona": null, "cargo": null, "documentos": [], '
		'"siguiente": {"tema": "<tema>", "pregunta": "...", "sugerencias": []}, "completo": false}\n'
		"- mapa: cada dato en el tema que le corresponde según las definiciones, aunque la pregunta fuera de otro "
		"tema. Un dato va en un solo tema. Devuelve SOLO los temas que cambian con la última respuesta, cada uno "
		"con su lista COMPLETA ya ordenada: lo que había más lo nuevo, sin repetir ideas con otras palabras, "
		"máximo 6 datos de 2 a 8 palabras, en tercera persona. Nada inventado.\n"
		"- nombre_persona: su nombre de pila si lo dijo; si no, null.\n"
		f"- cargo: SOLO si por lo que contó es claro, una de estas claves; si no, null:\n{cargos.lista_para_ia()}\n"
		"- documentos: los formatos o documentos que mencionó que existen, en 2 a 6 palabras cada uno. Solo los "
		"que nombró; lista vacía si ninguno.\n"
		"- siguiente.tema: la clave del tema de tu pregunta.\n"
		"- sugerencias: de 0 a 4 respuestas cortas para tocar; ninguna en preguntas abiertas.\n"
		"- completo: true solo si no quedan temas sin tocar; entonces siguiente es null."
	)
	actual = {k: v for k, v in mapa.items() if v}
	conversacion = "\n".join(f"[{r['tema']}] Lyra: {r['pregunta']}\n{nombre_persona(doc) or 'Persona'}: {r['respuesta']}"
							 for r in respuestas)
	datos = cerebro.completar_json(
		[{"role": "system", "content": sistema},
		 {"role": "user", "content": f"Mapa actual:\n{json.dumps(actual, ensure_ascii=False)}\n\nConversación:\n{conversacion}"}],
		funcion="diagnostico.funcionario", max_tokens=900, temperatura=0.5,
	)
	return datos if isinstance(datos, dict) else None


def _fijar_cargo(doc, respuestas: list, sugerido: str | None) -> None:
	"""El cargo sale de lo que la persona conto: primero la IA, si no las senales.

	Se puede corregir mientras la entrevista sea corta: si dice «no, yo soy de
	compras» en la segunda respuesta, el cargo cambia. Despues queda fijo."""
	if doc.cargo and len(respuestas) > VENTANA_CARGO:
		return
	nuevo = sugerido if sugerido and cargos.existe(sugerido) else None
	if not nuevo:
		ultimas = " ".join(r.get("respuesta", "") for r in respuestas[-VENTANA_CARGO:])
		nuevo = cargos.deducir(ultimas)
	if not nuevo and not doc.cargo:
		nuevo = cargos.GENERICO
	if nuevo and nuevo != doc.cargo:
		doc.cargo = nuevo
		doc.cargo_nombre = cargos.nombre(nuevo)
		doc.area = cargos.area(nuevo)


def _archivos(name: str) -> list[str]:
	"""Los archivos que la persona ya compartio, para que sigan ahi al recargar."""
	return frappe.get_all("File", filters={"attached_to_doctype": DT, "attached_to_name": name},
						  pluck="file_name", order_by="creation") or []


def _vista(doc, respuestas: list, mapa: dict, documentos: list, siguiente: dict | None) -> dict:
	cuenta = _cubiertos(respuestas, mapa)
	lista_temas = cargos.temas(doc.cargo)
	saludo = ("Hola, soy Lyra. Voy a estar contigo en el día a día, así que primero quiero conocerte. "
			  "Habla con calma: puedes responder hablando o escribiendo.")
	return {
		"name": doc.name,
		"empresa": doc.empresa,
		"cargo": doc.cargo,
		"cargo_nombre": doc.cargo_nombre or "",
		"saludo": saludo if not respuestas else None,
		"temas": [{"clave": t["clave"], "nombre": t["nombre"], "listo": cuenta[t["clave"]] > 0} for t in lista_temas],
		"mapa": mapa,
		"documentos": documentos,
		"archivos": _archivos(doc.name),
		"pedir_documento": bool(siguiente and siguiente.get("tema") == "documentos"),
		"siguiente": siguiente,
		"completo": siguiente is None,
		"estado": doc.estado,
		"nombre_usuario": nombre_persona(doc),
		"voz": _voz_lista(),
	}


# ------------------------------------------------------------------- API
@frappe.whitelist(methods=["POST"])
def estado() -> dict:
	"""POST y no GET: puede crear la entrevista, y Frappe descarta lo que se guarda en un GET."""
	_exigir()
	doc = _actual()
	respuestas, mapa, documentos = _leer(doc)
	siguiente = frappe.cache.get_value(f"lyra_func_siguiente:{doc.name}") or _pregunta_guion(doc, respuestas, mapa)
	return _vista(doc, respuestas, mapa, documentos, siguiente)


@frappe.whitelist(methods=["POST"])
def responder(name: str, tema: str, pregunta: str, respuesta: str) -> dict:
	_exigir()
	respuesta = (respuesta or "").strip()
	if not respuesta:
		frappe.throw(_("Escribe o di tu respuesta."))
	if not frappe.db.exists(DT, name):
		frappe.throw(_("La entrevista no se encontró."), exc=frappe.DoesNotExistError, title="entrevista_perdida")
	doc = frappe.get_doc(DT, name)
	if doc.funcionario != frappe.session.user:
		frappe.throw(_("Esta entrevista no es tuya."), frappe.PermissionError)
	if doc.estado != "En curso":
		frappe.throw(_("Esta entrevista ya está confirmada."))
	respuestas, mapa, documentos = _leer(doc)
	respuestas.append({"tema": tema if tema in CLAVES else "dia", "pregunta": pregunta,
					   "respuesta": respuesta[:1500], "hora": str(now_datetime())})
	nuevos: dict = {}
	siguiente = None
	motor = "Guion fijo"
	try:
		ia = _con_ia(doc, respuestas, mapa)
	except Exception:
		ia = None
	if ia:
		motor = "IA"
		_fijar_cargo(doc, respuestas, (ia.get("cargo") or "").strip() or None)
		for k, datos in (ia.get("mapa") or {}).items():
			if k in CLAVES and isinstance(datos, list):
				limpio = list(dict.fromkeys(str(d).strip().rstrip(".")[:80] for d in datos if str(d).strip()))[:6]
				antes = {d.lower() for d in mapa[k]}
				nuevos[k] = [d for d in limpio if d.lower() not in antes]
				mapa[k] = limpio
		if (ia.get("nombre_persona") or "").strip():
			doc.nombre_persona = str(ia["nombre_persona"]).strip()[:40]
		ya = {d.lower() for d in documentos}
		for d in (ia.get("documentos") or []):
			d = str(d).strip().rstrip(".")[:80]
			if d and d.lower() not in ya:
				documentos.append(d)
				ya.add(d.lower())
		sig = ia.get("siguiente")
		cuenta = _cubiertos(respuestas, mapa)
		# Primero la persona: si la IA quiere saltar al trabajo antes de tiempo, se sigue con la persona.
		en_persona = not cuenta["persona"] or not cuenta["camino"]
		if isinstance(sig, dict) and en_persona and sig.get("tema") not in cargos.FIJOS:
			sig = None
		if not ia.get("completo") and isinstance(sig, dict) and sig.get("tema") in CLAVES \
				and (sig.get("pregunta") or "").strip() and len(respuestas) < TOPE_SEGURIDAD:
			texto = sig["pregunta"].strip()[:240]
			if sig["tema"] not in cargos.FIJOS and doc.cargo and doc.cargo != cargos.GENERICO \
					and not _cargo_dicho(respuestas):
				texto = f"Entonces lo tuyo es {cargos.nombre(doc.cargo).lower()}, ¿cierto? {texto}"
			siguiente = {"tema": sig["tema"], "pregunta": texto,
						 "sugerencias": [str(x)[:40] for x in (sig.get("sugerencias") or [])][:4]}
		elif not ia.get("completo"):
			siguiente = _pregunta_guion(doc, respuestas, mapa)
	else:
		_fijar_cargo(doc, respuestas, None)
		piezas = _extraer_guion(respuestas[-1]["tema"], respuesta)
		ya = {d.lower() for d in mapa[respuestas[-1]["tema"]]}
		nuevos[respuestas[-1]["tema"]] = [d for d in piezas if d.lower() not in ya]
		mapa[respuestas[-1]["tema"]].extend(nuevos[respuestas[-1]["tema"]])
		if respuestas[-1]["tema"] == "documentos":
			ya = {d.lower() for d in documentos}
			documentos.extend([p for p in piezas if p.lower() not in ya])
		siguiente = _pregunta_guion(doc, respuestas, mapa)
	if siguiente is None:
		siguiente = _pregunta_guion(doc, respuestas, mapa)
	doc.respuestas = json.dumps(respuestas, ensure_ascii=False)
	doc.mapa = json.dumps(mapa, ensure_ascii=False)
	doc.documentos = json.dumps(documentos, ensure_ascii=False)
	doc.motor = motor
	doc.save(ignore_permissions=True)
	frappe.cache.set_value(f"lyra_func_siguiente:{doc.name}", siguiente, expires_in_sec=7 * 24 * 3600)
	vista = _vista(doc, respuestas, mapa, documentos, siguiente)
	vista["nuevos"] = nuevos
	return vista


@frappe.whitelist(methods=["POST"])
def confirmar(name: str, mapa: str | dict) -> dict:
	"""La persona revisó lo que Lyra entendió de su trabajo (y quizás lo corrigió)."""
	_exigir()
	doc = frappe.get_doc(DT, name)
	if doc.funcionario != frappe.session.user:
		frappe.throw(_("Esta entrevista no es tuya."), frappe.PermissionError)
	datos = frappe.parse_json(mapa) if isinstance(mapa, str) else mapa
	limpio = {k: [str(x).strip()[:90] for x in (datos.get(k) or []) if str(x).strip()][:12] for k in CLAVES}
	doc.mapa = json.dumps(limpio, ensure_ascii=False)
	doc.estado = "Confirmado"
	doc.confirmado_el = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.cache.delete_value(f"lyra_func_siguiente:{doc.name}")
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def empezar_de_nuevo(name: str) -> dict:
	_exigir()
	doc = frappe.get_doc(DT, name)
	if doc.funcionario != frappe.session.user:
		frappe.throw(_("Esta entrevista no es tuya."), frappe.PermissionError)
	if doc.estado == "En curso":
		frappe.delete_doc(DT, name, ignore_permissions=True, force=True)
	frappe.cache.delete_value(f"lyra_func_siguiente:{name}")
	return estado()


# ------------------------------------------------- lo que Lyra entendió
# El cierre NO promete nada. Lyra entrevista: al final le devuelve a la persona
# lo que entendió de su trabajo, para que lo corrija si quedó torcido, y le da
# las gracias. Quien recibe promesas es el dueño, en recomendacion.py.
RESUMEN = [
	("dia", "Tu día"),
	("proceso", "Tu paso a paso"),
	("herramientas", "Con qué lo haces"),
	("documentos", "Los papeles que usas"),
	("dolores", "Lo que te quita tiempo"),
	("traspaso", "Con quién te coordinas"),
]


def entendido(mapa: dict) -> list[dict]:
	"""Lo que quedó claro, por tema. Solo lo que la persona dijo."""
	salida = []
	for clave, titulo in RESUMEN:
		datos = [d for d in (mapa.get(clave) or []) if str(d).strip()]
		if datos:
			salida.append({"clave": clave, "titulo": titulo, "como": "; ".join(datos[:4])})
	return salida


def _cierre_simple(nombre: str, doc, mapa: dict, partes: list[dict]) -> dict:
	oficio = (doc.cargo_nombre or "").lower()
	resumen = ("Esto es lo que entendí de tu trabajo"
			   + (" en " + oficio if oficio and doc.cargo != cargos.GENERICO else "")
			   + ". Si algo quedó torcido, dímelo.")
	return {"titulo": _("Gracias, {0}.").format(nombre) if nombre else _("Gracias."),
			"resumen": resumen,
			"puntos": [{"titulo": p["titulo"], "como": p["como"], "porque": ""} for p in partes],
			"primero": ""}


def _cierre(nombre: str, doc, mapa: dict, partes: list[dict]) -> dict:
	simple = _cierre_simple(nombre, doc, mapa, partes)
	try:
		from lyra_ia import cerebro

		if not cerebro.lista():
			return simple
		datos = cerebro.completar_json(
			[{"role": "system", "content": (
				"Eres Lyra y acabas de ENTREVISTAR a una persona de una empresa colombiana para entender cómo "
				"trabaja. Ahora le devuelves, en sus propias palabras, lo que entendiste, y le agradeces el tiempo. "
				"En español de Colombia, en segunda persona, cálida y concreta, sin tecnicismos ni palabras como "
				"'módulo', 'ERP' o 'sistema'.\n"
				"PROHIBIDO: ofrecerle ayuda, prometerle algo, decirle que vas a estar con ella, que le vas a avisar, "
				"recordar, automatizar o facilitar nada, y hablar de lo que tú harás. No la evalúes ni opines sobre "
				"su desempeño. Solo le repites lo que ella te contó.\n"
				"Devuelve SOLO un JSON:\n"
				'{"titulo": "...", "resumen": "...", "puntos": [{"titulo": "...", "como": "..."}], "primero": "..."}\n'
				"- titulo: una frase corta dándole las gracias por su nombre.\n"
				"- resumen: lo que entendiste de su trabajo, máximo 3 frases, sin exagerar ni inventar, y pidiéndole "
				"que te corrija si algo quedó mal.\n"
				"- puntos: los mismos de 'entendido', en ese orden y sin agregar ninguno. titulo igual al que viene; "
				"como: lo que entendiste de ese tema, máximo 25 palabras, con lo que ella dijo.\n"
				"- primero: una frase corta de despedida. Sin prometer nada.")},
			 {"role": "user", "content": json.dumps(
				 {"nombre": nombre, "cargo": doc.cargo_nombre, "entendido": partes}, ensure_ascii=False)}],
			funcion="diagnostico.cierre_funcionario", max_tokens=700, temperatura=0.4,
		)
		puntos = [{"titulo": str(x.get("titulo", ""))[:60], "como": str(x.get("como", ""))[:220], "porque": ""}
				  for x in (datos.get("puntos") or []) if isinstance(x, dict)][:6]
		if not puntos or not all(p["titulo"] and p["como"] for p in puntos):
			return simple
		return {"titulo": str(datos.get("titulo") or simple["titulo"])[:120],
				"resumen": str(datos.get("resumen") or simple["resumen"])[:600],
				"puntos": puntos, "primero": str(datos.get("primero") or "")[:240]}
	except Exception:
		return simple


@frappe.whitelist(methods=["POST"])
def plan(name: str, rehacer: int = 0) -> dict:
	"""Lo que Lyra le devuelve a la persona al final. Se guarda y se reutiliza."""
	_exigir()
	doc = frappe.get_doc(DT, name)
	if doc.funcionario != frappe.session.user:
		frappe.throw(_("Esta entrevista no es tuya."), frappe.PermissionError)
	if doc.estado != "Confirmado":
		frappe.throw(_("Primero confirma lo que entendí de tu trabajo."))
	guardado = json.loads(doc.cierre or "null")
	if guardado and not int(rehacer):
		return guardado
	respuestas, mapa, documentos = _leer(doc)
	cierre = _cierre(nombre_persona(doc), doc, mapa, entendido(mapa))
	doc.cierre = json.dumps(cierre, ensure_ascii=False)
	doc.save(ignore_permissions=True)
	return cierre


# --------------------------------------------------- lo que ve el dueño
def _minimo_por_area() -> int:
	try:
		return int(frappe.db.get_single_value("Sense Ajustes", "min_personas_area") or 3)
	except Exception:
		return 3


@frappe.whitelist()
def consolidado() -> dict:
	"""Cómo funciona la empresa por dentro, por ÁREA y nunca por persona.

	Es lo único de las entrevistas a funcionarios que llega al dueño: sin nombres,
	sin quién dijo qué, y un área con menos personas que el mínimo (Sense Ajustes)
	se junta en «Otras áreas», porque con una o dos la cifra diría quién fue."""
	frappe.only_for(("System Manager", "Equipo Lyra"))
	minimo = _minimo_por_area()
	por_area: dict = {}
	for d in frappe.get_all(DT, filters={"estado": "Confirmado"},
							fields=["name", "area", "cargo_nombre", "mapa", "documentos"]):
		area = d.area or "Otras áreas"
		caja = por_area.setdefault(area, {"area": area, "personas": 0, "cargos": set(),
										  "como_trabajan": [], "duele": [], "papeles": []})
		caja["personas"] += 1
		if d.cargo_nombre:
			caja["cargos"].add(d.cargo_nombre)
		mapa = frappe.parse_json(d.mapa or "{}") or {}
		caja["como_trabajan"].extend(mapa.get("proceso") or [])
		caja["duele"].extend(mapa.get("dolores") or [])
		caja["papeles"].extend(frappe.parse_json(d.documentos or "[]") or [])
	chicas = [c for c in por_area.values() if c["personas"] < minimo]
	grandes = [c for c in por_area.values() if c["personas"] >= minimo]
	if chicas:
		otras = {"area": "Otras áreas", "personas": sum(c["personas"] for c in chicas), "cargos": set(),
				 "como_trabajan": [], "duele": [], "papeles": []}
		for c in chicas:
			# Sin el paso a paso ni los cargos: en un area de una o dos personas eso
			# es la firma de quien lo conto.
			otras["duele"].extend(c["duele"])
			otras["papeles"].extend(c["papeles"])
		grandes.append(otras)
	salida = []
	for c in sorted(grandes, key=lambda x: -x["personas"]):
		salida.append({
			"area": c["area"], "personas": c["personas"], "cargos": sorted(c["cargos"]),
			"como_trabajan": list(dict.fromkeys(c["como_trabajan"]))[:8],
			"duele": list(dict.fromkeys(c["duele"]))[:8],
			"papeles": list(dict.fromkeys(c["papeles"]))[:10],
		})
	return {"minimo": minimo, "areas": salida,
			"entrevistados": frappe.db.count(DT, {"estado": "Confirmado"})}
