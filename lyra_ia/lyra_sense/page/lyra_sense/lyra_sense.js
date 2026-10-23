// Lyra se da cuenta: como van los procesos por área (nunca por persona), las
// reglas de omisión, los últimos avisos y el reporte semanal al dueño.

const API_SENSE = "lyra_ia.sense.metricas";
const escS = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
const numS = (n) => (n || 0).toLocaleString("es-CO");

class LyraSense {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: "Lyra se da cuenta", single_column: true });
		this.page.set_primary_action("Nueva regla", () => frappe.new_doc("Sense Regla"), "add");
		this.page.add_menu_item("Ajustes y reporte semanal", () => frappe.set_route("Form", "Sense Ajustes"));
		this.page.add_menu_item("Todos los avisos", () => frappe.set_route("List", "Sense Aviso"));
		this.page.add_menu_item("Reportes enviados", () => frappe.set_route("List", "Sense Reporte"));
		this.$ = $(`
			<div class="lyra-sense">
				<div class="aviso-sense"></div>
				<p class="text-muted">Lyra mira en segundo plano lo que se crea y se guarda. Si falta un dato que una regla pide,
					avisa en privado a quien lo hizo (o lo completa, con Deshacer). Aquí ves cómo van los procesos de cada área
					en los últimos 7 días: nunca por persona.</p>
				<div class="tiles"></div>
				<section class="bloque"><h5>Por área</h5><div class="areas"></div></section>
				<div class="dos">
					<section class="bloque"><h5>Reglas <button class="btn btn-xs btn-default sugeridas">Proponer reglas de lo que contaron</button></h5>
						<div class="reglas"></div></section>
					<section class="bloque"><h5>Últimos avisos</h5><div class="avisos"></div></section>
				</div>
				<section class="bloque"><h5>Reporte semanal al dueño <button class="btn btn-xs btn-default enviar">Enviar uno ahora</button></h5>
					<div class="reporte"></div></section>
			</div>`).appendTo(this.page.body);
		// Las reglas salen de lo que la gente contó en su entrevista, no de una
		// lista fija: si nadie dijo nada, Lyra no propone nada.
		this.$.find(".sugeridas").on("click", async () => {
			const r = await frappe.call({ method: "lyra_ia.sense.propuestas.crear", type: "POST", freeze: true,
				freeze_message: "Mirando lo que contó la gente…" });
			const m = r.message || {};
			if (!m.cuantas) {
				frappe.msgprint({ title: "Nada que proponer", indicator: "blue",
					message: "No hay nada nuevo que proponer. Lyra propone reglas a partir de lo que la gente "
						+ "cuenta en su entrevista: si todavía no has entrevistado a nadie, o lo que contaron ya "
						+ "está vigilado, no hay de dónde sacarlas." });
			} else {
				frappe.msgprint({ title: "Reglas propuestas", indicator: "green",
					message: "<p>Lyra propone estas, apagadas. Ábrelas, mira por qué las propone y enciéndelas:</p><ul>"
						+ m.creadas.map((c) => `<li><b>${frappe.utils.escape_html(c.titulo)}</b> — lo dijeron ${c.personas} persona(s)</li>`).join("")
						+ "</ul>" });
			}
			this.cargar();
		});
		this.$.find(".enviar").on("click", async () => {
			const r = await frappe.call({ method: `${API_SENSE}.enviar_ahora`, type: "POST", freeze: true, freeze_message: "Armando el reporte…" });
			const m = r.message || {};
			frappe.msgprint({
				title: "Reporte semanal",
				message: `<div style="white-space:pre-wrap">${escS(m.texto)}</div>
					<p class="text-muted small" style="margin-top:10px">${m.enviado_a && m.enviado_a.length ? "Enviado a: " + escS(m.enviado_a.join(", "))
						: "No hay destinatarios configurados: quedó guardado. Ponlos en Ajustes y reporte semanal."}</p>`,
				wide: true,
			});
			this.cargar();
		});
	}

	async cargar() {
		const r = (await frappe.call({ method: `${API_SENSE}.tablero` })).message || {};
		const c = r.cifras || { total: {}, areas: [] };
		const t = c.total;
		this.$.find(".aviso-sense").html(r.activo ? "" : `<div class="alert alert-warning">«Lyra se da cuenta» está apagada.
			<a href="/app/sense-ajustes">Actívala en los ajustes</a>.</div>`);
		const tile = (titulo, valor, nota) => `<div class="tile"><span class="t">${escS(titulo)}</span><b>${escS(valor)}</b>${nota ? `<small>${escS(nota)}</small>` : ""}</div>`;
		this.$.find(".tiles").html(
			tile("Operaciones", numS(t.operaciones), "creados, guardados y validados") +
				tile("Efectividad", `${t.efectividad ?? 100}%`, "procesos completos a la primera") +
				tile("Omisiones", numS(t.omisiones), "datos que faltaban") +
				tile("Completadas por Lyra", numS(t.corregidas), t.deshechas ? `${numS(t.deshechas)} deshechas` : "") +
				tile("Avisos", numS(t.avisos), "en privado a cada persona")
		);
		this.$.find(".areas").html(
			c.areas.length
				? `<table class="table table-sm"><thead><tr><th>Área</th><th class="n">Operaciones</th><th class="n">Omisiones</th>
						<th class="n">Completadas</th><th class="n">Efectividad</th></tr></thead><tbody>${c.areas
						.map((a) => a.oculta
							? `<tr><td>${escS(a.area)}</td><td colspan="4" class="text-muted small">Menos de ${c.minimo} personas: no se muestra para no identificar a nadie.</td></tr>`
							: `<tr><td>${escS(a.area)}</td><td class="n">${numS(a.operaciones)}</td><td class="n">${numS(a.omisiones)}</td>
								<td class="n">${numS(a.corregidas)}</td><td class="n">${a.efectividad}%</td></tr>`)
						.join("")}</tbody></table>
					<p class="text-muted small">Las áreas con menos de ${c.minimo} personas se suman a «Otras áreas». El área sale del departamento de cada empleado en RR. HH.</p>`
				: `<p class="vacio">Todavía no hay actividad registrada esta semana.</p>`
		);
		const reglas = r.reglas || [];
		this.$.find(".reglas").html(
			reglas.length
				? `<table class="table table-sm"><tbody>${reglas
						.map((x) => `<tr><td><a href="/app/sense-regla/${encodeURIComponent(x.name)}">${escS(x.titulo)}</a>
							<div class="text-muted small">${escS(__(x.ref_doctype))} · ${escS(x.campo)}</div></td>
							<td><span class="chip ${x.activa ? x.modo : "apagada"}">${x.activa ? x.modo : "Apagada"}</span></td>
							<td class="n small text-muted">${numS(x.veces)} veces</td></tr>`)
						.join("")}</tbody></table>`
				: `<p class="vacio">No hay reglas. Crea una o agrega las sugeridas para empezar.</p>`
		);
		const avisos = r.avisos || [];
		this.$.find(".avisos").html(
			avisos.length
				? avisos
						.map((a) => `<div style="margin-bottom:8px"><span class="chip ${a.tipo === "Corrección" ? "Completar" : "Avisar"}">${escS(a.tipo)}</span>
							${escS(a.mensaje)} <span class="text-muted small">· ${escS(a.area || "")} · ${escS(frappe.datetime.comment_when(a.creation))}${a.estado === "Deshecho" ? " · deshecho" : ""}</span></div>`)
						.join("")
				: `<p class="vacio">Sin avisos todavía.</p>`
		);
		const rep = r.reporte || {};
		const reportes = r.reportes || [];
		this.$.find(".reporte").html(`
			<p>${rep.activo ? `Se envía cada <b>${escS(rep.dia)}</b> a las <b>${escS(rep.hora)}:00</b>.` : `Está apagado.`}
				<a href="/app/sense-ajustes">Configurar</a></p>
			${reportes.length ? `<div class="small text-muted">Últimos: ${reportes.map((x) => `<a href="/app/sense-reporte/${encodeURIComponent(x.name)}">semana del ${escS(frappe.datetime.str_to_user(x.semana))}</a>`).join(" · ")}</div>` : ""}`);
	}
}

frappe.pages["lyra-sense"].on_page_load = function (wrapper) {
	wrapper.lyra_sense = new LyraSense(wrapper);
};
frappe.pages["lyra-sense"].on_page_show = function (wrapper) {
	wrapper.lyra_sense && wrapper.lyra_sense.cargar();
};
