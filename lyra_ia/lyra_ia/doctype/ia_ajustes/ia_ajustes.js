// IA Ajustes: proveedor, probar la conexion y gasto del mes.
const PROVEEDORES_IA = {
	DeepSeek: { url: "https://api.deepseek.com", chat: "deepseek-chat", razonador: "deepseek-reasoner" },
	OpenRouter: { url: "https://openrouter.ai/api/v1", chat: "deepseek/deepseek-chat", razonador: "deepseek/deepseek-r1" },
	Together: { url: "https://api.together.xyz/v1", chat: "deepseek-ai/DeepSeek-V3", razonador: "deepseek-ai/DeepSeek-R1" },
};

frappe.ui.form.on("IA Ajustes", {
	refresh(frm) {
		frm.add_custom_button("Probar conexión", async () => {
			if (frm.is_dirty()) await frm.save();
			const r = await frappe.call({ method: "lyra_ia.cerebro.probar_conexion", type: "POST", freeze: true, freeze_message: "Probando…" });
			const m = r.message || {};
			frappe.msgprint({ title: m.ok ? "Conexión correcta" : "No se pudo conectar", message: frappe.utils.escape_html(m.estado || ""),
				indicator: m.ok ? "green" : "red" });
			frm.reload_doc();
		});
		frm.add_custom_button("Probar voz", async () => {
			if (frm.is_dirty()) await frm.save();
			const r = await frappe.call({ method: "lyra_ia.voz.probar", type: "POST", freeze: true, freeze_message: "Lyra está hablando…" });
			const m = r.message || {};
			if (m.audio) new Audio(`data:audio/mpeg;base64,${m.audio}`).play();
			frappe.show_alert({ message: frappe.utils.escape_html(m.estado || ""), indicator: m.ok ? "green" : "red" }, 8);
			frm.reload_doc();
		});
		// Las voces las pone VoiceStudio: se piden y se elige una, en vez de copiar
		// el identificador a mano.
		frm.add_custom_button("Ver voces", async () => {
			if (frm.is_dirty()) await frm.save();
			const r = await frappe.call({ method: "lyra_ia.voz.voces", freeze: true, freeze_message: "Preguntándole a VoiceStudio…" });
			const voces = r.message || [];
			if (!voces.length) return frappe.msgprint("VoiceStudio no tiene voces todavía.");
			const d = new frappe.ui.Dialog({
				title: "Voces de VoiceStudio",
				fields: [{ fieldname: "voz", fieldtype: "Select", label: "Voz", reqd: 1,
					options: voces.map((v) => `${v.nombre} (${v.id})`).join("\n") }],
				primary_action_label: "Usar esta voz",
				primary_action(valores) {
					const id = (valores.voz.match(/\(([^)]+)\)$/) || [])[1];
					frm.set_value("voz_id", id);
					d.hide();
					frappe.show_alert({ message: "Guarda y toca «Probar voz».", indicator: "blue" });
				},
			});
			d.show();
		});
		frm.add_custom_button("Ir al asistente", () => frappe.set_route("asistente-ia"));
		frappe.call({ method: "lyra_ia.cerebro.resumen_gasto" }).then((r) => {
			const g = r.message || {};
			const usd = (v) => `USD ${Number(v || 0).toFixed(4)}`;
			frm.fields_dict.gasto_mes.$wrapper.html(`
				<div class="text-muted small" style="line-height:1.7">
					Este mes: <b>${g.llamadas || 0}</b> usos${g.errores ? ` (${g.errores} con error)` : ""} ·
					${(g.tokens_entrada || 0).toLocaleString("es-CO")} tokens de entrada y ${(g.tokens_salida || 0).toLocaleString("es-CO")} de salida<br>
					${g.con_precios ? `Costo: <b>${usd(g.costo)}</b>${g.limite ? ` de ${usd(g.limite)}` : ""}`
						: "Pon los precios del proveedor para ver el costo y usar el límite mensual."}
				</div>`);
		});
	},
	proveedor(frm) {
		const p = PROVEEDORES_IA[frm.doc.proveedor];
		if (!p) return;
		frm.set_value("url_base", p.url);
		frm.set_value("modelo_chat", p.chat);
		frm.set_value("modelo_razonador", p.razonador);
		frappe.show_alert({ message: "Revisa que el nombre del modelo coincida con el de tu cuenta en el proveedor.", indicator: "blue" });
	},
});
