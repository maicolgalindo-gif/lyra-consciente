"""Las herramientas que el asistente puede usar, segun los modulos activos.

Cada app de Lyra declara las suyas con el hook lyra_ia_herramientas: una
funcion que devuelve una lista de herramientas. Cada herramienta:

	{
		"nombre": "cartera_vencida",
		"modulo": "Ventas",
		"descripcion": "...",                      # el modelo la lee para decidir
		"parametros": {...},                       # JSON Schema de los argumentos
		"funcion": callable,                       # recibe los argumentos, devuelve algo serializable
		"disponible": callable -> bool,            # app instalada y permiso del usuario
	}

El modelo solo ve las disponibles para quien pregunta. Y todas corren como
ese usuario, con sus permisos: la IA no puede ver mas que el.

Por ahora todas son de consulta. Las que cambien datos (fase 3) devolveran
una propuesta que el usuario aprueba; nunca se ejecutaran solas.
"""

from __future__ import annotations

import json

import frappe

MAX_RESULTADO = 7000  # caracteres que vuelven al modelo por herramienta


def todas() -> list[dict]:
	salida = []
	for ruta in frappe.get_hooks("lyra_ia_herramientas"):
		try:
			salida.extend(frappe.get_attr(ruta)() or [])
		except Exception:
			frappe.log_error(title=f"Lyra IA: herramientas de {ruta}")
	return salida


def disponibles() -> list[dict]:
	lista = []
	for h in todas():
		try:
			if h.get("disponible", lambda: True)():
				lista.append(h)
		except Exception:
			continue
	return lista


def para_el_modelo(lista: list[dict]) -> list[dict]:
	return [{"type": "function", "function": {"name": h["nombre"], "description": h["descripcion"],
											  "parameters": h.get("parametros") or {"type": "object", "properties": {}}}}
			for h in lista]


def ejecutar(lista: list[dict], nombre: str, argumentos: dict) -> str:
	"""Corre una herramienta y devuelve el resultado como texto para el modelo."""
	h = next((x for x in lista if x["nombre"] == nombre), None)
	if not h:
		return json.dumps({"error": f"La herramienta {nombre} no está disponible para este usuario."}, ensure_ascii=False)
	try:
		resultado = h["funcion"](**(argumentos or {}))
	except frappe.PermissionError:
		resultado = {"error": "El usuario no tiene permiso para ver esto."}
	except TypeError as e:
		resultado = {"error": f"Argumentos no válidos: {e}"}
	except frappe.ValidationError as e:
		resultado = {"error": str(e)}
	texto = json.dumps(resultado, ensure_ascii=False, default=str)
	if len(texto) > MAX_RESULTADO:
		texto = texto[:MAX_RESULTADO] + "… (recortado)"
	return texto
