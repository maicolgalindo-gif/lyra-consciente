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

# Registro de uso: 90 dias (se cambia en Log Settings).
default_log_clearing_doctypes = {"IA Registro": 90}

# Preguntas de clasificacion de cada modulo (ver clasificador.py). Cada app de
# Lyra puede declarar las suyas con este mismo hook; solo cuentan las de apps
# instaladas.
lyra_ia_preguntas = ["lyra_ia.copiloto.preguntas_whatsapp"]

# Herramientas del asistente, por modulo (ver herramientas.py). Solo aparecen
# las de apps instaladas y que el usuario tenga permiso de ver.
lyra_ia_herramientas = ["lyra_ia.herramientas_crm.herramientas"]
