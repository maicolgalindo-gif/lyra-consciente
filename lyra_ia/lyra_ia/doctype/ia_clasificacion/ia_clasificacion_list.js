frappe.listview_settings["IA Clasificacion"] = {
	add_fields: ["corregida", "respuesta_final"],
	get_indicator(doc) {
		return doc.corregida ? ["Corregida", "orange", "corregida,=,1"] : ["De la IA", "blue", "corregida,=,0"];
	},
	onload(list) {
		list.page.add_inner_button("Descargar ejemplos para Laya", () => {
			frappe.prompt(
				{ fieldname: "conjunto", fieldtype: "Data", label: "Conjunto", default: "whatsapp", reqd: 1,
					description: "Los ejemplos revisados por el equipo, en el formato para entrenar a Laya (JSONL)." },
				(v) => window.open(`/api/method/lyra_ia.clasificador.descargar_ejemplos?conjunto=${encodeURIComponent(v.conjunto)}`),
				"Ejemplos para entrenar a Laya",
				"Descargar"
			);
		});
	},
};
