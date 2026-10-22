// El organigrama que sale de las entrevistas: nadie lo dibuja a mano.
// Línea llena = quién le reporta a quién. Línea punteada = por dónde pasa el
// trabajo de verdad, que casi nunca es igual al cuadrito oficial.

const API_ORG = "lyra_ia.diagnostico.organigrama";
const escO = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

const ANCHO = 180, ALTO = 62, SEP_X = 28, SEP_Y = 86;

class LyraOrganigrama {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: "Organigrama", single_column: true });
		this.conNombres = true;
		this.page.add_menu_item("Mostrar solo los cargos", () => { this.conNombres = !this.conNombres; this.cargar(); });
		this.page.add_menu_item("Entrevistas de trabajo", () => frappe.set_route("List", "Diagnostico Funcionario"));
		this.$ = $(`
			<div class="lyra-organigrama">
				<p class="text-muted intro"></p>
				<div class="lienzo-org"></div>
				<section class="bloque-org flujo"></section>
			</div>`).appendTo(this.page.body);
		this.cargar();
	}

	async cargar() {
		const r = await frappe.call({ method: `${API_ORG}.organigrama`, args: { con_nombres: this.conNombres ? 1 : 0 } });
		this.datos = r.message || { nodos: [], aristas: [], niveles: [] };
		this.pintar();
	}

	pintar() {
		const d = this.datos;
		this.$.find(".intro").html(d.entrevistados
			? `Armado con ${d.entrevistados} entrevista${d.entrevistados === 1 ? "" : "s"} confirmada${d.entrevistados === 1 ? "" : "s"}.
			   La línea llena es quién le reporta a quién; la punteada, por dónde pasa el trabajo.
			   ${d.sin_entrevistar.length ? `En gris, los cargos que alguien nombró pero que todavía no has entrevistado: ${escO(d.sin_entrevistar.join(", "))}.` : ""}`
			: `Todavía no hay entrevistas confirmadas. Cuando tu gente hable con Lyra en <code>/lyra</code>, el organigrama se arma solo.`);
		this.dibujar();
		this.pintarFlujo();
	}

	// Cada piso es una fila; el ancho lo manda el piso más lleno.
	posiciones() {
		const pisos = this.datos.niveles || [];
		const porClave = {};
		const anchoMax = Math.max(1, ...pisos.map((p) => p.length)) * (ANCHO + SEP_X);
		pisos.forEach((piso, fila) => {
			const ancho = piso.length * (ANCHO + SEP_X);
			const x0 = (anchoMax - ancho) / 2;
			piso.forEach((clave, i) => {
				porClave[clave] = { x: x0 + i * (ANCHO + SEP_X) + SEP_X / 2, y: fila * (ALTO + SEP_Y) + 20 };
			});
		});
		return { porClave, ancho: anchoMax, alto: pisos.length * (ALTO + SEP_Y) + 20 };
	}

	dibujar() {
		const d = this.datos;
		if (!d.nodos.length) { this.$.find(".lienzo-org").html(""); return; }
		const { porClave, ancho, alto } = this.posiciones();
		const nodo = (n) => {
			const p = porClave[n.clave];
			if (!p) return "";
			const gente = n.personas && n.personas.length ? escO(n.personas.join(", "))
				: n.cuantos ? `${n.cuantos} persona${n.cuantos === 1 ? "" : "s"}` : "sin entrevistar";
			return `<g class="nodo-org ${n.cuantos ? "" : "vacio"}" transform="translate(${p.x},${p.y})">
					<rect width="${ANCHO}" height="${ALTO}" rx="10"/>
					<text class="cargo" x="14" y="25">${escO(n.cargo)}</text>
					<text class="gente" x="14" y="44">${gente}</text>
				</g>`;
		};
		const linea = (a) => {
			const o = porClave[a.de], t = porClave[a.a];
			if (!o || !t) return "";
			const x1 = o.x + ANCHO / 2, y1 = o.y + (t.y > o.y ? ALTO : 0);
			const x2 = t.x + ANCHO / 2, y2 = t.y + (t.y > o.y ? 0 : ALTO);
			const my = (y1 + y2) / 2;
			return `<path class="arista ${a.tipo}" d="M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}"
					marker-end="url(#punta-${a.tipo})"><title>${escO(a.porque)}</title></path>`;
		};
		this.$.find(".lienzo-org").html(`
			<svg viewBox="0 0 ${ancho} ${alto}" width="100%" height="${alto}" role="img" aria-label="Organigrama de la empresa">
				<defs>
					${["reporta", "entrega"].map((t) => `<marker id="punta-${t}" viewBox="0 0 8 8" refX="7" refY="4"
						markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" class="punta ${t}"/></marker>`).join("")}
				</defs>
				${d.aristas.map(linea).join("")}
				${d.nodos.map(nodo).join("")}
			</svg>`);
	}

	pintarFlujo() {
		const flujo = (this.datos.aristas || []).filter((a) => a.tipo === "entrega");
		const nombre = (c) => (this.datos.nodos.find((n) => n.clave === c) || {}).cargo || c;
		this.$.find(".flujo").html(!flujo.length ? "" : `
			<h5>Por dónde pasa el trabajo</h5>
			<ul class="lista-flujo">${flujo.map((a) => `
				<li><b>${escO(nombre(a.de))}</b> → <b>${escO(nombre(a.a))}</b>
					<span class="text-muted">${escO(a.porque)}</span></li>`).join("")}</ul>`);
	}
}

frappe.pages["lyra-organigrama"].on_page_load = (wrapper) => new LyraOrganigrama(wrapper);
