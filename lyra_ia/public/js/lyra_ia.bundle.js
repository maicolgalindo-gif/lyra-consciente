// Lyra IA en el escritorio. Por ahora: el copiloto de los chats de WhatsApp.
// Las pantallas lo usan solo si existe y la IA esta activa:
//   if (window.lyra_ia && lyra_ia.activa()) $cabecera.append(lyra_ia.boton_chat({...}))

const API_COPILOTO = "lyra_ia.copiloto";
const escIA = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

const NOMBRES = {
	intencion: "Qué busca", urgencia: "Urgencia", sentimiento: "Cómo se siente", venta: "¿Oportunidad de venta?",
	pide_baja: "¿Pide que no le escriban?",
};
const OPCIONES = {
	precio: "Precio / cotización", agendar: "Agendar", compra: "Comprar", soporte: "Soporte", queja: "Queja",
	documentos: "Documentos", informacion: "Información", otro: "Otro", baja: "Baja", media: "Media", alta: "Alta",
	positivo: "Positivo", neutral: "Neutral", negativo: "Negativo", si: "Sí", no: "No",
};

window.lyra_ia = {
	activa() {
		return !!(frappe.boot.lyra_ia && frappe.boot.lyra_ia.activa);
	},

	/**
	 * Boton «IA» con su menu, para la cabecera de un chat.
	 * opciones: canal ("meta" | "waha"), id() -> numero o chat_id,
	 *           textarea() -> jQuery del cuadro de texto (o vacio si no se puede escribir),
	 *           al_cambiar() -> recargar el chat (despues de clasificar).
	 */
	boton_chat(opciones) {
		const $g = $(`
			<div class="btn-group lyra-ia-menu">
				<button class="btn btn-xs btn-default dropdown-toggle" data-toggle="dropdown" title="Copiloto de IA">IA</button>
				<div class="dropdown-menu dropdown-menu-right">
					<a class="dropdown-item" data-accion="resumir">Resumir la conversación</a>
					<a class="dropdown-item" data-accion="sugerir">Sugerir respuesta</a>
					<a class="dropdown-item" data-accion="indicar">Sugerir respuesta con una indicación…</a>
					<a class="dropdown-item" data-accion="clasificar">Clasificar el chat</a>
				</div>
			</div>`);
		$g.on("click", "[data-accion]", (e) => {
			e.preventDefault();
			const accion = $(e.currentTarget).data("accion");
			if (accion === "resumir") lyra_ia.resumir(opciones);
			else if (accion === "sugerir") lyra_ia.sugerir(opciones);
			else if (accion === "indicar") {
				frappe.prompt(
					{ fieldname: "instruccion", fieldtype: "Data", label: "¿Qué quieres que diga?", reqd: 1,
						placeholder: "Ej.: ofrécele cita mañana a las 9, más formal, dile que el precio es 120.000" },
					(v) => lyra_ia.sugerir(opciones, v.instruccion),
					"Sugerir respuesta",
					"Sugerir"
				);
			} else if (accion === "clasificar") lyra_ia.clasificar(opciones);
		});
		return $g;
	},

	async resumir(o) {
		const r = await frappe.call({
			method: `${API_COPILOTO}.resumir`, args: { canal: o.canal, ident: o.id() }, type: "POST",
			freeze: true, freeze_message: "Leyendo la conversación…",
		});
		if (!r.message) return;
		const html = escIA(r.message.resumen)
			.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
			.replace(/\n/g, "<br>");
		frappe.msgprint({ title: "Resumen de la conversación", message: `<div class="lyra-ia-resumen">${html}</div>`, wide: true });
	},

	async sugerir(o, instruccion) {
		const $t = o.textarea ? o.textarea() : $();
		if (!$t || !$t.length) {
			frappe.msgprint("No se puede escribir libre en este chat ahora (por ejemplo, la ventana de 24 horas de Meta está cerrada).");
			return;
		}
		const r = await frappe.call({
			method: `${API_COPILOTO}.sugerir`, args: { canal: o.canal, ident: o.id(), instruccion: instruccion || null }, type: "POST",
			freeze: true, freeze_message: "Escribiendo una sugerencia…",
		});
		if (!r.message) return;
		const poner = () => {
			$t.val(r.message.texto).trigger("input").trigger("focus");
			frappe.show_alert({ message: "Sugerencia lista: revísala antes de enviarla.", indicator: "blue" });
		};
		if (($t.val() || "").trim()) frappe.confirm("Ya escribiste algo. ¿Reemplazarlo por la sugerencia?", poner);
		else poner();
	},

	async clasificar(o) {
		const r = await frappe.call({
			method: `${API_COPILOTO}.clasificar`, args: { canal: o.canal, ident: o.id() }, type: "POST",
			freeze: true, freeze_message: "Clasificando…",
		});
		if (!r.message) return;
		const { respuestas, etiquetas_sugeridas, etiquetas_actuales } = r.message;
		const campos = Object.entries(respuestas).map(([clave, p]) => ({
			fieldname: clave,
			fieldtype: "Select",
			label: `${NOMBRES[clave] || clave}${p.respuesta ? ` · ${Math.round(p.confianza * 100)}%` : ""}`,
			options: [{ value: "", label: "" }, ...p.opciones.map((x) => ({ value: x, label: OPCIONES[x] || x }))],
			default: p.respuesta || "",
		}));
		const etiquetas = [...new Set([...(etiquetas_actuales || []), ...(etiquetas_sugeridas || [])])];
		const d = new frappe.ui.Dialog({
			title: "Clasificación del chat",
			fields: [
				{ fieldtype: "HTML", options: `<p class="text-muted small">Propuesta de la IA. Corrige lo que no esté bien:
					cada corrección enseña al sistema (sirve para entrenar a Laya).</p>` },
				...campos,
				{ fieldtype: "Section Break" },
				{ fieldname: "etiquetas", fieldtype: "Data", label: "Etiquetas del chat", default: etiquetas.join(", "),
					description: etiquetas_sugeridas.length ? `Sugeridas por la IA: ${etiquetas_sugeridas.join(", ")}` : "" },
			],
			primary_action_label: "Guardar",
			primary_action: async (v) => {
				const revisadas = {};
				Object.entries(respuestas).forEach(([clave, p]) => {
					if (p.id) revisadas[p.id] = v[clave] || null;
				});
				await frappe.call({
					method: `${API_COPILOTO}.guardar_clasificacion`,
					args: { canal: o.canal, ident: o.id(), revisadas, etiquetas: v.etiquetas || "" },
					type: "POST",
				});
				d.hide();
				frappe.show_alert({ message: "Clasificación guardada.", indicator: "green" });
				if (o.al_cambiar) o.al_cambiar();
			},
		});
		d.show();
	},
};
