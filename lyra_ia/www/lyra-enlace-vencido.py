"""La página que ve alguien cuyo enlace ya no sirve.

Sin esto, un enlace vencido mandaba a la pantalla de login, que es justo lo que
el enlace existe para evitar: la persona no tiene contraseña y se queda sin
saber qué pasó."""

no_cache = 1


def get_context(context):
	context.no_breadcrumbs = True
	return context
