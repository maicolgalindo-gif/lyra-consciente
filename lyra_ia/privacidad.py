"""Ocultar datos personales antes de enviarlos al modelo, y devolverlos despues.

El modelo ve [CORREO_1], [TELEFONO_1], [DOCUMENTO_1], [TARJETA_1] y Lyra los
cambia otra vez por el dato real en lo que responde. Asi la conversacion sigue
teniendo sentido sin que el proveedor reciba el dato (Ley 1581).

No se ocultan montos, placas ni fechas: sin ellos la IA no entiende el caso.
"""

from __future__ import annotations

import re

PATRONES = [
	("CORREO", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
	("TARJETA", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
	# Cedula / NIT solo con su palabra delante: un numero suelto puede ser un precio.
	("DOCUMENTO", re.compile(r"(?i)\b(?:c\.?\s?c\.?|c[eé]dula|documento|nit|identificaci[oó]n|pasaporte)\s*(?:n[oº°.]*)?\s*[:#]?\s*([\d][\d.\-]{5,14}\d)")),
	("TELEFONO", re.compile(r"(?<![\w])(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")),
]


def ocultar(texto: str, mapa: dict) -> str:
	"""mapa: {"[CORREO_1]": "ana@x.com", ...}; se comparte entre todos los textos de una llamada."""
	if not texto:
		return texto
	inverso = {v: k for k, v in mapa.items()}
	for tipo, patron in PATRONES:
		def cambiar(m, tipo=tipo):
			dato = m.group(1) if m.groups() and m.group(1) else m.group(0)
			if dato not in inverso:
				n = sum(1 for k in mapa if k.startswith(f"[{tipo}_")) + 1
				marca = f"[{tipo}_{n}]"
				mapa[marca] = dato
				inverso[dato] = marca
			return m.group(0).replace(dato, inverso[dato])

		texto = patron.sub(cambiar, texto)
	return texto


def mostrar(texto: str, mapa: dict) -> str:
	for marca, dato in mapa.items():
		texto = (texto or "").replace(marca, dato)
	return texto
