import os
import requests
import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Cargar variables de entorno (para pruebas locales)
load_dotenv()

app = Flask(__name__)

# Configuración de la Base de Datos (Neon)
DATABASE_URL = os.getenv('DATABASE_URL')
# Configuración de Green API
ID_INSTANCE = os.getenv('ID_INSTANCE')
API_TOKEN_INSTANCE = os.getenv('API_TOKEN_INSTANCE')
API_URL = f"https://api.green-api.com/waInstance{ID_INSTANCE}"

def get_db_connection():
    """Establece conexión con la base de datos PostgreSQL de Neon."""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def send_whatsapp_message(chat_id, text):
    """Envía un mensaje de texto vía Green API."""
    url = f"{API_URL}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {
        "chatId": chat_id,
        "message": text
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")
        return False

@app.route('/')
def home():
    return "Servidor del Bot de Cine Activo 🎬", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        
        # 1. VALIDACIÓN: Solo procesamos mensajes de texto entrantes
        # Esto evita errores con notificaciones de conexión o estados
        if data.get('typeWebhook') != 'incomingMessageReceived':
            return "OK", 200

        # 2. EXTRACCIÓN SEGURA DE DATOS (Protección contra 'NoneType')
        message_data = data.get('messageData', {})
        text_message_data = message_data.get('textMessageData', {})
        user_text = text_message_data.get('textMessage')
        
        # Si el mensaje no tiene texto (es una foto o emoji solo), ignoramos
        if user_text is None:
            return "OK", 200

        # Limpiamos el texto
        user_input = user_text.strip().lower()
        sender_id = data.get('senderData', {}).get('sender') # Número del cliente
        
        print(f"📩 Mensaje recibido de {sender_id}: {user_input}")

        # 3. LÓGICA DE MENÚS
        if user_input in ['hola', 'buenos días', 'buenas tardes', 'menu', 'menú', '0']:
            welcome_msg = (
                "🎬 *¡Bienvenido a Cine Club La Fábrica de los Sueños!* 🍿\n\n"
                "Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?\n"
                "Responde con el *número* de la opción:\n\n"
                "1️⃣ *Ver Cartelera y Reservar*\n"
                "2️⃣ *¿Cómo funciona la entrada gratis?*\n"
                "3️⃣ *Ubicación y Horarios*\n"
                "4️⃣ *Hablar con un asesor*"
            )
            send_whatsapp_message(sender_id, welcome_msg)

        elif user_input == '1':
            # Aquí podrías consultar tu tabla 'peliculas' en Neon
            msg = "📽️ *Nuestra Cartelera:* \n1. Película A (Viernes 7pm)\n2. Película B (Sábado 5pm)\n\n_Escribe el número de la película para iniciar la reserva._"
            send_whatsapp_message(sender_id, msg)

        elif user_input == '2':
            msg = "🎟️ *Entradas Gratis:* \nNuestro cine funciona bajo un sistema de membresía pre-pago. Tus entradas son gratuitas al presentar tu código de socio..."
            send_whatsapp_message(sender_id, msg)

        elif user_input == '3':
            msg = "📍 *Ubicación:* Estamos en Plaza Paraíso, Cartago.\n🕒 *Horarios:* Vie-Dom de 4pm a 10pm."
            send_whatsapp_message(sender_id, msg)

        elif user_input == '4':
            msg = "👤 Un asesor humano se comunicará contigo pronto. Por favor espera un momento."
            send_whatsapp_message(sender_id, msg)

        else:
            msg = "⚠️ No entendí esa opción. Escribe *Menú* para ver las opciones disponibles."
            send_whatsapp_message(sender_id, msg)

        return "OK", 200

    except Exception as e:
        print(f"❌ Error crítico en el Webhook: {e}")
        # Retornamos 200 para que Green API no intente reenviar el mensaje fallido infinitamente
        return "Error Interno", 200

if __name__ == '__main__':
    # Render usa el puerto 5000 por defecto para Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)