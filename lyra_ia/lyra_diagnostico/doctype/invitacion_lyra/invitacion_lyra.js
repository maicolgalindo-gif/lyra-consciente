// La invitación: un enlace para mandarle a alguien por WhatsApp.
frappe.ui.form.on("Invitacion Lyra", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.enlace) return;

		frm.add_custom_button("Copiar el enlace", () => {
			frappe.utils.copy_to_clipboard(frm.doc.enlace);
			frappe.show_alert({ message: "Copiado. Pégalo en el chat de la persona.", indicator: "green" }, 4);
		});

		// El mensaje ya escrito, que es lo que de verdad se manda.
		frm.add_custom_button("Copiar el mensaje", () => {
			const texto = `Hola ${frm.doc.nombre_persona}, soy de Lyra. Quiero conocer cómo trabajas: `
				+ `son unos minutos y lo que cuentes de ti no lo ve nadie de tu empresa. `
				+ `Entra aquí: ${frm.doc.enlace}`;
			frappe.utils.copy_to_clipboard(texto);
			frappe.show_alert({ message: "Mensaje copiado.", indicator: "green" }, 4);
		});

		const vencida = frm.doc.estado === "Vencida";
		frm.dashboard.set_headline(
			vencida ? "Este enlace ya no sirve. Borra esta invitación y haz una nueva."
				: `Mándale este enlace a <b>${frappe.utils.escape_html(frm.doc.nombre_persona)}</b>. `
				  + "Es solo suyo y se vence; con él entra sin cuenta ni contraseña.");
	},
});
