// Mi perfil: lo que cada quien cuenta de sí mismo.
//
// Es la otra mitad de la entrevista al funcionario, la que NO se cruza con el
// trabajo: aquí va quién es profesionalmente, y lo ve esa persona y nadie más,
// salvo que ella deje verlo a Recursos Humanos. El dueño no lo ve nunca, ni
// siquiera consolidado. Por eso la pantalla dice en todo momento quién lo ve.

const API_PERFIL = "lyra_ia.diagnostico.perfil";
const escP = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

class MiPerfil {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: "Mi perfil", single_column: true });
		this.$ = $(`
			<div class="lyra-perfil">
				<p class="text-muted intro">
					Esto es tuyo. Lo guarda Lyra para ti, y solo lo ve alguien más si tú lo permites aquí abajo.
					Tu jefe no lo ve, ni siquiera en resumen. Puedes dejar algo en blanco o borrarlo todo cuando quieras.
				</p>
				<div class="campos-perfil"></div>
				<section class="bloque-perfil hv">
					<h5>Tu hoja de vida</h5>
					<div class="estado-hv"></div>
					<button class="btn btn-sm btn-default subir-hv">Subir mi hoja de vida</button>
				</section>
				<section class="bloque-perfil permiso">
					<h5>Quién puede verlo</h5>
					<div class="estado-permiso"></div>
				</section>
				<div class="pie-perfil">
					<button class="btn btn-sm btn-danger borrar-perfil">Borrar mi perfil</button>
				</div>
			</div>`).appendTo(this.page.body);

		this.$.find(".subir-hv").on("click", () => this.subirHojaDeVida());
		this.$.find(".borrar-perfil").on("click", () => this.borrar());
		this.cargar();
	}

	async llamar(metodo, args) {
		const r = await frappe.call({ method: `${API_PERFIL}.${metodo}`, type: "POST", args: args || {} });
		return r.message;
	}

	async cargar() {
		this.datos = await this.llamar("mio");
		this.pintar();
	}

	pintar() {
		const d = this.datos;
		this.$.find(".campos-perfil").html(
			(d.preguntas || []).map((p) => `
				<div class="campo-perfil" data-campo="${p.campo}">
					<label>${escP(p.pregunta)}</label>
					<textarea rows="2" data-campo="${p.campo}">${escP(d.datos[p.campo] || "")}</textarea>
				</div>`).join(""));

		// Se guarda al salir del campo: nadie debería tener que buscar un botón.
		this.$.find("textarea").on("blur", async (e) => {
			const campo = e.target.dataset.campo;
			const valor = e.target.value.trim();
			if (valor === (this.datos.datos[campo] || "")) return;
			this.datos = await this.llamar("responder", { campo, respuesta: valor });
			frappe.show_alert({ message: "Guardado", indicator: "green" }, 2);
		});

		this.$.find(".estado-hv").html(d.hoja_vida
			? `<a href="${escP(d.hoja_vida)}" target="_blank">Ver la que subiste</a>`
			: `<span class="text-muted">Todavía no has subido ninguna.</span>`);

		const comparte = d.compartir_rrhh;
		this.$.find(".estado-permiso").html(`
			<label class="interruptor">
				<input type="checkbox" ${comparte ? "checked" : ""}>
				<span>Dejo que Recursos Humanos vea mi perfil</span>
			</label>
			<p class="text-muted small">${comparte
				? "Recursos Humanos puede leerlo. No puede cambiarlo, y puedes quitarles el permiso cuando quieras."
				: "Ahora mismo solo lo ves tú."}</p>`);
		this.$.find(".estado-permiso input").on("change", async (e) => {
			await this.llamar("permitir_rrhh", { permitir: e.target.checked ? 1 : 0 });
			this.cargar();
		});
	}

	subirHojaDeVida() {
		new frappe.ui.FileUploader({
			doctype: "Perfil Funcionario",
			docname: this.datos.name,
			frm: null,
			folder: "Home/Attachments",
			restrictions: { allowed_file_types: [".pdf", ".doc", ".docx", "image/*"] },
			on_success: async (archivo) => {
				await frappe.db.set_value("Perfil Funcionario", this.datos.name, "hoja_vida", archivo.file_url);
				frappe.show_alert({ message: "Hoja de vida guardada", indicator: "green" });
				this.cargar();
			},
		});
	}

	borrar() {
		frappe.confirm("¿Borro tu perfil? Se va todo lo que contaste aquí y no se puede deshacer.", async () => {
			await this.llamar("borrar");
			frappe.show_alert({ message: "Tu perfil se borró", indicator: "orange" });
			this.cargar();
		});
	}
}

frappe.pages["mi-perfil"].on_page_load = (wrapper) => new MiPerfil(wrapper);
