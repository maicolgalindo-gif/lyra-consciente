// El alma se llena sola; este boton solo la pone al dia sin esperar al programador.
frappe.ui.form.on("Lyra Alma", {
	refresh(frm) {
		frm.add_custom_button("Actualizar ahora", async () => {
			await frappe.call({ method: "lyra_ia.alma.actualizar", type: "POST", freeze: true, freeze_message: "Lyra está repasando lo que sabe…" });
			frm.reload_doc();
		});
	},
});
