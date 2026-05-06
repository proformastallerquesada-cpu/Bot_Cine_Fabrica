import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def conectar_bd():
    try:
        conexion = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        return conexion
    except Exception as e:
        print(f"❌ Error al conectar a la base de datos: {e}")
        return None

def obtener_cartelera_activa():
    conexion = conectar_bd()
    if not conexion: return []
    try:
        cursor = conexion.cursor()
        consulta = "SELECT id, pelicula, dia_funcion, hora_funcion, cupo_disponible FROM cartelera WHERE activa = TRUE AND cupo_disponible > 0 ORDER BY id ASC;"
        cursor.execute(consulta)
        peliculas = cursor.fetchall()
        conexion.close()
        return peliculas
    except Exception as e:
        return []

def registrar_o_buscar_cliente(telefono, nombre=""):
    conexion = conectar_bd()
    if not conexion: return None
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM clientes WHERE telefono = %s;", (telefono,))
        cliente = cursor.fetchone()
        if cliente:
            cliente_id = cliente[0]
            if nombre:
                cursor.execute("UPDATE clientes SET nombre = %s WHERE id = %s;", (nombre, cliente_id))
        else:
            cursor.execute("INSERT INTO clientes (telefono, nombre) VALUES (%s, %s) RETURNING id;", (telefono, nombre))
            cliente_id = cursor.fetchone()[0]
        conexion.commit()
        conexion.close()
        return cliente_id
    except Exception as e:
        return None

def procesar_reserva(cliente_id, cartelera_id, cantidad, codigo_qr):
    conexion = conectar_bd()
    if not conexion: return False, "Error de conexión", False
    
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT saldo_reservas FROM configuracion WHERE id = 1;")
        saldo = cursor.fetchone()[0]
        
        if saldo < cantidad:
            return False, "❌ El sistema está en mantenimiento (Código: Saldo Administrador). Contacte soporte.", False
            
        cursor.execute("SELECT cupo_disponible FROM cartelera WHERE id = %s;", (cartelera_id,))
        cupos = cursor.fetchone()[0]
        
        if cupos < cantidad:
            return False, f"❌ Lo sentimos, solo quedan {cupos} espacios disponibles para esta función.", False
            
        nuevo_saldo = saldo - cantidad
        cursor.execute("UPDATE configuracion SET saldo_reservas = %s WHERE id = 1;", (nuevo_saldo,))
        cursor.execute("UPDATE cartelera SET cupo_disponible = cupo_disponible - %s WHERE id = %s;", (cantidad, cartelera_id))
        
        cursor.execute(
            "INSERT INTO reservas (cliente_id, cartelera_id, cantidad_personas, codigo_qr) VALUES (%s, %s, %s, %s);",
            (cliente_id, cartelera_id, cantidad, codigo_qr)
        )
        
        conexion.commit()
        conexion.close()
        
        alerta_asesor = nuevo_saldo in [500, 200, 100]
        return True, "Reserva procesada", alerta_asesor
        
    except Exception as e:
        print(f"❌ Error en base de datos al reservar: {e}")
        return False, "Ocurrió un error interno al procesar su reserva.", False

# ==========================================
# NUEVAS FUNCIONES: MODO ADMINISTRADOR
# ==========================================
def admin_recargar_saldo(cantidad):
    conexion = conectar_bd()
    if not conexion: return False
    try:
        cursor = conexion.cursor()
        cursor.execute("UPDATE configuracion SET saldo_reservas = saldo_reservas + %s WHERE id = 1;", (cantidad,))
        conexion.commit()
        conexion.close()
        return True
    except: return False

def admin_cambiar_asesor(numero):
    conexion = conectar_bd()
    if not conexion: return False
    try:
        cursor = conexion.cursor()
        cursor.execute("UPDATE configuracion SET numeros_asesor = %s WHERE id = 1;", (numero,))
        conexion.commit()
        conexion.close()
        return True
    except: return False

def admin_agregar_pelicula(nombre, dia, hora, cupos):
    conexion = conectar_bd()
    if not conexion: return False
    try:
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO cartelera (pelicula, dia_funcion, hora_funcion, cupo_total, cupo_disponible, activa) VALUES (%s, %s, %s, %s, %s, TRUE);",
            (nombre, dia, hora, cupos, cupos)
        )
        conexion.commit()
        conexion.close()
        return True
    except: return False

def admin_eliminar_pelicula(pelicula_id):
    conexion = conectar_bd()
    if not conexion: return False
    try:
        cursor = conexion.cursor()
        # En lugar de borrarla de la base de datos (para no dañar el historial), solo la "desactivamos"
        cursor.execute("UPDATE cartelera SET activa = FALSE WHERE id = %s;", (pelicula_id,))
        conexion.commit()
        conexion.close()
        return True
    except: return False


    # ==========================================
# NUEVA FUNCIÓN: RECEPCIÓN Y ASISTENCIA
# ==========================================
def marcar_asistencia(codigo_unico):
    """Busca el código de la reserva y marca que el cliente sí llegó al cine."""
    conexion = conectar_bd()
    if not conexion: return False, "Error de conexión."
    
    try:
        cursor = conexion.cursor()
        
        # 1. Buscamos si la reserva existe
        cursor.execute("""
            SELECT r.id, r.estado, r.cantidad_personas, c.nombre, c.telefono, r.cliente_id
            FROM reservas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.codigo_qr = %s;
        """, (codigo_unico,))
        
        reserva = cursor.fetchone()
        
        # 2. Verificamos los posibles errores
        if not reserva:
            return False, "❌ CÓDIGO NO ENCONTRADO. Esta entrada no existe o es falsa."
            
        reserva_id = reserva[0]
        estado_actual = reserva[1]
        cantidad = reserva[2]
        nombre_cliente = reserva[3]
        telefono_cliente = reserva[4]
        cliente_id = reserva[5]
        
        if estado_actual == 'asistio':
            return False, f"⚠️ CÓDIGO YA USADO. Esta entrada ya fue escaneada anteriormente.\n(A nombre de: {nombre_cliente})"
            
        if estado_actual == 'ausente':
            return False, "❌ CÓDIGO VENCIDO. Esta función ya pasó y se marcó como ausente."
            
        # 3. Si todo está bien, actualizamos el estado a 'asistio'
        cursor.execute("UPDATE reservas SET estado = 'asistio' WHERE id = %s;", (reserva_id,))
        
        # 4. Le perdonamos las ausencias al cliente porque sí vino a esta
        cursor.execute("UPDATE clientes SET ausencias_seguidas = 0 WHERE id = %s;", (cliente_id,))
        
        conexion.commit()
        conexion.close()
        
        # Devolvemos un mensaje de éxito y el número del cliente para mandarle las gracias luego
        mensaje_exito = f"✅ ENTRADA VÁLIDA.\n👤 Cliente: {nombre_cliente}\n🎟️ Personas: {cantidad}\n¡Pueden pasar!"
        return True, (mensaje_exito, telefono_cliente, nombre_cliente)
        
    except Exception as e:
        print(f"❌ Error al validar entrada: {e}")
        return False, "Ocurrió un error interno al leer el código."
    

    # ==========================================
# NUEVA FUNCIÓN: VERIFICAR BLOQUEOS
# ==========================================
def verificar_bloqueo(telefono):
    """Revisa si el cliente está castigado y no puede reservar."""
    conexion = conectar_bd()
    if not conexion: return False, ""
    
    try:
        cursor = conexion.cursor()
        # Revisamos si la fecha de castigo es mayor a la hora exacta de hoy
        cursor.execute("SELECT bloqueado_hasta > CURRENT_TIMESTAMP FROM clientes WHERE telefono = %s;", (telefono,))
        resultado = cursor.fetchone()
        
        # Si el resultado es True, significa que sigue bloqueado
        if resultado and resultado[0] == True:
            # Buscamos el mensaje oficial de bloqueo del sistema (el que configuraste)
            cursor.execute("SELECT mensaje_bloqueo FROM configuracion WHERE id = 1;")
            mensaje_oficial = cursor.fetchone()[0]
            conexion.close()
            return True, mensaje_oficial
            
        # Si el resultado es False (ya pasaron las 2 semanas), le perdonamos los strikes
        if resultado and resultado[0] == False:
            cursor.execute("UPDATE clientes SET ausencias_seguidas = 0, bloqueado_hasta = NULL WHERE telefono = %s;", (telefono,))
            conexion.commit()
            
        conexion.close()
        return False, ""
    except Exception as e:
        print(f"❌ Error al verificar bloqueo: {e}")
        return False, ""