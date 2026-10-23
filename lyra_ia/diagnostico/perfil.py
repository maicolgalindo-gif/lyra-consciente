"""El perfil profesional de la persona: lo suyo, no lo de la empresa.

Esta es la otra mitad de la entrevista al funcionario, y la que NUNCA se cruza con
la primera: en funcionario.py queda cómo trabaja (eso la empresa sí lo necesita);
aquí queda quién es profesionalmente (estudios, cursos, experiencia, qué quiere
aprender, su hoja de vida).

Quién lo ve, y nadie más:
- la persona, siempre, y lo puede cambiar o borrar;
- Recursos Humanos, SOLO si ella lo permitió (compartir_rrhh), y lo puede quitar
  cuando quiera;
- el dueño, nunca. Ni consolidado: de esto no sale ninguna cifra.

Los permisos no se dejan al doctype solo: se sostienen abajo con las dos funciones
que Frappe consulta en cada lectura (condiciones y puede_ver, enganchadas en
hooks.py). Un olvido en una pantalla no alcanza para destapar un perfil.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

DT = "Perfil Funcionario"
ROL_RRHH = "Recursos Humanos"

# Lo que Lyra le pregunta, al final de la entrevista de trabajo y en la misma
# conversacion. Son pocas y opcionales a proposito: se llena si la persona
# quiere, y puede dejar lo que sea en blanco.
#
# Estas van por guion fijo, no las decide la IA: son datos de la persona y no
# hay nada que improvisar. La ultima no es un dato, es el permiso.
PREGUNTAS = [
	{"campo": "estudios", "nombre": "Qué estudiaste",
	 "pregunta": "Ya entiendo cómo trabajas. Ahora cuéntame de ti: ¿qué estudiaste? Si no terminaste algo, también cuenta.",
	 "sugerencias": []},
	{"campo": "experiencia", "nombre": "Dónde has trabajado",
	 "pregunta": "¿En qué has trabajado antes de aquí?",
	 "sugerencias": []},
	{"campo": "cursos", "nombre": "Cursos",
	 "pregunta": "¿Has hecho cursos o tienes certificaciones, aunque sean cortos?",
	 "sugerencias": ["Ninguno por ahora"]},
	{"campo": "quiere_aprender", "nombre": "Qué quieres aprender",
	 "pregunta": "¿Qué te gustaría aprender o hacer mejor?",
	 "sugerencias": []},
]
CAMPOS = [p["campo"] for p in PREGUNTAS]

# El permiso va aparte y de ultimo: primero la persona ve lo que conto, y
# despues decide quien lo lee. Nunca al reves.
PERMISO = {
	"campo": "permiso", "nombre": "Quién lo ve",
	"pregunta": "Esto que me contaste de ti es tuyo: tu jefe no lo ve. ¿Dejas que Recursos Humanos lo lea, para tenerte en cuenta en formaciones o vacantes?",
	"sugerencias": ["Sí, que lo vean", "No, solo yo"],
}
# Lo que cuenta como un «sí». Ante la duda, NO se comparte.
SI = ("si", "sí", "claro", "bueno", "dale", "ok", "listo", "de una", "obvio", "por supuesto",
	  "no hay problema", "esta bien", "está bien", "adelante", "hagale", "hágale")


def _exigir():
	if frappe.session.user == "Guest":
		frappe.throw(_("Entra con tu usuario."), frappe.PermissionError)


def _mio(crear: bool = True):
	nombre = frappe.db.get_value(DT, {"funcionario": frappe.session.user}, "name")
	if nombre:
		return frappe.get_doc(DT, nombre)
	if not crear:
		return None
	completo = frappe.utils.get_fullname(frappe.session.user) or ""
	doc = frappe.get_doc({"doctype": DT, "funcionario": frappe.session.user,
						  "nombre_persona": completo.split(" ")[0] if completo.lower() != "administrator" else "",
						  "estado": "En curso", "respuestas": "[]"})
	doc.insert(ignore_permissions=True)
	return doc


def temas() -> list[dict]:
	"""Los temas del perfil, en orden, con el permiso al final."""
	return list(PREGUNTAS) + [PERMISO]


def claves() -> list[str]:
	return [p["campo"] for p in temas()]


def desde_entrevista(campo: str, respuesta: str) -> None:
	"""Guarda lo que la persona contó de sí misma en la conversación.

	Se llama desde funcionario.py: el perfil se recoge hablando, en la misma
	entrevista, pero se guarda aparte y nunca se mezcla con lo del trabajo."""
	doc = _mio()
	texto = (respuesta or "").strip()
	respuestas = json.loads(doc.respuestas or "[]")
	if campo == "permiso":
		bajo = texto.lower()
		# «No» gana siempre: si dice «no, mejor no», no se comparte.
		dice_si = any(s in bajo for s in SI) and not bajo.startswith(("no", "nel", "prefiero que no"))
		doc.compartir_rrhh = 1 if dice_si else 0
		respuestas = [r for r in respuestas if r.get("campo") != "permiso"]
		respuestas.append({"campo": "permiso", "pregunta": PERMISO["pregunta"], "respuesta": texto[:300],
						   "hora": str(now_datetime())})
		doc.respuestas = json.dumps(respuestas, ensure_ascii=False)
	elif campo in CAMPOS:
		doc.set(campo, texto[:2000])
		pregunta = next((p["pregunta"] for p in PREGUNTAS if p["campo"] == campo), campo)
		respuestas = [r for r in respuestas if r.get("campo") != campo]
		respuestas.append({"campo": campo, "pregunta": pregunta, "respuesta": texto[:2000],
						   "hora": str(now_datetime())})
		doc.respuestas = json.dumps(respuestas, ensure_ascii=False)
	else:
		return
	doc.actualizado_el = now_datetime()
	if all((doc.get(c) or "").strip() for c in CAMPOS):
		doc.estado = "Confirmado"
	doc.save(ignore_permissions=True)


def lo_contado() -> dict:
	"""Lo que la persona ya contó de sí misma, para pintarlo en la pantalla."""
	doc = _mio(crear=False)
	if not doc:
		return {c: [] for c in claves()}
	salida = {c: ([doc.get(c)[:90]] if (doc.get(c) or "").strip() else []) for c in CAMPOS}
	# El permiso cuenta como contestado solo si ELLA contestó esa pregunta; con
	# mirar si hay otros datos, Lyra se la saltaba y nadie decidía nada.
	contestado = any(r.get("campo") == "permiso" for r in json.loads(doc.respuestas or "[]"))
	salida["permiso"] = ([] if not contestado else
						 ["Lo ve Recursos Humanos"] if doc.compartir_rrhh else ["Solo lo ves tú"])
	return salida


# ------------------------------------------------------------------- API
@frappe.whitelist(methods=["POST"])
def mio() -> dict:
	"""Mi perfil (lo crea vacío la primera vez). Solo el de quien pregunta."""
	_exigir()
	doc = _mio()
	hechos = {p["campo"] for p in PREGUNTAS if (doc.get(p["campo"]) or "").strip()}
	siguiente = next((p for p in PREGUNTAS if p["campo"] not in hechos), None)
	return {
		"name": doc.name,
		"nombre_usuario": doc.nombre_persona or "",
		"estado": doc.estado,
		"compartir_rrhh": bool(doc.compartir_rrhh),
		"hoja_vida": doc.hoja_vida or "",
		"datos": {c: doc.get(c) or "" for c in CAMPOS},
		"preguntas": PREGUNTAS,
		"siguiente": siguiente,
		"completo": siguiente is None,
	}


@frappe.whitelist(methods=["POST"])
def responder(campo: str, respuesta: str) -> dict:
	"""Guarda una respuesta del perfil. Siempre sobre el perfil de quien pregunta."""
	_exigir()
	if campo not in CAMPOS:
		frappe.throw(_("Ese dato no es del perfil."))
	doc = _mio()
	doc.set(campo, (respuesta or "").strip()[:2000])
	respuestas = json.loads(doc.respuestas or "[]")
	pregunta = next((p["pregunta"] for p in PREGUNTAS if p["campo"] == campo), campo)
	respuestas = [r for r in respuestas if r.get("campo") != campo]
	respuestas.append({"campo": campo, "pregunta": pregunta, "respuesta": (respuesta or "").strip()[:2000],
					   "hora": str(now_datetime())})
	doc.respuestas = json.dumps(respuestas, ensure_ascii=False)
	doc.actualizado_el = now_datetime()
	if all((doc.get(c) or "").strip() for c in CAMPOS):
		doc.estado = "Confirmado"
	doc.save(ignore_permissions=True)
	return mio()


@frappe.whitelist(methods=["POST"])
def permitir_rrhh(permitir: int = 1) -> dict:
	"""La persona decide si Recursos Humanos puede ver su perfil. Lo puede quitar después."""
	_exigir()
	doc = _mio()
	doc.compartir_rrhh = 1 if int(permitir) else 0
	doc.save(ignore_permissions=True)
	return {"ok": True, "compartir_rrhh": bool(doc.compartir_rrhh)}


@frappe.whitelist(methods=["POST"])
def borrar() -> dict:
	"""La persona borra su perfil. Es suyo."""
	_exigir()
	doc = _mio(crear=False)
	if doc:
		frappe.delete_doc(DT, doc.name, ignore_permissions=True, force=True)
	return {"ok": True}


# ------------------------------------------------- los permisos, en el servidor
def condiciones(user: str | None = None) -> str:
	"""Qué perfiles puede listar alguien (permission_query_conditions).

	El suyo siempre; los de los demás solo si es de Recursos Humanos y esa persona
	lo permitió. Cualquier otro rol, ninguno."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	mio = f"`tabPerfil Funcionario`.funcionario = {frappe.db.escape(user)}"
	if ROL_RRHH in frappe.get_roles(user):
		return f"({mio} OR `tabPerfil Funcionario`.compartir_rrhh = 1)"
	return mio


def puede_ver(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Lo mismo, documento por documento (has_permission)."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if doc.get("funcionario") == user:
		return True
	# Recursos Humanos lee lo que le dejaron ver; cambiarlo, nunca.
	return bool(ptype == "read" and doc.get("compartir_rrhh") and ROL_RRHH in frappe.get_roles(user))
