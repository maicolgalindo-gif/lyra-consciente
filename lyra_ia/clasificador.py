"""Clasificaciones para todo el CRM.

Cada modulo de Lyra declara sus preguntas (hook lyra_ia_preguntas) con el
mismo formato que usa Laya: {"pregunta": {"type": "choice" | "score" | "noul",
"instructions": "...", "criteria": {...} o [...]}}.

Hoy responde DeepSeek. Cada respuesta se guarda en IA Clasificacion, y cuando
una persona la corrige queda marcada: esos son los ejemplos con los que
despues se entrena a Laya, que respondera las mismas preguntas en el
servidor propio, rapido y sin costo por consulta. Las pantallas no cambian
cuando eso pase: piden clasificar(), y adentro se decide el motor.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from lyra_ia.cerebro import IAError, completar_json

DT = "IA Clasificacion"


def conjuntos() -> dict:
	"""{nombre: {"modulo": ..., "preguntas": {...}}} de las apps instaladas."""
	salida = {}
	for ruta in frappe.get_hooks("lyra_ia_preguntas"):
		try:
			salida.update(frappe.get_attr(ruta)() or {})
		except Exception:
			frappe.log_error(title=f"Lyra IA: preguntas de {ruta}")
	return salida


def _opciones(p: dict) -> list[str]:
	if p["type"] == "noul":
		return ["si", "no"]
	c = p.get("criteria") or []
	return list(c.keys()) if isinstance(c, dict) else list(c)


def _instrucciones(preguntas: dict) -> str:
	lineas = []
	for clave, p in preguntas.items():
		c = p.get("criteria")
		if p["type"] == "noul":
			opciones = "si | no"
		elif isinstance(c, dict):
			opciones = " | ".join(f"{k} ({v})" for k, v in c.items())
		else:
			opciones = " | ".join(c or [])
		lineas.append(f'- "{clave}": {p["instructions"]} Opciones: {opciones}')
	return "\n".join(lineas)


def clasificar(conjunto: str, texto: str, referencia: tuple[str, str] | None = None, guardar: bool = True) -> dict:
	"""Responde las preguntas del conjunto sobre el texto.

	Devuelve {pregunta: {"respuesta": opcion o None, "confianza": 0..1, "tipo": ..., "opciones": [...], "id": ...}}.
	"""
	todos = conjuntos()
	if conjunto not in todos:
		raise IAError(_("No hay preguntas de clasificación para «{0}».").format(conjunto))
	preguntas = todos[conjunto]["preguntas"]
	sistema = (
		"Eres un clasificador para un CRM en Colombia. Lee el texto y responde cada pregunta eligiendo SOLO una de "
		"sus opciones (la clave exacta, sin la explicación entre paréntesis). Devuelve un JSON así: "
		'{"<pregunta>": {"respuesta": "<opcion>", "confianza": <0 a 1>}, ...}. Sin texto adicional.\n\nPreguntas:\n'
		+ _instrucciones(preguntas)
	)
	datos = completar_json(
		[{"role": "system", "content": sistema}, {"role": "user", "content": texto[-12000:]}],
		funcion=f"clasificar.{conjunto}",
		referencia=referencia,
		max_tokens=400,
		temperatura=0,
	)
	salida = {}
	for clave, p in preguntas.items():
		r = datos.get(clave) or {}
		respuesta = str(r.get("respuesta", "")).strip().lower() if isinstance(r, dict) else str(r).strip().lower()
		opciones = _opciones(p)
		mapa = {o.lower(): o for o in opciones}
		elegida = mapa.get(respuesta.replace("sí", "si"))
		try:
			confianza = max(0.0, min(1.0, float(r.get("confianza", 0)))) if isinstance(r, dict) else 0.0
		except (TypeError, ValueError):
			confianza = 0.0
		salida[clave] = {"respuesta": elegida, "confianza": confianza, "tipo": p["type"], "opciones": opciones,
						 "pregunta": p["instructions"]}
	if guardar:
		_guardar(conjunto, todos[conjunto].get("modulo"), texto, referencia, salida)
	return salida


def _guardar(conjunto: str, modulo: str | None, texto: str, referencia, salida: dict) -> None:
	for clave, r in salida.items():
		filtros = {"conjunto": conjunto, "pregunta": clave, "corregida": 0}
		if referencia:
			filtros.update({"referencia_doctype": referencia[0], "referencia_name": referencia[1]})
			# Volver a clasificar el mismo documento reemplaza lo que nadie reviso todavia.
			frappe.db.delete(DT, filtros)
		doc = frappe.get_doc({
			"doctype": DT, "modulo": modulo, "conjunto": conjunto, "pregunta": clave, "motor": "DeepSeek",
			"referencia_doctype": referencia[0] if referencia else None,
			"referencia_name": referencia[1] if referencia else None,
			"respuesta_ia": r["respuesta"], "respuesta_final": r["respuesta"], "confianza": round(r["confianza"] * 100, 1),
			"texto": texto[-12000:],
		}).insert(ignore_permissions=True)
		r["id"] = doc.name


def revisar(respuestas: dict) -> None:
	"""Lo que la persona dejo despues de ver la propuesta: {id: respuesta_final}.

	Si cambio algo, queda como corregida (un ejemplo valioso para entrenar a Laya).
	"""
	for ident, final in (respuestas or {}).items():
		fila = frappe.db.get_value(DT, ident, ["respuesta_ia", "owner"], as_dict=True)
		if not fila:
			continue
		frappe.db.set_value(DT, ident, {
			"respuesta_final": final or None,
			"corregida": int((final or None) != fila.respuesta_ia),
			"revisada_por": frappe.session.user,
		})


def exportar_para_laya(conjunto: str) -> list[dict]:
	"""Los ejemplos revisados en el formato de entrenamiento de Laya (state, question, answer)."""
	todos = conjuntos()
	preguntas = (todos.get(conjunto) or {}).get("preguntas") or {}
	filas = frappe.get_all(DT, filters={"conjunto": conjunto, "revisada_por": ["is", "set"], "respuesta_final": ["is", "set"]},
						   fields=["pregunta", "texto", "respuesta_final"])
	return [{"state": f.texto, "question": {f.pregunta: preguntas.get(f.pregunta)}, "answer": {f.pregunta: f.respuesta_final}}
			for f in filas if f.pregunta in preguntas]


@frappe.whitelist()
def descargar_ejemplos(conjunto: str) -> None:
	"""JSONL con los ejemplos revisados, para el cuaderno de entrenamiento de Laya."""
	frappe.only_for("System Manager")
	frappe.response["filename"] = f"laya_{conjunto}.jsonl"
	frappe.response["filecontent"] = "\n".join(json.dumps(e, ensure_ascii=False) for e in exportar_para_laya(conjunto))
	frappe.response["type"] = "download"
