import qrcode
import os

def crear_qr(datos_reserva, nombre_archivo):
    """
    Toma los datos de la reserva, genera un código QR y lo guarda como imagen PNG.
    Devuelve la ruta (el camino) donde quedó guardada la imagen para que el bot la pueda enviar.
    """
    # 1. Por orden profesional, creamos una carpeta llamada 'qrs' si no existe
    # para que no se nos llene el proyecto de imágenes sueltas.
    if not os.path.exists('qrs'):
        os.makedirs('qrs')
        
    ruta_final = f"qrs/{nombre_archivo}.png"
    
    # 2. Configuramos cómo queremos que se vea el QR
    qr = qrcode.QRCode(
        version=1, # Tamaño del QR
        error_correction=qrcode.constants.ERROR_CORRECT_L, # Permite leerlo aunque esté un poco borroso
        box_size=10, # Tamaño de los cuadritos
        border=4, # Borde blanco alrededor
    )
    
    # 3. Le inyectamos la información y creamos la imagen
    qr.add_data(datos_reserva)
    qr.make(fit=True)
    
    imagen = qr.make_image(fill_color="black", back_color="white")
    
    # 4. Guardamos la imagen en nuestra carpeta
    imagen.save(ruta_final)
    
    print(f"✅ ¡Código QR generado y guardado en: {ruta_final}!")
    return ruta_final

# ==========================================
# Zona de Prueba
# ==========================================
if __name__ == "__main__":
    # Vamos a simular que alguien hizo una reserva
    info_secreta = "ID: 105 | Cris | Deadpool | 2 Personas | VIP"
    
    # Mandamos a crear el QR y le ponemos de nombre 'entrada_105'
    crear_qr(info_secreta, "entrada_105")
