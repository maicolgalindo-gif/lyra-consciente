// Asistente Lyra: la pantalla principal del modulo Lyra IA. Conversas con la
// IA y ella consulta los modulos activos (con tus permisos) para responder.

const API_AS = "lyra_ia.asistente";
const escA = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
const NOMBRE_CONSULTA = {
	buscar_registros: "buscó en el CRM", ficha_cliente: "ficha del cliente", cartera_vencida: "cartera vencida",
	embudo_ventas: "embudo de ventas", ventas_del_periodo: "ventas del periodo", buscar_chats: "buscó chats",
	chats_sin_responder: "chats sin responder", leer_chat: "leyó un chat",
};
// Ideas para empezar, segun lo que el usuario puede consultar.
const IDEAS = [
	{ requiere: "cartera_vencida", texto: "¿Quién me debe más de 30 días?" },
	{ requiere: "chats_sin_responder", texto: "¿Qué chats de WhatsApp están sin responder?" },
	{ requiere: "embudo_ventas", texto: "¿Cómo va el embudo de ventas?" },
	{ requiere: "ventas_del_periodo", texto: "¿Cuánto facturamos este mes y quiénes son los mejores clientes?" },
	{ requiere: "leer_chat", texto: "Resume el último chat de WhatsApp y sugiéreme una respuesta" },
	{ requiere: "buscar_registros", texto: "Muéstrame los clientes potenciales más recientes" },
];

function md(texto) {
	// Primero se escapa (el texto viene del modelo), luego Markdown.
	let html = frappe.markdown(escA(texto));
	// Codigos de documentos de ERPNext -> enlaces.
	html = html.replace(/\b((?:ACC-SINV|SAL-QTN|SAL-ORD|CRM-OPP|CRM-LEAD|CUST|SINV|QTN|SO)-[\w-]*\d)\b/g, (c) => {
		const ruta = c.startsWith("ACC-SINV") || c.startsWith("SINV") ? "sales-invoice"
			: c.startsWith("SAL-QTN") || c.startsWith("QTN") ? "quotation"
			: c.startsWith("SAL-ORD") || c.startsWith("SO") ? "sales-order"
			: c.startsWith("CRM-OPP") ? "opportunity" : c.startsWith("CRM-LEAD") ? "lead" : "customer";
		return `<a href="/app/${ruta}/${encodeURIComponent(c)}" target="_blank">${c}</a>`;
	});
	return html;
}

class AsistenteLyra {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: "Asistente Lyra", single_column: true });
		this.page.set_secondary_action("Nueva conversación", () => this.nueva());
		this.actual = null;
		this.$ = $(`
			<div class="lyra-ia">
				<aside class="lyra-ia-historial">
					<div class="titulo">Conversaciones</div>
					<div class="lista"></div>
				</aside>
				<section class="lyra-ia-chat">
					<div class="aviso-ia"></div>
					<div class="mensajes"></div>
					<footer class="redactor">
						<textarea class="form-control" rows="1" placeholder="Pregúntale a Lyra… (Enter para enviar)"></textarea>
						<button class="btn btn-primary btn-sm enviar">Enviar</button>
					</footer>
				</section>
			</div>`).appendTo(this.page.body);
		this.$msgs = this.$.find(".mensajes");
		this.$t = this.$.find("textarea");
		this.$t.on("input", () => {
			this.$t[0].style.height = "auto";
			this.$t[0].style.height = Math.min(this.$t[0].scrollHeight, 180) + "px";
		});
		this.$t.on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				this.enviar();
			}
		});
		this.$.find(".enviar").on("click", () => this.enviar());
		this.$.on("click", ".idea", (e) => {
			this.$t.val($(e.currentTarget).text()).trigger("input");
			this.enviar();
		});
		this.$.on("click", ".lyra-ia-historial .item", (e) => {
			if ($(e.target).closest(".borrar").length) return;
			this.abrir($(e.currentTarget).data("name"));
		});
		this.$.on("click", ".lyra-ia-historial .borrar", (e) => {
			const name = $(e.currentTarget).closest(".item").data("name");
			frappe.confirm("¿Borrar esta conversación?", async () => {
				await frappe.call({ method: `${API_AS}.borrar`, args: { name }, type: "POST" });
				if (name === this.actual) this.nueva();
				this.cargar_historial();
			});
		});
	}

	async mostrar() {
		const r = await frappe.call({ method: `${API_AS}.estado` });
		this.estado = r.message || {};
		const $a = this.$.find(".aviso-ia");
		if (!this.estado.lista) {
			$a.html(`<div class="alert alert-warning">La IA todavía no está activa.
				${this.estado.es_admin ? `Configúrala en <a href="/app/ia-ajustes">IA Ajustes</a>: proveedor, clave y activar.`
					: "Pídele al administrador que la active."}</div>`);
		} else {
			$a.empty();
		}
		this.$t.prop("disabled", !this.estado.lista);
		this.cargar_historial();
		if (!this.actual) this.bienvenida();
	}

	bienvenida() {
		const ideas = IDEAS.filter((i) => (this.estado.herramientas || []).includes(i.requiere));
		const mods = (this.estado.modulos || []).join(", ");
		this.$msgs.html(`
			<div class="bienvenida">
				<h4>Hola, ${escA(frappe.session.user_fullname || "")}</h4>
				<p class="text-muted">Pregúntame lo que necesites de Lyra. Consulto los módulos a los que tienes acceso
					${mods ? `(<b>${escA(mods)}</b>)` : ""} con tus mismos permisos. Por ahora consulto y redacto; crear, enviar
					o cambiar cosas llega pronto, y siempre te pediré confirmación.</p>
				${ideas.length ? `<div class="ideas">${ideas.map((i) => `<button class="btn btn-default btn-sm idea">${escA(i.texto)}</button>`).join("")}</div>` : ""}
			</div>`);
	}

	async cargar_historial() {
		const r = await frappe.call({ method: `${API_AS}.conversaciones` });
		const lista = r.message || [];
		this.$.find(".lyra-ia-historial .lista").html(
			lista.length
				? lista
						.map(
							(c) => `<div class="item ${c.name === this.actual ? "activo" : ""}" data-name="${escA(c.name)}">
								<span class="t">${escA(c.titulo || "Conversación")}</span>
								<button class="btn btn-xs btn-link borrar" title="Borrar">${frappe.utils.icon("delete", "xs")}</button>
							</div>`
						)
						.join("")
				: `<div class="text-muted small vacio">Aún no hay conversaciones.</div>`
		);
	}

	nueva() {
		this.actual = null;
		this.$.find(".lyra-ia-historial .item").removeClass("activo");
		this.bienvenida();
		this.$t.trigger("focus");
	}

	async abrir(name) {
		const r = await frappe.call({ method: `${API_AS}.abrir`, args: { name } });
		if (!r.message) return;
		this.actual = name;
		this.$.find(".lyra-ia-historial .item").removeClass("activo");
		this.$.find(`.lyra-ia-historial .item[data-name="${name}"]`).addClass("activo");
		this.pintar(r.message.mensajes);
	}

	pintar(mensajes) {
		this.$msgs.html(
			mensajes
				.map((m) =>
					m.rol === "usuario"
						? `<div class="msg yo"><div class="burbuja">${escA(m.texto).replace(/\n/g, "<br>")}</div></div>`
						: `<div class="msg lyra"><div class="burbuja">${md(m.texto)}
							${(m.consultas || []).length ? `<div class="consultas">Consultó: ${m.consultas.map((c) => escA(NOMBRE_CONSULTA[c] || c)).join(" · ")}</div>` : ""}
						</div></div>`
				)
				.join("")
		);
		this.$msgs.scrollTop(this.$msgs[0].scrollHeight);
	}

	async enviar() {
		const texto = (this.$t.val() || "").trim();
		if (!texto || this._enviando) return;
		this._enviando = true;
		if (!this.actual) this.$msgs.empty();
		this.$msgs.append(`<div class="msg yo"><div class="burbuja">${escA(texto).replace(/\n/g, "<br>")}</div></div>
			<div class="msg lyra pensando"><div class="burbuja"><span class="puntos"><i></i><i></i><i></i></span> Consultando…</div></div>`);
		this.$msgs.scrollTop(this.$msgs[0].scrollHeight);
		this.$t.val("").trigger("input").prop("disabled", true);
		try {
			const r = await frappe.call({ method: `${API_AS}.preguntar`, args: { texto, name: this.actual }, type: "POST" });
			if (r.message) {
				const nueva = !this.actual;
				this.actual = r.message.name;
				this.pintar(r.message.mensajes);
				if (nueva) this.cargar_historial();
			}
		} catch (e) {
			this.$msgs.find(".pensando").remove();
		} finally {
			this._enviando = false;
			this.$msgs.find(".pensando").remove();
			this.$t.prop("disabled", false).trigger("focus");
		}
	}
}

frappe.pages["asistente-ia"].on_page_load = function (wrapper) {
	wrapper.asistente = new AsistenteLyra(wrapper);
};
frappe.pages["asistente-ia"].on_page_show = function (wrapper) {
	wrapper.asistente && wrapper.asistente.mostrar();
};
