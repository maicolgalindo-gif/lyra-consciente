// Qué activarle a esta empresa: la mesa donde el Equipo Lyra lee lo que Lyra
// recomienda después de la entrevista, y decide.
//
// Lyra propone con el porqué pegado a lo que el dueño contó; la decisión es del
// equipo. El dueño no ve esta pantalla: a él se le dijo cómo lo va a ayudar, sin
// módulos ni nada que aprobar.

const API_REC = "lyra_ia.diagnostico.recomendacion";
const escR = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

class Recomendacion {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: "Qué activarle a esta empresa", single_column: true });
		this.$ = $(`
			<div class="lyra-recomendacion">
				<div class="cabeza"></div>
				<div class="partes"></div>
				<div class="pie"></div>
			</div>`).appendTo(this.page.body);
		this.cargar();
	}

	async cargar(name) {
		const r = await frappe.call({ method: `${API_REC}.para_el_equipo`, args: { name: name || null } });
		this.d = r.message || { hay: false };
		this.pintar();
	}

	pintar() {
		const d = this.d;
		if (!d.hay) {
			this.$.find(".cabeza").html(`<p class="text-muted">Todavía no hay ninguna entrevista confirmada.
				Cuando el dueño termine la suya en <code>/lyra</code>, aquí aparece qué le recomienda Lyra y por qué.</p>`);
			this.$.find(".partes, .pie").empty();
			return;
		}
		// Si hay varias empresas, se puede saltar entre ellas.
		const otras = (d.diagnosticos || []).filter((x) => x.name !== d.name);
		this.$.find(".cabeza").html(`
			<h4>${escR(d.empresa)}</h4>
			<p class="text-muted resumen">${escR(d.resumen)}</p>
			<p class="text-muted small">Entrevista con ${escR(d.dueno || "el dueño")}, confirmada el
				${escR(frappe.datetime.str_to_user(d.confirmado_el))}.
				${d.decidido_el ? `Decidido el ${escR(frappe.datetime.str_to_user(d.decidido_el))} por ${escR(d.decidido_por)}.`
					: "Todavía nadie ha decidido qué activar."}</p>
			${otras.length ? `<p class="small">Otras empresas: ${otras.map((x) =>
				`<a href="#" data-ir="${escR(x.name)}">${escR(x.nombre_negocio || x.name)}</a>`).join(" · ")}</p>` : ""}`);
		this.$.find("[data-ir]").on("click", (e) => { e.preventDefault(); this.cargar(e.target.dataset.ir); });

		this.$.find(".partes").html((d.partes || []).map((p) => `
			<label class="parte ${p.dolor ? "duele" : ""}">
				<input type="checkbox" data-clave="${escR(p.clave)}" ${p.elegida ? "checked" : ""}>
				<span class="cuerpo">
					<b>${escR(p.nombre)}</b>
					${p.dolor ? `<span class="marca">le duele</span>` : ""}
					${p.instalada ? `<span class="marca ok">ya instalada</span>`
						: p.faltan.length ? `<span class="marca falta">falta instalar: ${escR(p.faltan.join(", "))}</span>` : ""}
					<span class="para-que">${escR(p.para_que)}</span>
					<span class="porque">${escR(p.porque)}</span>
				</span>
			</label>`).join("") || `<p class="text-muted">Lyra no recomienda nada todavía.</p>`);

		this.$.find(".pie").html(`<button class="btn btn-primary btn-sm guardar">Guardar lo que vamos a activar</button>`);
		this.$.find(".guardar").on("click", () => this.guardar());
	}

	async guardar() {
		const elegidas = this.$.find("input:checked").map((i, el) => el.dataset.clave).get();
		const r = await frappe.call({ method: `${API_REC}.decidir`, type: "POST",
			args: { name: this.d.name, elegidas }, freeze: true, freeze_message: "Guardando…" });
		const m = r.message || {};
		frappe.msgprint({
			title: "Decidido", indicator: "green",
			message: (m.elegidas || []).length
				? `<p>Se activa:</p><ul>${m.elegidas.map((x) => `<li>${escR(x)}</li>`).join("")}</ul>`
					+ (m.faltan_instalar || []).length
						? `<p class="text-muted">Falta instalar en el sitio: <b>${escR((m.faltan_instalar || []).join(", "))}</b>. `
						  + `Eso se hace desde el bench, no desde aquí.</p>` : ""
				: "<p>No se activa nada por ahora.</p>",
		});
		this.cargar(this.d.name);
	}
}

frappe.pages["lyra-recomendacion"].on_page_load = (wrapper) => new Recomendacion(wrapper);
