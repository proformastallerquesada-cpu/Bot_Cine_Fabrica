import os
import requests
import uuid
import qrcode
import tempfile
import pandas as pd
from flask import Flask, request, jsonify
import database 

app = Flask(__name__)

ID_INSTANCE = os.getenv('ID_INSTANCE')
API_TOKEN_INSTANCE = os.getenv('API_TOKEN_INSTANCE')
API_URL = f"https://api.green-api.com/waInstance{ID_INSTANCE}"

# ⚠️ MUY IMPORTANTE: Cambia este número por el número REAL de WhatsApp del bot.
# Debe tener el código de país sin signos, ej: "50688888888"
NUMERO_DEL_BOT = "50688888888" 

sesiones = {}

def obtener_sesion(numero_cliente):
    if numero_cliente not in sesiones:
        sesiones[numero_cliente] = {'paso': 'inicio', 'cartelera_id': None, 'nombre': '', 'cantidad': 0, 'admin_temp': {}}
    return sesiones[numero_cliente]

def enviar_texto(chat_id, texto):
    url = f"{API_URL}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {"chatId": chat_id, "message": texto}
    requests.post(url, json=payload)

def enviar_qr(chat_id, texto_qr, nombre_archivo, codigo_corto):
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(texto_qr) # texto_qr ahora es un enlace web inteligente
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        path = os.path.join(tempfile.gettempdir(), f"{nombre_archivo}.png")
        img.save(path)
        url = f"{API_URL}/sendFileByUpload/{API_TOKEN_INSTANCE}"
        with open(path, 'rb') as f:
            files = {'file': (f"{nombre_archivo}.png", f, 'image/png')}
            payload = {'chatId': chat_id, 'caption': "🎟️ *Aquí tienes tu entrada inteligente*"}
            requests.post(url, data=payload, files=files)
    except:
        enviar_texto(chat_id, f"⚠️ Tu código de entrada oficial es: *{codigo_corto}*")

def enviar_boton_validacion(chat_id, codigo):
    url = f"{API_URL}/sendButtons/{API_TOKEN_INSTANCE}"
    payload = {
        "chatId": chat_id,
        "message": f"🎫 Tu código es: *{codigo}*\n\n_(Si estás en recepción, pídele al encargado que presione el botón de abajo para validar tu entrada)_ 👇",
        "footer": "Sistema de Reservas",
        "buttons": [
            {"buttonId": f"validar {codigo}", "buttonText": "✅ Validar Entrada", "type": 1}
        ]
    }
    res = requests.post(url, json=payload)
    if res.status_code != 200:
        enviar_texto(chat_id, f"🎫 Código: *{codigo}*\n_(Para validar en recepción, el encargado debe responder a este mensaje con: *validar {codigo}*)_")

def enviar_excel(chat_id, columnas, datos, nombre_archivo, caption):
    try:
        df = pd.DataFrame(datos, columns=columnas)
        ruta = os.path.join(tempfile.gettempdir(), f"{nombre_archivo}.xlsx")
        
        with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
            # Dividir en pestañas por película si existe la columna
            if 'Película' in df.columns:
                for pelicula, grupo in df.groupby('Película'):
                    nombre_hoja = str(pelicula)[:31].replace('/', '').replace('\\', '')
                    grupo.to_excel(writer, sheet_name=nombre_hoja, index=False)
            else:
                df.to_excel(writer, index=False)
            
            # MAGIA: Auto-ajuste del ancho de todas las columnas en todas las hojas
            for sheetname in writer.sheets:
                worksheet = writer.sheets[sheetname]
                for col in worksheet.columns:
                    max_length = 0
                    column_letter = col[0].column_letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        url = f"{API_URL}/sendFileByUpload/{API_TOKEN_INSTANCE}"
        with open(ruta, 'rb') as f:
            files = {'file': (f"{nombre_archivo}.xlsx", f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            payload = {'chatId': chat_id, 'caption': caption}
            requests.post(url, data=payload, files=files)
    except Exception as e:
        print(f"Error generando Excel: {e}")
        enviar_texto(chat_id, "❌ Error técnico al generar el archivo Excel.")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if data.get('typeWebhook') != 'incomingMessageReceived': return "OK", 200
        
        msg_data = data.get('messageData', {})
        mensaje_original = ""
        if 'textMessageData' in msg_data:
            mensaje_original = msg_data['textMessageData'].get('textMessage', '')
        elif 'buttonMessageData' in msg_data: 
            mensaje_original = msg_data['buttonMessageData'].get('buttonId', '')
        elif 'extendedTextMessageData' in msg_data: 
            mensaje_original = msg_data['extendedTextMessageData'].get('text', '')
            
        if not mensaje_original: return "OK", 200
        
        mensaje = mensaje_original.strip().lower()
        sender_id = data.get('senderData', {}).get('sender')
        sesion = obtener_sesion(sender_id)

        if mensaje in ['hola', 'menu', 'salir', '0']:
            sesion['paso'] = 'inicio'
        elif mensaje == 'secreto123':
            sesion['paso'] = 'admin_menu'

        paso = sesion['paso']

        # 1. RECEPCIÓN Y ESCANER
        if mensaje.startswith('validar '):
            codigo = mensaje.replace('validar ', '').strip().upper()
            exito, res = database.marcar_asistencia(codigo)
            
            if exito:
                msj_rec, tel_cli, nom_cli = res
                enviar_texto(sender_id, msj_rec)
                msj_agradecimiento = f"🎬 ¡Gracias {nom_cli}! Esperamos que disfrutes la función. ¡Te esperamos la próxima vez!"
                enviar_texto(tel_cli, msj_agradecimiento)
            else: 
                enviar_texto(sender_id, res)
            return "OK", 200

        # 2. MODO ADMINISTRADOR COMPLETO
        if paso == 'admin_menu':
            menu = (
                "🔐 *MODO ADMINISTRADOR*\n\n"
                "1️⃣ Agregar Película\n2️⃣ Eliminar Película\n3️⃣ Cambiar Asesor\n"
                "4️⃣ Programar Reporte Reservas\n5️⃣ Enviar Excel Reservas\n"
                "6️⃣ Programar Reporte Utilizadas\n7️⃣ Enviar Excel Utilizadas\n"
                "8️⃣ Configurar Bloqueo\n9️⃣ Programar Reporte Ausentes\n"
                "🔟 Enviar Excel Ausentes\n11️⃣ Recargar Saldo\n12️⃣ Exportar DB\n"
                "13️⃣ Reenviar Saldo a Asesor\n\n"
                "*(Escribe 'salir' para volver)*"
            )
            enviar_texto(sender_id, menu)
            sesion['paso'] = 'admin_esperando_opcion'

        elif paso == 'admin_esperando_opcion':
            if mensaje == '1':
                sesion['paso'] = 'admin_peli_nombre'
                enviar_texto(sender_id, "🎬 Escribe el *Nombre* de la función/película:")
            elif mensaje == '2':
                peli_list = database.obtener_cartelera_activa()
                if not peli_list:
                    enviar_texto(sender_id, "No hay funciones para eliminar.")
                    sesion['paso'] = 'admin_menu'
                else:
                    resp = "🗑️ *ELIMINAR FUNCIÓN*\nEscribe el *ID* (número inicial):\n\n"
                    for p in peli_list:
                        resp += f"ID: *{p[0]}* - {p[1]}\n"
                    enviar_texto(sender_id, resp)
                    sesion['paso'] = 'admin_peli_eliminar'
            elif mensaje == '3':
                enviar_texto(sender_id, "📞 Escribe el número del asesor (Formato: 50688888888):")
                sesion['paso'] = 'admin_cambiar_asesor'
            elif mensaje in ['4', '6', '9']:
                sesion['admin_temp']['tipo_repo'] = {'4':'reservas', '6':'utilizadas', '9':'ausentes'}[mensaje]
                enviar_texto(sender_id, "Día de la semana (Lunes, Martes...):")
                sesion['paso'] = 'admin_repo_dia'
            
            elif mensaje in ['5', '7', '10']:
                tipo = {'5':'reservas', '7':'utilizadas', '10':'ausentes'}[mensaje]
                columnas, datos = database.admin_obtener_datos_reporte(tipo)
                _, asesor = database.obtener_configuracion()
                chat_id_asesor = f"{asesor}@c.us" if asesor else sender_id
                
                if not datos:
                    enviar_texto(sender_id, f"⚠️ No hay datos registrados para el reporte de {tipo}.")
                else:
                    enviar_texto(sender_id, "⏳ Construyendo archivo Excel (Celdas ajustadas automáticamente)...")
                    enviar_excel(chat_id_asesor, columnas, datos, f"Reporte_{tipo}", f"📊 *Reporte automático de {tipo.capitalize()}*")
                    if chat_id_asesor != sender_id:
                        enviar_texto(sender_id, f"✅ Excel generado y enviado exitosamente al Asesor ({asesor}).")
                sesion['paso'] = 'admin_menu'

            elif mensaje == '11':
                saldo, _ = database.obtener_configuracion()
                enviar_texto(sender_id, f"💰 Tienes *{saldo}* reservas actuales.\n¿Cuántas deseas agregar al sistema? (ej: 1000, 2000):")
                sesion['paso'] = 'admin_recargando'
            elif mensaje == '12':
                enviar_texto(sender_id, "⚠️ Opción en mantenimiento.")
                sesion['paso'] = 'admin_menu'
            elif mensaje == '13':
                saldo, asesor = database.obtener_configuracion()
                if asesor:
                    enviar_texto(f"{asesor}@c.us", f"💳 *REPORTE DE CRÉDITOS*\nEl sistema cuenta actualmente con *{saldo} reservas* disponibles.")
                    enviar_texto(sender_id, f"✅ Saldo enviado al asesor ({asesor}).")
                else:
                    enviar_texto(sender_id, f"💳 El sistema tiene *{saldo}* reservas, pero no hay un número de asesor configurado.")
                sesion['paso'] = 'admin_menu'

        # --- FLUJOS ADMIN ---
        elif paso == 'admin_peli_nombre':
            sesion['admin_temp']['n'] = mensaje_original
            enviar_texto(sender_id, "🗓️ Día de función:")
            sesion['paso'] = 'admin_peli_dia'
        elif paso == 'admin_peli_dia':
            sesion['admin_temp']['d'] = mensaje_original
            enviar_texto(sender_id, "⏰ Hora de función:")
            sesion['paso'] = 'admin_peli_hora'
        elif paso == 'admin_peli_hora':
            sesion['admin_temp']['h'] = mensaje_original
            enviar_texto(sender_id, "🎟️ Cantidad de Cupos:")
            sesion['paso'] = 'admin_peli_cupos'
        elif paso == 'admin_peli_cupos':
            database.admin_agregar_pelicula(sesion['admin_temp']['n'], sesion['admin_temp']['d'], sesion['admin_temp']['h'], int(mensaje))
            enviar_texto(sender_id, "✅ Función agregada con éxito.")
            sesion['paso'] = 'admin_menu'

        elif paso == 'admin_peli_eliminar':
            if database.admin_eliminar_pelicula(int(mensaje)):
                enviar_texto(sender_id, "✅ Función eliminada.")
            else: enviar_texto(sender_id, "❌ ID no válido.")
            sesion['paso'] = 'admin_menu'

        elif paso == 'admin_cambiar_asesor':
            database.admin_cambiar_asesor(mensaje)
            enviar_texto(sender_id, "✅ Número de asesor actualizado.")
            sesion['paso'] = 'admin_menu'

        elif paso == 'admin_recargando':
            database.admin_recargar_saldo(int(mensaje))
            enviar_texto(sender_id, "✅ Saldo de reservas actualizado correctamente.")
            sesion['paso'] = 'admin_menu'

        # ==========================================
        # 3. FLUJO CLIENTES 
        # ==========================================
        elif paso == 'inicio':
            menu_vip = (
                "🎬 *Bienvenido al Sistema de Reservas* 🍿\n"
                "Soy tu asistente virtual. Elige una opción:\n\n"
                "1️⃣ Reservar entradas\n"
                "2️⃣ ¿Cómo funciona?\n"
                "3️⃣ Ubicación\n"
                "4️⃣ Hablar con atención al cliente"
            )
            enviar_texto(sender_id, menu_vip)
            sesion['paso'] = 'esperando_menu'

        elif paso == 'esperando_menu':
            if mensaje == '1':
                bloq, msj = database.verificar_bloqueo(sender_id)
                if bloq: enviar_texto(sender_id, msj); sesion['paso'] = 'inicio'
                else:
                    pelis = database.obtener_cartelera_activa()
                    if not pelis: enviar_texto(sender_id, "🚧 No hay funciones programadas hoy.")
                    else:
                        r = "🎞️ *Funciones Disponibles*\nEscribe el número de la opción:\n\n"
                        for p in pelis:
                            r += f"*{p[0]}* - {p[1]} ({p[2]} {p[3]})\n"
                        enviar_texto(sender_id, r); sesion['paso'] = 'eligiendo_peli'
            elif mensaje == '2': 
                enviar_texto(sender_id, "🎟️ Las entradas se reservan por este medio. Al finalizar se te brindará un código QR que debes presentar en puerta.")
            elif mensaje == '3': 
                # SE DEVOLVIERON LAS UBICACIONES EXACTAS DE MAPS Y WAZE
                ubicacion = (
                    "📍 *Ubicación:* Plaza Paraíso, Cartago.\n"
                    "🕒 *Horarios:* Viernes a Domingo 4pm a 10pm.\n\n"
                    "🚗 *Waze:*\nhttps://waze.com/ul?q=Plaza+Paraiso+Cartago\n\n"
                    "🗺️ *Google Maps:*\nhttps://maps.google.com/?q=Plaza+Paraiso+Cartago"
                )
                enviar_texto(sender_id, ubicacion)
            elif mensaje == '4': 
                # AQUÍ OCURRE LA MAGIA DEL ENLACE AL ASESOR
                _, asesor = database.obtener_configuracion()
                if asesor:
                    enviar_texto(sender_id, f"👤 Haz clic en el siguiente enlace para chatear directamente con nuestro asesor humano:\n👉 https://wa.me/{asesor}")
                else:
                    enviar_texto(sender_id, "⚠️ En este momento no hay un número de asesor configurado en el sistema.")

        elif paso == 'eligiendo_peli':
            sesion['cartelera_id'] = int(mensaje)
            enviar_texto(sender_id, "📝 Escribe tu *Nombre Completo* para la reserva:")
            sesion['paso'] = 'pidiendo_nombre'
        elif paso == 'pidiendo_nombre':
            sesion['nombre'] = mensaje_original
            enviar_texto(sender_id, "¿Para cuántas personas es la reserva? (Solo el número)")
            sesion['paso'] = 'pidiendo_cantidad'
            
        elif paso == 'pidiendo_cantidad':
            cant = int(mensaje)
            cod = str(uuid.uuid4())[:8].upper()
            cli_id = database.registrar_o_buscar_cliente(sender_id, sesion['nombre'])
            exito, msj, alert = database.procesar_reserva(cli_id, sesion['cartelera_id'], cant, cod)
            
            if exito:
                # Buscamos los datos exactos
                p_nombre, p_dia, p_hora = database.obtener_detalles_pelicula(sesion['cartelera_id'])
                
                tiquete_vip = (
                    f"✅ *¡RESERVA CONFIRMADA!*\n\n"
                    f"👤 *A nombre de:* {sesion['nombre']}\n"
                    f"🎟️ *Personas:* {cant}\n"
                    f"🎬 *Evento:* {p_nombre}\n"
                    f"🗓️ *Fecha:* {p_dia}\n"
                    f"⏰ *Hora:* {p_hora}\n"
                    f"🔐 *Código Interno:* {cod}"
                )
                enviar_texto(sender_id, tiquete_vip)
                
                # --- MAGIA DEL QR DIRECCIONADO A WHATSAPP ---
                enlace_whatsapp = f"https://wa.me/{NUMERO_DEL_BOT}?text=validar%20{cod}"
                enviar_qr(sender_id, enlace_whatsapp, f"t_{cod}", cod)
                
                # Enviamos el Botón Interactivo de validación rápida
                enviar_boton_validacion(sender_id, cod)
                
                if alert:
                    _, asesor = database.obtener_configuracion()
                    if asesor:
                        enviar_texto(f"{asesor}@c.us", "⚠️ *ALERTA DEL SISTEMA:* El saldo de reservas ha caído a un nivel crítico. Por favor recarga pronto.")
            else: enviar_texto(sender_id, f"❌ Error: {msj}")
            sesion['paso'] = 'inicio'

        return "OK", 200
    except Exception as e:
        print(f"Error global: {e}")
        return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
