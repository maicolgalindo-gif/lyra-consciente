# Antes de tocar Lyra

Esto no es documentación del código: el README cuenta qué hace Lyra y el código
está comentado. Esto es lo que **no se deduce leyendo**, y que si se rompe no se
nota hasta que ya pasó.

Léelo antes del primer cambio.

## Hacia dónde va

`PLAN.md` tiene el plan completo en cuatro fases, con las palabras del dueño del
producto. Si vas a construir algo nuevo, mira ahí en qué fase cae y qué incluye:
varias cosas que suenan a una sola (una «plantilla por sector», por ejemplo) son
en realidad cuatro.

## Las reglas que no se negocian

No son preferencias de estilo. Son decisiones del producto, y varias se tomaron
después de equivocarse.

1. **Lo que una persona cuenta de sí misma no lo ve nadie de su empresa.** Ni el
   dueño, ni Recursos Humanos. Lo ven ella y el Equipo Lyra, que viene de
   afuera. Su perfil se corrige, no se borra desde la app: es el contexto con el
   que Lyra la acompaña.
2. **Las entrevistas de trabajo no llegan al dueño con nombre.** A él le llega
   el consolidado por área, y un área con menos personas que el mínimo (Sense
   Ajustes, 3 por defecto) se junta en «Otras áreas» y pierde su cargo y su paso
   a paso, porque eso diría quién lo contó.
3. **Métricas por área, nunca por persona.** Vale para el reporte semanal, el
   consolidado y el Alma.
4. **La IA no decide ni inventa.** Las cifras y las recomendaciones salen de
   reglas y datos reales; la IA solo redacta. Si una propuesta no se puede atar
   a algo que alguien dijo, no se propone.
5. **Lyra no hace nada sin que una persona diga que sí.** Deja la propuesta con
   el texto exacto y espera. Lo que se puede deshacer, se deshace (`acciones.py`,
   `Lyra Accion`).
6. **Lyra nunca toca montos, cantidades, consentimientos ni nada enviado a la
   DIAN**, y solo completa en borradores (`sense/reglas.py`).
7. **Lyra se da cuenta nunca puede impedir que alguien guarde su trabajo.** Si
   falla, se anota el error y la persona ni se entera (`sense/captura.py`).

## Decisiones que ya se tomaron (no las deshagas sin preguntar)

Estas se ven «mejorables» desde el código porque el código ya no muestra lo que
había antes:

- **El perfil tuvo acceso para Recursos Humanos. Se quitó a propósito.** Hoy no
  está, y no es un olvido.
- **Hubo una pantalla «Mi perfil» con formulario. Se borró.** Lyra conversa, no
  hace llenar casillas. El perfil se recoge hablando, al final de la entrevista
  de trabajo.
- **Las reglas de «Lyra se da cuenta» venían de una lista fija en el código. Se
  sacó.** Ahora se proponen desde lo que la gente contó en su entrevista
  (`sense/propuestas.py`), citando sus palabras. Si nadie contó nada, no se
  propone nada: eso es lo correcto.
- **Las invitaciones las crea solo el Equipo Lyra**, no la empresa ni el dueño.
  Si el dueño pudiera, decidiría a quién se entrevista.
- **Con un funcionario, Lyra solo entrevista**: no le ofrece ayuda ni le promete
  nada. Lo de «así te voy a ayudar» es del dueño.

## Cuidado con el servidor

`lyra.algoritmia.com.co` es la demo **en producción**, en Coolify. Cada push o
merge a `main` **la reinicia y despliega solo** (`.github/workflows/deploy-coolify.yml`
en el monorepo `nexterp-opys`). Trabaja en otra rama; a `main` se pasa cuando una
persona lo decide.

## Gotchas de Frappe que ya mordieron aquí

- Los endpoints que crean algo van por **POST**: Frappe descarta lo que se guarda
  en un GET.
- Las páginas de `www/` **no pueden contener `.__`** en ningún lado.
- Un **Single** no toma los `default` de sus campos hasta que se guarda:
  `setup.despues_de_migrar()` los llena.
- Un **módulo nuevo** necesita su Module Def antes del sync: patch en
  `pre_model_sync`.
- Un **Workspace** no se actualiza si no le cambias el campo `modified` del JSON.
- Un **rol** que un doctype usa en sus permisos tiene que existir antes del sync.
- **Cuidado con los nombres de campo de ERPNext**: el número de factura del
  proveedor es `bill_no`, no `supplier_invoice_no`. Comprueba contra el meta
  antes de escribir una regla.

## Cómo probar sin romper nada

El entorno vive en Docker (repo `nexterp-opys`, `docker-compose.local.yml`),
sitio `erp.local` en el puerto 8000, app instalada en modo editable.

Para correr código con contexto de sitio **no uses `bench console` con heredoc**
(IPython se come el stdin). Escribe el script en `/tmp` dentro del contenedor y
córrelo así:

```sh
docker exec -i lyra-erx-bench bash -lc 'cat > /tmp/x.py' <<'PY'
import frappe
frappe.init(site="erp.local"); frappe.connect()
...
PY
docker exec -i lyra-erx-bench bash -lc 'cd /home/frappe/frappe-bench/sites && ../env/bin/python /tmp/x.py'
```

Dos cosas más:

- `frappe.sessions.get_csrf_token()` revienta fuera de una petición real. Si
  pruebas una página de `www/`, hazlo por HTTP, no con ese arnés.
- **Borra tus datos de prueba.** Los diagnósticos, perfiles, invitaciones y
  usuarios que crees para probar no son del usuario: límpialos al terminar.

## La voz

Corre **fuera** del contenedor (`scripts/voz-servicio.sh`), porque necesita la
GPU y un contenedor de Linux no alcanza la de un Mac. En una máquina normal cada
frase cuesta unos 12 segundos y eso **no se puede bajar desde el código**: ya se
probó con menos pasos, con otro motor, con streaming y liberando memoria.
