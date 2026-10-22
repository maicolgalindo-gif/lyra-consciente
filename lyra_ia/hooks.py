app_name = "lyra_ia"
app_title = "Lyra IA"
app_publisher = "Algoritmia Labs"
app_description = "Inteligencia artificial de Lyra: cerebro LLM, registro de uso y clasificaciones para todo el CRM."
app_email = "maicol.galindo@devshouse.org"
app_license = "mit"

# El copiloto (botones de IA en los chats y donde se vaya agregando) carga en
# todo el escritorio; si la IA esta apagada no muestra nada.
app_include_js = ["lyra_ia.bundle.js"]
app_include_css = ["lyra_ia.bundle.css"]

# El modulo «Lyra IA» del menu y su entrada en /apps.
add_to_apps_screen = [
	{"name": "lyra_ia", "logo": "/assets/lyra_ia/images/lyra_ia.svg", "title": "Lyra IA", "route": "/app/lyra-ia"}
]

# frappe.boot.lyra_ia: si la IA esta lista, para que las pantallas decidan si
# muestran los botones.
boot_session = "lyra_ia.boot.boot"

after_install = "lyra_ia.setup.despues_de_migrar"
after_migrate = "lyra_ia.setup.despues_de_migrar"

# Registro de uso: 90 dias (se cambia en Log Settings).
default_log_clearing_doctypes = {"IA Registro": 90, "Sense Evento": 90, "Sense Aviso": 180}

# Preguntas de clasificacion de cada modulo (ver clasificador.py). Cada app de
# Lyra puede declarar las suyas con este mismo hook; solo cuentan las de apps
# instaladas.
lyra_ia_preguntas = ["lyra_ia.copiloto.preguntas_whatsapp"]

# Herramientas del asistente, por modulo (ver herramientas.py). Solo aparecen
# las de apps instaladas y que el usuario tenga permiso de ver.
lyra_ia_herramientas = ["lyra_ia.herramientas_crm.herramientas"]

# ---------------------------------------------------------------------------
# Lyra se da cuenta (modulo Lyra Sense): mira lo que pasa, aplica las reglas de
# omision, avisa en privado y arma las metricas por area. Ver sense/.
doc_events = {
	"*": {
		"on_update": "lyra_ia.sense.captura.capturar",
		"on_submit": "lyra_ia.sense.captura.capturar",
		"on_cancel": "lyra_ia.sense.captura.capturar",
	},
	# El alma aprende de cada diagnostico confirmado (ver alma.py).
	"Diagnostico Empresa": {"on_update": "lyra_ia.alma.al_confirmar_diagnostico"},
	"Lyra Alma": {"on_update": "lyra_ia.alma.al_guardar_notas"},
	"Sense Regla": {
		"on_update": "lyra_ia.sense.reglas.limpiar_cache",
		"on_trash": "lyra_ia.sense.reglas.limpiar_cache",
	},
}

# El perfil profesional del funcionario no se protege solo con el doctype: estas
# dos funciones las consulta Frappe en cada lectura, venga de donde venga (lista,
# informe, API). Ver diagnostico/perfil.py.
permission_query_conditions = {"Perfil Funcionario": "lyra_ia.diagnostico.perfil.condiciones"}
has_permission = {"Perfil Funcionario": "lyra_ia.diagnostico.perfil.puede_ver"}

scheduler_events = {
	# El reporte semanal al dueno: se revisa cada hora si es el dia y la hora.
	"hourly": ["lyra_ia.sense.metricas.tick"],
	# El alma se pone al dia con lo que cambio en la empresa.
	"daily": ["lyra_ia.alma.actualizar_en_segundo_plano"],
}
