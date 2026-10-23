"""Entrar a hablar con Lyra con un enlace, sin cuenta ni contraseña.

Lyra TIENE que saber quién le habla: lo que una persona cuenta de sí misma es
suyo, y sin identificarla no se le puede prometer que nadie más lo lea. Pero
pedirle a cada persona de la empresa que se cree una cuenta del ERP y recuerde
una contraseña, para una conversación de diez minutos, es un muro.

El enlace resuelve las dos cosas: identifica sin pedir nada.

Quién invita: el Equipo Lyra, que es quien despliega Lyra en la empresa. La
empresa no invita a nadie, ni siquiera el dueño: si pudiera, decidiría a quién
se entrevista y a quién no, y la entrevista dejaría de ser de Lyra para ser
suya.

Lo que lo mantiene honesto:
- Es personal: un enlace por persona, nunca uno compartido.
- Se vence (ver Invitacion Lyra) y se puede revocar borrando la invitación.
- Solo abre la entrevista. La persona entra como un usuario normal, sin
  permisos de nada: lo que vea despues es lo que su rol le permita, que es
  ninguno hasta que alguien se lo de.
- La clave viaja por la URL, asi que vale lo que valga el canal por el que se
  mande. Por eso vence rapido: un enlace viejo reenviado no sirve.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

DT = "Invitacion Lyra"


def leer(clave: str):
	"""La invitación de esa clave, si todavía vale. None si no."""
	clave = (clave or "").strip()
	if not clave or len(clave) < 20:
		return None
	nombre = frappe.db.get_value(DT, {"clave": clave}, "name")
	if not nombre:
		return None
	doc = frappe.get_doc(DT, nombre)
	if doc.vence_el and frappe.utils.get_datetime(doc.vence_el) < now_datetime():
		if doc.estado != "Vencida":
			frappe.db.set_value(DT, doc.name, "estado", "Vencida", update_modified=False)
			frappe.db.commit()
		return None
	if not frappe.db.get_value("User", doc.usuario, "enabled"):
		return None
	return doc


def entrar(clave: str) -> bool:
	"""Deja entrar a la persona de ese enlace. True si lo logró.

	Se la identifica, no se le dan permisos: entra como ella misma y ve lo que
	su usuario pueda ver, que es su entrevista y nada más."""
	doc = leer(clave)
	if not doc:
		return False
	if frappe.session.user == doc.usuario:
		return True
	frappe.local.login_manager.login_as(doc.usuario)
	frappe.local.response["type"] = "page"
	if doc.estado != "Usada":
		frappe.db.set_value(DT, doc.name, {"estado": "Usada", "usada_el": now_datetime()}, update_modified=False)
		frappe.db.commit()
	return True
