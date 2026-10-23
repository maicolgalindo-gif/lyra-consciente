# Lyra Consciente

La capa de inteligencia de Lyra ERX: una app de Frappe que conoce la empresa, la
acompaña en el día a día y se da cuenta de lo que falta. El paquete se llama
`lyra_ia` (así se instala y así aparece en el código).

Funciona con **solo Frappe v15**. Si en el mismo sitio están ERPNext, las apps de
WhatsApp (`lyra_whatsapp`) o WAHA (`lyra_waha`), las aprovecha; si no, sigue
andando sin ellas.

## Qué hace

| Parte | Dónde | Qué hace |
|---|---|---|
| Diagnóstico del dueño | `diagnostico/entrevista.py`, página `/lyra` | El primer acercamiento: Lyra entrevista al dueño (primero a la persona, después la empresa), le muestra lo que entendió y le dice cómo lo va a ayudar. La recomendación de módulos queda aparte, solo para el Equipo Lyra |
| Diagnóstico de cada funcionario | `diagnostico/funcionario.py`, `cargos.py`, la misma `/lyra` | Lyra entra a toda la empresa: deduce el cargo de la primera respuesta, pregunta según el puesto (contabilidad, RR. HH., ventas…) y pide los formatos y manuales con los que se trabaja de verdad. Al dueño solo le llega el consolidado, por área y sin nombres |
| Organigrama (solo Equipo Lyra) | `diagnostico/organigrama.py`, página `lyra-organigrama` | Herramienta nuestra, no del cliente: se arma solo con lo que la gente contó. De los traspasos («de quién recibo, a quién entrego») salen quién le reporta a quién y por dónde pasa el trabajo de verdad, que casi nunca es igual al cuadrito oficial. Con eso el equipo entiende la empresa y arma la recomendación |
| Perfil profesional | `diagnostico/perfil.py` | La otra mitad, que no se cruza con la anterior: cuando Lyra ya entiende cómo trabaja, la misma conversación sigue con la persona (qué estudió, dónde ha trabajado, qué quiere aprender). Se guarda en su propio documento: ni el mapa del trabajo ni su transcripción lo tocan. Lo ven la persona y el Equipo Lyra; de la empresa, nadie |
| Asistente y copiloto | `asistente.py`, `copiloto.py`, `herramientas*.py` | Chat dentro del ERP que consulta los módulos activos con los permisos del usuario; ayuda en los chats de WhatsApp y WAHA si esas apps están |
| Lyra se da cuenta | `sense/`, página `lyra-sense` | En segundo plano: reglas de datos que faltan (avisa en privado o completa, con Deshacer), métricas por área (nunca por persona) y reporte semanal al dueño |
| Clasificaciones | `clasificador.py` | Preguntas con el formato de Laya; hoy responde el modelo y cada respuesta queda en IA Clasificacion para entrenar a Laya más adelante |

Lo que comparten:

| Pieza | Qué hace |
|---|---|
| `cerebro.py` | La única puerta a la IA (formato OpenAI: DeepSeek, OpenRouter, Together…). Límite de gasto y registro de cada llamada en IA Registro |
| `alma.py` | Lo que Lyra sabe de la empresa. Se llena sola (entrevista confirmada, empresa, ventas, clientes) y la IA la recibe como contexto |
| `voz.py` | La voz de Lyra con VoiceStudio, que corre en la misma máquina: no cobra y el texto no sale de ahí. Si falla, la voz del navegador |
| `privacidad.py` | Oculta correos, teléfonos y documentos antes de enviarlos a la IA |
| `entorno.py` | Qué apps hay instaladas y cómo se llama la empresa, en un solo lugar |

## Para empezar a trabajar

### Lo que necesitas

| Qué | Para qué | ¿Obligatorio? |
|---|---|---|
| Docker Desktop (8 GB de RAM libres o más) | Corre Frappe, MariaDB y Redis sin instalar nada más | Sí, con el entorno de LYRA |
| Acceso al repo `algoritmia-labs/LYRA` | El entorno local listo: Frappe v15 + ERPNext + HRMS | Recomendado |
| Frappe v15 | La base sobre la que corre esta app | Sí |
| ERPNext v15 | Datos del negocio para el asistente y el Alma (clientes, ventas, productos) | No, pero sin él el asistente no tiene qué consultar |
| Clave de DeepSeek (u otro proveedor compatible con OpenAI) | La IA: entrevista, asistente, copiloto, resúmenes | Para probar la IA. Sin clave, la entrevista corre con un guion fijo |
| VoiceStudio en la máquina (lo deja andando `scripts/voz-servicio.sh`) | La voz de Lyra | No: sin él usa la voz del navegador |
| Chrome o Edge | Responder hablando en la entrevista (micrófono) | No: también se puede escribir |

### Montarlo con el entorno de LYRA (recomendado)

1. Levanta LYRA en local siguiendo su `LOCAL_SETUP.md` (`docker compose -f docker-compose.local.yml up -d`).
   Queda en http://localhost:8000.
2. En tu Mac, dentro de la carpeta de LYRA, clona este repo como `apps/lyra_ia`
   (la carpeta `apps/` se comparte con el contenedor):
   ```bash
   git clone <url de este repo> apps/lyra_ia
   ```
3. Instálala en el sitio:
   ```bash
   docker exec -it lyra-erx-bench bash -lc 'cd /home/frappe/frappe-bench \
     && ./env/bin/pip install -e apps/lyra_ia \
     && (grep -qx lyra_ia sites/apps.txt || echo lyra_ia >> sites/apps.txt) \
     && bench --site erp.local install-app lyra_ia \
     && bench build --app lyra_ia'
   docker compose -f docker-compose.local.yml restart bench-cli
   ```
4. Entra como Administrator (la contraseña sale con `bash docker/apps.sh password`), pon tu clave en
   **IA Ajustes**, actívala y toca **Probar conexión**.
5. Abre http://localhost:8000/lyra y haz la entrevista.

Para trabajar: editas en `apps/lyra_ia` desde tu Mac. Los cambios de Python se ven al recargar; si
cambias un doctype (`.json`) corre `bench --site erp.local migrate`, y si cambias el JS o SCSS del
escritorio, `bench build --app lyra_ia`. La página `/lyra` se cachea: `bench --site erp.local clear-website-cache`.

### En otro bench de Frappe

```bash
bench get-app <url de este repo>
bench --site <sitio> install-app lyra_ia
bench --site <sitio> migrate
```

## Cómo quedó (octubre de 2026)

Funciona y está probado en local, con DeepSeek:
- La entrevista al dueño en `/lyra`: conoce primero a la persona, decide cuántas preguntas hacer,
  arma el mapa de la empresa sin repetidos y al final le dice cómo lo va a ayudar.
- El holograma 3D del mapa, el orbe de Lyra, el micrófono y la voz del navegador.
- Lyra se da cuenta: reglas, avisos privados con Deshacer, métricas por área y reporte semanal.
- El Alma, que se llena sola al confirmar la entrevista y cada día.
- El rol Equipo Lyra: el cliente no ve IA Ajustes, el Alma, los costos ni la recomendación de módulos.
- Instalarla sola, en un sitio con solo Frappe y sin ERPNext: se instala, crea sus doctypes y su rol,
  y la entrevista corre con el guion fijo aunque no haya clave de IA.
- La entrevista a los funcionarios: Lyra deduce el cargo, lo confirma, pregunta según el puesto, recibe
  los archivos que le comparten y al final le dice a la persona cómo la va a ayudar. Probado con
  DeepSeek en contabilidad y en Recursos Humanos.
- Quién ve qué: el dueño no ve las entrevistas con nombre ni ningún perfil, solo el consolidado por
  área. El Equipo Lyra, que no es de la empresa, sí ve las entrevistas y los perfiles, pero no puede
  cambiar lo que alguien contó de sí mismo. Cada quien ve lo suyo.
- El organigrama que sale de las entrevistas, para el Equipo Lyra: los cargos, quién le reporta a
  quién y por dónde pasa el trabajo, con la frase que justifica cada flecha.

Hecho, pero sin probar de punta a punta:

Pendiente:
- Una pantalla para que el Equipo Lyra lea el consolidado por área (hoy se consulta por API).
- Una pantalla para que el Equipo Lyra revise la recomendación de módulos y active las apps.
- Los precios del proveedor en IA Ajustes, para ver el costo real de cada entrevista.
- Laya: el clasificador local, para más adelante.

## Configurar

1. **IA Ajustes** (`/app/ia-ajustes`): proveedor, clave y modelo, activar, y **Probar conexión**.
   La clave se guarda cifrada en la base de datos, nunca en el código ni en `site_config`.
   Opcional: los precios del proveedor, para ver costos.
   Para la voz, una sola vez:
   ```bash
   bash scripts/voz-servicio.sh instalar
   ```
   Ese comando hace todo: si no tienes VoiceStudio lo clona e instala, lo deja arrancando solo
   con la máquina y levantándose si se cae, **mete la voz de Lyra** (`voz/marcela.omnivoice`, el
   perfil exportado que viaja con el repo) y, si Lyra corre en Docker aquí, se la deja
   configurada. `estado` y `quitar` para lo demás; `VOICESTUDIO_HOME=/ruta` si ya lo tienes en
   otro sitio.

   La voz **no** va dentro del contenedor de Lyra a propósito: necesita la GPU, y un contenedor
   de Linux no alcanza la GPU de un Mac (lo dice la documentación de VoiceStudio). En un servidor
   Linux con GPU, el mismo script instala el servicio con systemd. Después, en IA Ajustes: la
   dirección `http://host.docker.internal:3900` —dentro del contenedor «localhost» es el
   contenedor, no tu máquina—, **Ver voces**, eliges la tuya y **Probar voz**.
2. El rol **Equipo Lyra** ve IA Ajustes, el Alma, IA Registro, el organigrama y la recomendación de
   módulos del diagnóstico. El cliente, aunque sea System Manager, no los ve. Administrator lo tiene siempre; a
   otra persona del equipo se le asigna en su usuario.
3. La entrevista se abre en `/lyra`. A un System Manager le toca la de su empresa; a cualquier otra
   persona, la de su trabajo. Con `/lyra?modo=trabajo` el dueño también cuenta cómo trabaja él.


## Reglas de diseño

- Lyra entrevista a cualquier persona igual: primero la conoce y después habla de la empresa o del
  trabajo. No hay un número fijo de preguntas: Lyra decide.
- Con el dueño, además, acuerdan cómo se van a ayudar, y al final ella le dice cómo lo va a ayudar.
  **Con un funcionario, Lyra solo entrevista**: no le ofrece ayuda, no le promete nada y no le habla
  de lo que ella hará. Al final solo le devuelve lo que entendió, para que lo corrija.
- La IA nunca decide qué se recomienda ni escribe el Alma: eso sale de reglas y datos reales. La IA
  solo redacta.
- Al dueño se le dice cómo lo va a ayudar Lyra, sin módulos ni nada que aprobar. Qué se activa lo
  decide el Equipo Lyra.
- Métricas por área, nunca por persona; un área con menos de 3 personas no se muestra.
- Todo lo que Lyra cambia sola se puede deshacer y queda en el historial del documento.

## Gotchas de Frappe

- Los endpoints que crean registros van por POST: Frappe descarta lo que se guarda en un GET.
- Las páginas de `www/` no pueden contener `.__` en ningún lado (Frappe rechaza la plantilla).
- Un Single no toma los `default` de sus campos hasta que se guarda: `setup.despues_de_migrar` los llena.
- Un módulo nuevo necesita su Module Def antes de sincronizar: patch en `pre_model_sync`.

## Créditos

- Orbe de Lyra: [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs) de Jakub Antalik
  (MIT), en `lyra_ia/public/js/vendor/thinking-orbs/`.
