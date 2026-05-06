import database
import generador_qr
import uuid

sesiones = {}

def obtener_sesion(numero_cliente):
    if numero_cliente not in sesiones:
        sesiones[numero_cliente] = {'paso': 'inicio', 'cartelera_id': None, 'nombre': '', 'cantidad': 0}
    return sesiones[numero_cliente]

def procesar_mensaje(numero_cliente, mensaje_entrante):
    mensaje = mensaje_entrante.strip().lower()
    sesion = obtener_sesion(numero_cliente)
    paso_actual = sesion['paso']

    if mensaje in ['salir', 'cancelar', 'menu', 'menú', 'hola']:
        sesion['paso'] = 'inicio'
        paso_actual = 'inicio'

    # =========================================================
    # EL SISTEMA DE RECEPCIÓN (Escaner de Entradas)
    # =========================================================
    if mensaje.startswith('validar '):
        partes = mensaje.split(" ")
        if len(partes) >= 2:
            codigo_a_validar = partes[1].upper()
            exito, resultado = database.marcar_asistencia(codigo_a_validar)
            
            if exito:
                msj_pantalla, tel_cliente, nom_cliente = resultado
                print(f"\n📲 [MENSAJE AUTOMÁTICO ENVIADO A {tel_cliente}]:")
                print(f"¡Hola {nom_cliente}! Gracias por confirmar tu asistencia. Te esperamos en la dulcería. ¡Disfruta la función! 🍿🎬\n")
                return msj_pantalla, None
            else:
                return resultado, None
        else:
            return "❌ Formato incorrecto. Debes escribir: validar CODIGO", None

    # =========================================================
    # EL CÓDIGO SECRETO (La llave maestra)
    # =========================================================
    if mensaje == 'secreto123':
        sesion['paso'] = 'menu_admin'
        respuesta = (
            "🔐 *MENÚ SECRETO DE ADMINISTRADOR* 🔐\n"
            "Elige una opción:\n\n"
            "1️⃣ Ingreso de nueva película\n"
            "2️⃣ Eliminar (Ocultar) película\n"
            "3️⃣ Cambiar número de asesor\n"
            "11️⃣ Recargar saldo de reservas\n"
            "*(Escribe 'salir' en cualquier momento para cerrar el menú)*"
        )
        return respuesta, None

    if paso_actual.startswith('admin_'):
        if paso_actual == 'admin_esperando_opcion':
            if mensaje == '11':
                sesion['paso'] = 'admin_recargando'
                return "💰 ¿Cuántas reservas deseas recargar?:", None
            elif mensaje == '3':
                sesion['paso'] = 'admin_cambiando_asesor'
                return "📱 Escribe el nuevo número telefónico del asesor:", None
            elif mensaje == '2':
                peliculas = database.obtener_cartelera_activa()
                if not peliculas: return "No hay películas activas para eliminar.", None
                resp = "🗑️ ¿Qué película quieres eliminar? Escribe su ID:\n\n"
                for p in peliculas: resp += f"ID: *{p[0]}* - {p[1]}\n"
                sesion['paso'] = 'admin_eliminando_peli'
                return resp, None
            elif mensaje == '1':
                sesion['paso'] = 'admin_agregando_peli_nombre'
                return "🎬 Escribe el *Nombre de la Película*:", None
            else:
                return "❌ Opción de admin no válida o en construcción.", None

        elif paso_actual == 'admin_recargando':
            if database.admin_recargar_saldo(int(mensaje)):
                sesion['paso'] = 'inicio'
                return f"✅ ¡Exito! Se sumaron {mensaje} reservas.", None
            return "❌ Error.", None
        elif paso_actual == 'admin_cambiando_asesor':
            if database.admin_cambiar_asesor(mensaje):
                sesion['paso'] = 'inicio'
                return f"✅ Asesor actualizado a: {mensaje}", None
            return "❌ Error.", None
        elif paso_actual == 'admin_eliminando_peli':
            if database.admin_eliminar_pelicula(int(mensaje)):
                sesion['paso'] = 'inicio'
                return "✅ Película eliminada.", None
            return "❌ Error.", None
        elif paso_actual == 'admin_agregando_peli_nombre':
            sesion['temp_nombre_peli'] = mensaje_entrante.strip()
            sesion['paso'] = 'admin_agregando_peli_dia'
            return "📅 ¿Qué día será la función? (Ej: Sábado):", None
        elif paso_actual == 'admin_agregando_peli_dia':
            sesion['temp_dia_peli'] = mensaje_entrante.strip()
            sesion['paso'] = 'admin_agregando_peli_hora'
            return "⏰ ¿A qué hora? (Ej: 7:00 PM):", None
        elif paso_actual == 'admin_agregando_peli_hora':
            sesion['temp_hora_peli'] = mensaje_entrante.strip()
            sesion['paso'] = 'admin_agregando_peli_cupos'
            return "🎟️ ¿Cuántos cupos tendrá la sala?:", None
        elif paso_actual == 'admin_agregando_peli_cupos':
            if database.admin_agregar_pelicula(sesion['temp_nombre_peli'], sesion['temp_dia_peli'], sesion['temp_hora_peli'], int(mensaje)):
                sesion['paso'] = 'inicio'
                return f"✅ ¡Película '{sesion['temp_nombre_peli']}' agregada!", None
            return "❌ Error.", None

    if paso_actual == 'menu_admin':
        sesion['paso'] = 'admin_esperando_opcion'
        return "*(Modo admin activado)*", None

    # =========================================================
    # LÓGICA NORMAL (CLIENTES)
    # =========================================================
    if paso_actual == 'inicio':
        respuesta = (
            "🎬 *¡Bienvenido a Cine Fábrica de Sonrisas!* 🍿\n"
            "Por favor, responde con el *número* de la opción:\n\n"
            "1️⃣ Reservar espacios\n"
            "2️⃣ ¿Cómo funciona la entrada gratis?\n"
            "3️⃣ Ubicación del cine\n"
            "4️⃣ Hablar con un asesor"
        )
        sesion['paso'] = 'esperando_opcion_menu'
        return respuesta, None

    elif paso_actual == 'esperando_opcion_menu':
        if mensaje == '1':
            # 🛡️ VERIFICACIÓN DE SEGURIDAD (EL ESCUDO)
            esta_bloqueado, msj_bloqueo = database.verificar_bloqueo(numero_cliente)
            if esta_bloqueado:
                sesion['paso'] = 'inicio' # Lo devolvemos al inicio para que no avance
                return f"🚫 *ACCESO RESTRINGIDO*\n\n{msj_bloqueo}", None

            peliculas = database.obtener_cartelera_activa()
            if not peliculas: return "No hay películas disponibles en este momento. 🚧", None
            respuesta = "🎞️ *Cartelera Actual* 🎞️\nResponde con el *número* de la película:\n\n"
            for p in peliculas: respuesta += f"*{p[0]}* - {p[1]} ({p[2]} a las {p[3]}) - Libres: {p[4]}\n"
            sesion['paso'] = 'esperando_seleccion_pelicula'
            return respuesta, None

        elif mensaje == '2': return "🎟️ QR en entrada = Gratis.", None
        elif mensaje == '3': return "📍 Plaza Paraíso, Cartago.", None
        elif mensaje == '4': return "🗣️ Un asesor te escribirá.", None
        else: return "❌ Opción no válida (1-4).", None

    elif paso_actual == 'esperando_seleccion_pelicula':
        if not mensaje.isdigit(): return "❌ Solo el número.", None
        sesion['cartelera_id'] = int(mensaje)
        sesion['paso'] = 'esperando_nombre'
        return "📝 Escribe tu *Nombre Completo*:", None

    elif paso_actual == 'esperando_nombre':
        sesion['nombre'] = mensaje_entrante.strip()
        sesion['paso'] = 'esperando_cantidad'
        return f"¿Cuántas personas asistirán en total {sesion['nombre']}?", None

    elif paso_actual == 'esperando_cantidad':
        if not mensaje.isdigit() or int(mensaje) <= 0: return "❌ Número inválido.", None
        cantidad = int(mensaje)
        cliente_id = database.registrar_o_buscar_cliente(numero_cliente, sesion['nombre'])
        codigo_unico = str(uuid.uuid4())[:8].upper()
        
        exito, msj_db, alerta = database.procesar_reserva(cliente_id, sesion['cartelera_id'], cantidad, codigo_unico)
        if not exito:
            sesion['paso'] = 'inicio' 
            return msj_db, None 
            
        info_reserva = f"COD:{codigo_unico}|CLI:{cliente_id}|CANT:{cantidad}"
        nombre_qr = f"reserva_{codigo_unico}"
        ruta_imagen_qr = generador_qr.crear_qr(info_reserva, nombre_qr)
        
        sesion['paso'] = 'inicio'
        respuesta_final = (
            f"✅ *¡Reserva Confirmada!*\n\n"
            f"👤 {sesion['nombre']}\n"
            f"🎟️ {cantidad} personas\n"
            f"🔐 Código: {codigo_unico}\n\n"
            f"Presenta este QR en la recepción."
        )
        return respuesta_final, ruta_imagen_qr

    return "❌ No entendí. Escribe *salir* para reiniciar.", None

if __name__ == "__main__":
    mi_numero = "50688888888" 
    while True:
        texto_usuario = input("👤 Tú: ")
        if texto_usuario.lower() == 'salir_bot': break
        respuesta_texto, ruta_imagen = procesar_mensaje(mi_numero, texto_usuario)
        print(f"\n🤖 Bot:\n{respuesta_texto}")