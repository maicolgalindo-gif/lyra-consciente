// Regla de «Lyra se da cuenta»: al elegir el documento, se ofrecen sus campos y
// se marca cuales Lyra puede completar sola (los demas, solo avisar).
frappe.ui.form.on("Sense Regla", {
	refresh(frm) {
		frm.trigger("cargar_campos");
		frm.set_intro("Lyra revisa esta regla en segundo plano después de que alguien guarda: nunca frena el trabajo. " +
			"Completar solo funciona en borradores y nunca en montos, consentimientos ni documentos validados.", "blue");
	},
	ref_doctype(frm) {
		frm.set_value("campo", "");
		frm.trigger("cargar_campos");
	},
	async cargar_campos(frm) {
		if (!frm.doc.ref_doctype) return;
		const r = await frappe.call({ method: "lyra_ia.sense.reglas.campos_de", args: { doctype: frm.doc.ref_doctype } });
		frm._campos = r.message || [];
		frm.set_df_property("campo", "options", frm._campos.map((c) => ({
			value: c.value, label: c.label + (c.completable ? "" : " · solo avisar"),
		})));
	},
	modo(frm) {
		const c = (frm._campos || []).find((x) => x.value === frm.doc.campo);
		if (frm.doc.modo === "Completar" && c && !c.completable) {
			frappe.msgprint("Lyra no puede completar ese dato (monto, consentimiento o similar). Queda en «Avisar».");
			frm.set_value("modo", "Avisar");
		}
	},
});
