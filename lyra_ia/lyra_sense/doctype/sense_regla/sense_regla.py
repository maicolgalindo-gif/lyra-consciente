import frappe
from frappe import _
from frappe.model.document import Document


class SenseRegla(Document):
	"""Una regla de omision. La aplica sense/reglas.py."""

	def validate(self):
		from lyra_ia.sense.reglas import puede_completar

		meta = frappe.get_meta(self.ref_doctype)
		df = meta.get_field(self.campo)
		if not df:
			frappe.throw(_("El documento {0} no tiene el campo «{1}».").format(_(self.ref_doctype), self.campo))
		if meta.istable or meta.issingle:
			frappe.throw(_("Elige un documento normal (no una tabla ni unos ajustes)."))
		if self.modo == "Completar":
			motivo = puede_completar(meta, df)
			if motivo:
				frappe.throw(_("Lyra no puede completar este dato: {0} Usa «Avisar».").format(motivo))
			if not (self.valor or "").strip():
				frappe.throw(_("Escribe con qué se completa."))
		if self.condicion:
			try:
				compile(self.condicion, "<condicion>", "eval")
			except SyntaxError:
				frappe.throw(_("La condición no es una expresión válida."))
