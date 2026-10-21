"""Lyra se da cuenta: reglas de omision (Sense Regla).

«Si en este documento falta este dato, avisar (o completarlo)». Corre en segundo
plano despues del guardado (captura.py la encola), asi que nunca frena a nadie.

Protecciones, en el codigo y no solo en la regla:
- Completar solo en borradores (docstatus 0): nada validado, anulado ni enviado a la DIAN.
- Nunca montos ni cantidades, ni consentimientos, aceptaciones o autorizaciones:
  marcarlos por alguien seria hablar por el. Esos campos solo admiten «Avisar».
- Antes de completar se vuelve a leer el documento: si ya lo lleno, no se toca.
- Todo cambio de Lyra queda con Deshacer y en el historial del documento.
- Lyra no reacciona a sus propios cambios (frappe.flags.lyra_sense_cambio).
- Pocos avisos: la misma regla y documento como mucho cada 12 h, y un tope por hora.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.safe_exec import safe_eval

DT_REGLA = "Sense Regla"
DT_AVISO = "Sense Aviso"
EVENTOS = {"Crear": ("Al crear", "Al guardar"), "Guardar": ("Al guardar",), "Validar": ("Al validar",)}
# Sin «Check»: marcar una casilla sola puede deshabilitar un cliente o congelar una cuenta.
TIPOS_COMPLETABLES = {"Data", "Select", "Link", "Small Text", "Text", "Date", "Datetime", "Phone", "Dynamic Link"}
NO_COMPLETAR = ("consent", "acept", "autoriz", "habeas", "firma", "terminos", "términos", "acuerdo")


def puede_completar(meta, df) -> str | None:
	"""Por que Lyra no puede completar este campo (None si si puede)."""
	if df.fieldtype not in TIPOS_COMPLETABLES:
		return _("es un campo de tipo {0} (montos, cantidades o tablas no se tocan).").format(df.fieldtype)
	nombre = f"{df.fieldname} {df.label or ''}".lower()
	if any(p in nombre for p in NO_COMPLETAR):
		return _("es un consentimiento, aceptación o autorización: solo la persona puede darlo.")
	return None


def hay_reglas(doctype: str) -> bool:
	clave = "lyra_sense_doctypes_con_reglas"
	con = frappe.cache.get_value(clave, expires=True)
	if con is None:
		con = list(set(frappe.get_all(DT_REGLA, filters={"activa": 1}, pluck="ref_doctype")))
		frappe.cache.set_value(clave, con, expires_in_sec=300)
	return doctype in con


def limpiar_cache(doc=None, method=None) -> None:
	"""Al guardar o borrar una regla (doc_events de Sense Regla)."""
	frappe.cache.delete_value("lyra_sense_doctypes_con_reglas")


def _vacio(valor) -> bool:
	return valor in (None, "", 0, "0") if not isinstance(valor, (list, tuple)) else not valor


def _cumple(regla, doc) -> bool:
	if not (regla.condicion or "").strip():
		return True
	try:
		return bool(safe_eval(regla.condicion, None, {"doc": doc, "frappe": frappe._dict(utils=frappe.utils)}))
	except Exception:
		return False


def revisar(ref_doctype: str, ref_name: str, accion: str, usuario: str) -> None:
	"""Aplica las reglas activas de ese documento. Encolada por captura.py."""
	if not frappe.db.exists(ref_doctype, ref_name):
		return
	reglas = frappe.get_all(DT_REGLA, filters={"activa": 1, "ref_doctype": ref_doctype, "evento": ["in", EVENTOS.get(accion, ())]},
							fields=["name", "titulo", "campo", "condicion", "modo", "valor", "mensaje"])
	if not reglas:
		return
	doc = frappe.get_doc(ref_doctype, ref_name)
	for regla in reglas:
		try:
			if not _vacio(doc.get(regla.campo)) or not _cumple(regla, doc):
				continue
			if _reciente(regla.name, ref_name):
				continue
			if regla.modo == "Completar" and _completar(regla, doc, usuario):
				continue
			_avisar(regla, doc, usuario)
		except Exception:
			frappe.log_error(title=f"Lyra se da cuenta: regla {regla.titulo}")
	frappe.db.commit()


def _reciente(regla: str, ref_name: str) -> bool:
	clave = f"lyra_sense_regla:{regla}:{ref_name}"
	if frappe.cache.get_value(clave, expires=True):
		return True
	frappe.cache.set_value(clave, 1, expires_in_sec=12 * 3600)
	return False


def _completar(regla, doc, usuario: str) -> bool:
	"""Pone el valor si se puede. Devuelve False si hay que avisar en su lugar."""
	df = doc.meta.get_field(regla.campo)
	if not df or doc.docstatus != 0 or puede_completar(doc.meta, df):
		return False
	valor = (regla.valor or "").replace("{usuario}", usuario).strip()
	if not valor:
		return False
	# Releer: si la persona ya lo lleno en este rato, no se toca.
	actual = frappe.db.get_value(doc.doctype, doc.name, regla.campo)
	if not _vacio(actual):
		return True
	frappe.flags.lyra_sense_cambio = True
	try:
		frappe.db.set_value(doc.doctype, doc.name, regla.campo, valor)
	finally:
		frappe.flags.lyra_sense_cambio = False
	doc.add_comment("Info", _("Lyra completó «{0}» con «{1}» (regla «{2}»). Se puede deshacer.").format(
		_(df.label or df.fieldname), valor, regla.titulo))
	from lyra_ia.sense.avisos import enviar

	enviar(regla, doc, usuario, tipo="Corrección", campo=regla.campo, anterior=actual, nuevo=valor)
	return True


def _avisar(regla, doc, usuario: str) -> None:
	from lyra_ia.sense.avisos import enviar

	enviar(regla, doc, usuario, tipo="Aviso", campo=regla.campo)


@frappe.whitelist(methods=["POST"])
def deshacer(aviso: str) -> dict:
	"""Devuelve el dato a como estaba antes de que Lyra lo completara."""
	a = frappe.get_doc(DT_AVISO, aviso)
	if a.usuario != frappe.session.user and "System Manager" not in frappe.get_roles():
		raise frappe.PermissionError
	if a.tipo != "Corrección" or a.estado == "Deshecho":
		return {"ok": False, "mensaje": _("Ya estaba deshecho.")}
	if not frappe.db.exists(a.ref_doctype, a.ref_name):
		return {"ok": False, "mensaje": _("El documento ya no existe.")}
	doc = frappe.get_doc(a.ref_doctype, a.ref_name)
	doc.check_permission("write")
	actual = doc.get(a.campo)
	if str(actual or "") != str(a.valor_nuevo or ""):
		frappe.db.set_value(DT_AVISO, a.name, "estado", "Visto")
		return {"ok": False, "mensaje": _("El dato ya cambió después; no se toca.")}
	frappe.flags.lyra_sense_cambio = True
	try:
		frappe.db.set_value(a.ref_doctype, a.ref_name, a.campo, a.valor_anterior or None)
	finally:
		frappe.flags.lyra_sense_cambio = False
	doc.add_comment("Info", _("Se deshizo lo que completó Lyra en «{0}».").format(a.campo))
	frappe.db.set_value(DT_AVISO, a.name, "estado", "Deshecho")
	return {"ok": True}


@frappe.whitelist()
def campos_de(doctype: str) -> list[dict]:
	"""Para el formulario de la regla: los campos que pueden faltar en ese documento."""
	frappe.only_for("System Manager")
	meta = frappe.get_meta(doctype)
	salida = []
	for df in meta.fields:
		if df.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Table MultiSelect",
							"Fold", "Heading", "Image") or not df.label:
			continue
		salida.append({"value": df.fieldname, "label": f"{_(df.label)} ({df.fieldname})",
					   "completable": not puede_completar(meta, df)})
	return salida
