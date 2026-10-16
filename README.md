# Lyra IA

Inteligencia artificial de Lyra, para todo el ERP/CRM. Módulo **Lyra IA** en el menú.

- **Cerebro** (`cerebro.py`): llamadas a un modelo de lenguaje con el formato de OpenAI
  (`/chat/completions`), así que sirve DeepSeek, OpenRouter, Together u otro compatible: cambiar de
  proveedor es cambiar URL, clave y modelo en **IA Ajustes**. Cada llamada queda en **IA Registro**
  (quién, para qué, tokens, costo), respeta un límite de gasto mensual y oculta correos, teléfonos,
  documentos y tarjetas antes de enviarlos (`privacidad.py`), devolviéndolos en la respuesta.
- **Asistente** (`asistente.py`, página `asistente-ia`): conversación con la IA, que consulta los
  módulos activos mediante herramientas (`herramientas.py`). Cada app declara las suyas con el hook
  `lyra_ia_herramientas`; solo aparecen las de apps instaladas y que el usuario puede leer, y corren
  como ese usuario (sus permisos). Por ahora solo consultan; las que cambien datos pedirán confirmación.
- **Copiloto en los chats** (`copiloto.py`, `public/js/lyra_ia.bundle.js`): botón «IA» en
  Conversaciones (Meta) y Conversaciones WAHA para resumir, sugerir respuesta (va al cuadro de texto,
  nunca se envía sola) y clasificar.
- **Clasificaciones** (`clasificador.py`): cada módulo declara preguntas con el formato de Laya
  (`choice`, `score`, `noul`) en el hook `lyra_ia_preguntas`. Hoy responde el modelo; cada respuesta y su
  corrección quedan en **IA Clasificacion**, y se exportan en JSONL para entrenar a Laya, que más adelante
  responderá las mismas preguntas en el servidor propio.
