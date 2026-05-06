import database
from datetime import date

def generar_reporte_diario():
    """Genera un resumen en texto de cómo le fue al cine hoy."""
    conexion = database.conectar_bd()
    if not conexion: return "Error de conexión."

    try:
        cursor = conexion.cursor()
        hoy = date.today()

        # 1. Total de Reservas generadas hoy
        cursor.execute("SELECT COUNT(*), SUM(cantidad_personas) FROM reservas WHERE DATE(fecha_reserva) = %s;", (hoy,))
        datos_reservas = cursor.fetchone()
        total_tickets = datos_reservas[0] or 0
        total_personas = datos_reservas[1] or 0

        # 2. Total de personas que SÍ asistieron hoy
        cursor.execute("SELECT SUM(cantidad_personas) FROM reservas WHERE DATE(fecha_reserva) = %s AND estado = 'asistio';", (hoy,))
        total_asistieron = cursor.fetchone()[0] or 0

        # 3. Total de personas AUSENTES hoy
        cursor.execute("SELECT SUM(cantidad_personas) FROM reservas WHERE DATE(fecha_reserva) = %s AND estado = 'ausente';", (hoy,))
        total_ausentes = cursor.fetchone()[0] or 0

        conexion.close()

        # Armamos el mensaje final estilo WhatsApp
        reporte = (
            f"📊 *REPORTE DIARIO DE CINE* ({hoy})\n"
            f"-----------------------------------\n"
            f"🎟️ Tickets generados: {total_tickets}\n"
            f"👥 Total espacios reservados: {total_personas}\n"
            f"✅ Personas que ASISTIERON: {total_asistieron}\n"
            f"❌ Personas AUSENTES: {total_ausentes}\n"
            f"-----------------------------------\n"
        )
        return reporte

    except Exception as e:
        return f"Error al generar reporte: {e}"

def auditar_y_castigar_ausentes():
    """Esta función se corre al final de la noche. Castiga a los que no fueron."""
    conexion = database.conectar_bd()
    if not conexion: return False

    try:
        cursor = conexion.cursor()

        # 1. Traemos la regla del administrador (Ej: a las 2 ausencias se bloquea)
        cursor.execute("SELECT limite_ausencias_seguidas FROM configuracion WHERE id = 1;")
        limite = cursor.fetchone()[0]

        # 2. Buscamos todas las reservas de hoy que se quedaron en estado 'reservada' 
        # (Es decir, que el recepcionista nunca las escaneó). Las pasamos a estado 'ausente'.
        cursor.execute("""
            UPDATE reservas
            SET estado = 'ausente'
            WHERE estado = 'reservada' AND DATE(fecha_reserva) = CURRENT_DATE
            RETURNING cliente_id;
        """)
        clientes_que_fallaron = cursor.fetchall()

        # 3. Le sumamos 1 ausencia (strike) a cada uno de esos clientes irresponsables
        for cliente in clientes_que_fallaron:
            c_id = cliente[0]
            cursor.execute("UPDATE clientes SET ausencias_seguidas = ausencias_seguidas + 1 WHERE id = %s;", (c_id,))

        # 4. El Martillo: Bloqueamos por 14 días a los que llegaron al límite de strikes
        cursor.execute("""
            UPDATE clientes
            SET bloqueado_hasta = CURRENT_TIMESTAMP + INTERVAL '14 days'
            WHERE ausencias_seguidas >= %s AND bloqueado_hasta IS NULL;
        """, (limite,))

        conexion.commit()
        conexion.close()
        return True
        
    except Exception as e:
        print(f"Error en auditoría: {e}")
        return False

# ==========================================
# Zona de Prueba (Simulador de Fin de Día)
# ==========================================
if __name__ == "__main__":
    print("\n⏳ Simulando que el cine cerró y son las 11:59 PM...")
    
    print("\n🔍 1. Corriendo el Auditor de Asistencias y Castigos...")
    exito = auditar_y_castigar_ausentes()
    if exito:
        print("✅ ¡Auditoría terminada! Los ausentes han recibido su 'strike'.")
        
    print("\n📈 2. Generando el Reporte para el Administrador...")
    reporte_final = generar_reporte_diario()
    print(f"\n{reporte_final}")