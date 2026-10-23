"""El enlace personal con el que alguien entra a hablar con Lyra.

Sin esto, para entrevistar a alguien hay que crearle cuenta del ERP y que
recuerde una contraseña: el de almacén y el técnico de campo nunca van a pasar
por ahí, y la idea era entrevistar a toda la empresa.

El enlace identifica a la persona (Lyra tiene que saber de quién guarda lo que
cuenta), pero no le pide nada. Es personal, se vence y se puede revocar.
"""

import re
import unicodedata

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime

DIAS = 7


def _sin_tildes(nombre: str) -> str:
	"""«Marta Pérez» -> «marta.perez». Frappe no acepta tildes en un correo, y
	media Colombia tiene una en el apellido."""
	plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
	limpio = re.sub(r"[^a-zA-Z0-9]+", ".", plano).strip(".").lower()
	return (limpio or "persona")[:30]


class InvitacionLyra(Document):
	def before_insert(self):
		self.clave = frappe.generate_hash(length=40)
		self.vence_el = add_days(now_datetime(), DIAS)
		self.estado = "Sin usar"
		self.usuario = self._usuario()
		self.enlace = self._enlace()

	def _usuario(self) -> str:
		"""La persona, como usuario de Frappe. Si ya existe, se reusa."""
		correo = (self.correo or "").strip().lower()
		if not correo:
			# Sin correo, uno interno: no recibe nada, solo sirve para que Lyra
			# sepa de quién es lo que guarda.
			base = _sin_tildes(self.nombre_persona or "persona")
			correo = f"{base}.{frappe.generate_hash(length=6)}@lyra.local"
		if frappe.db.exists("User", correo):
			return correo
		partes = (self.nombre_persona or "").strip().split(" ", 1)
		frappe.get_doc({
			"doctype": "User", "email": correo, "first_name": partes[0] or _("Persona"),
			"last_name": partes[1] if len(partes) > 1 else "",
			"send_welcome_email": 0, "user_type": "System User", "enabled": 1,
		}).insert(ignore_permissions=True)
		return correo

	def _enlace(self) -> str:
		return f"{frappe.utils.get_url()}/lyra?i={self.clave}"
