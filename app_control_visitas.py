#!/usr/bin/env python
# coding: utf-8

# In[ ]:

import os
import math
import re
import io
import pandas as pd
from datetime import datetime
from PIL import Image, ImageOps
import streamlit as st
from streamlit_js_eval import get_geolocation

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA INTERFAZ MÓVIL Y ESTILOS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Control de Visitas GeoLab", page_icon="📍", layout="centered")

RUTA_AUDITORIA = "Auditoria_Visitas_Campo.csv"
CARPETA_FOTOS = "Fotos_Evidencia"

if not os.path.exists(CARPETA_FOTOS):
    os.makedirs(CARPETA_FOTOS)

st.sidebar.title("📌 Menú GeoLab")
modo_app = st.sidebar.radio("Selecciona el perfil:", [
    "📱 Registro de Visitas (Vendedor)", 
    "🔐 Panel Admin / Auditoría"
])

st.sidebar.divider()

if st.sidebar.button("🔄 Recargar Datos del Excel", use_container_width=True):
    st.cache_data.clear()
    for key in ['foto_comprimida_bytes', 'ruta_foto_temp']:
        if key in st.session_state:
            del st.session_state[key]
    st.sidebar.success("¡Caché borrada! Leyendo la versión más reciente del Excel...")
    st.rerun()

# -----------------------------------------------------------------------------
# 2. FUNCIONES DE APOYO Y OPTIMIZACIÓN DE IMAGEN
# -----------------------------------------------------------------------------
def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Radio terrestre en metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def limpiar_formato_rif(rif_raw):
    if not rif_raw:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', str(rif_raw)).upper()

def comprimir_y_procesar_foto(bytes_imagen, max_dimension=1280, calidad=75):
    """Comprime la foto recibida a ~150KB en memoria de forma instantánea."""
    if not bytes_imagen:
        return None
    try:
        imagen = Image.open(io.BytesIO(bytes_imagen))
        imagen = ImageOps.exif_transpose(imagen) # Respetar orientación vertical del celular

        if imagen.mode in ("RGBA", "P"):
            imagen = imagen.convert("RGB")

        imagen.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        
        buffer_salida = io.BytesIO()
        imagen.save(buffer_salida, format="JPEG", optimize=True, quality=calidad)
        return buffer_salida.getvalue()
    except Exception as e:
        st.error(f"Error comprimiendo foto: {e}")
        return None

def guardar_foto_disco(bytes_comprimidos, comercio_nombre):
    """Guarda la foto optimizada de session_state al disco."""
    if not bytes_comprimidos:
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^A-Za-z0-9]', '_', str(comercio_nombre))
    nombre_archivo = f"{timestamp}_{nombre_limpio}.jpg"
    ruta_completa = os.path.join(CARPETA_FOTOS, nombre_archivo)
    
    with open(ruta_completa, "wb") as f:
        f.write(bytes_comprimidos)
    return ruta_completa

@st.cache_data
def cargar_prospectos():
    ruta_excel = "Prospectos_Asignados_y_Desbordamiento.xlsx"
    if not os.path.exists(ruta_excel):
        ruta_excel = r"D:\Usuarios\jmontesdeoca\Desktop\GeoLab\Exp2\Asignaciones\Prospectos_Asignados_y_Desbordamiento.xlsx"
    df = pd.read_excel(ruta_excel, sheet_name="Prospectos_Asignados")
    df.columns = df.columns.str.strip()
    return df

def obtener_comercios_finalizados():
    if os.path.exists(RUTA_AUDITORIA):
        try:
            df_aud = pd.read_csv(RUTA_AUDITORIA)
            if 'Comercio' in df_aud.columns and 'Estatus' in df_aud.columns:
                estatus_reintento = ["Cerrado temporalmente", "No desea ser visitado", "Cerrado", "No interesado"]
                definitivos = df_aud[~df_aud['Estatus'].isin(estatus_reintento)]['Comercio'].unique().tolist()
                
                df_reintentos = df_aud[df_aud['Estatus'].isin(estatus_reintento)]
                conteo_reintentos = df_reintentos.groupby('Comercio').size()
                descartados_segunda_visita = conteo_reintentos[conteo_reintentos >= 2].index.tolist()
                
                return list(set(definitivos + descartados_segunda_visita))
        except Exception:
            return []
    return []

def obtener_conteo_visitas_comercio(comercio_nombre):
    if os.path.exists(RUTA_AUDITORIA):
        try:
            df_aud = pd.read_csv(RUTA_AUDITORIA)
            if 'Comercio' in df_aud.columns:
                return len(df_aud[df_aud['Comercio'] == comercio_nombre])
        except Exception:
            return 0
    return 0

# =============================================================================
# MODO 1: REGISTRO DE VISITAS DE CAMPO (ASESORES DE VENTA)
# =============================================================================
if modo_app == "📱 Registro de Visitas (Vendedor)":
    st.title("📍 Control de Visitas de Campo")
    st.subheader("Validación Geofencing y Navegación")

    try:
        df_prospectos = cargar_prospectos()
    except Exception:
        st.error("❌ No se encontró el archivo 'Prospectos_Asignados_y_Desbordamiento.xlsx' en el servidor.")
        st.stop()

    columnas_lower = {col.lower(): col for col in df_prospectos.columns}
    col_sucursal = columnas_lower.get('sucursal', columnas_lower.get('estado', df_prospectos.columns[0]))

    sucursales_disponibles = sorted(df_prospectos[col_sucursal].dropna().astype(str).unique())
    sucursal_sel = st.selectbox("🏢 1. Selecciona tu Sucursal:", sucursales_disponibles)

    df_sucursal = df_prospectos[df_prospectos[col_sucursal].astype(str) == sucursal_sel].copy()

    col_asesor = columnas_lower.get('id-nombre', columnas_lower.get('id_vendedor', 'Asesor'))
    vendedores_disponibles = sorted(df_sucursal[col_asesor].dropna().astype(str).unique())
    vendedor_sel = st.selectbox("👤 2. Selecciona tu Asesor (ID - Nombre):", vendedores_disponibles)

    df_vendedor_total = df_sucursal[df_sucursal[col_asesor].astype(str) == vendedor_sel].copy()
    
    completados_lista = obtener_comercios_finalizados()
    col_nombre = columnas_lower.get('nombre', 'Nombre')
    df_vendedor_pendiente = df_vendedor_total[~df_vendedor_total[col_nombre].isin(completados_lista)].copy()
    
    total_asignados = len(df_vendedor_total)
    restantes = len(df_vendedor_pendiente)
    atendidos = total_asignados - restantes

    st.info(f"📋 **Progreso de Cartera:** Quedan **{restantes}** pendientes de {total_asignados} asignados ({atendidos} cerrados/finalizados).")

    if restantes == 0:
        st.balloons()
        st.success("🎉 **¡Felicidades!** Has completado la visita de todos tus prospectos asignados.")
    else:
        col_lat = columnas_lower.get('latitud', columnas_lower.get('lat', 'Latitud'))
        col_lon = columnas_lower.get('longitud', columnas_lower.get('lon', 'Longitud'))

        prospecto_sel_nombre = st.selectbox("🏪 Selecciona el comercio a visitar:", df_vendedor_pendiente[col_nombre].values)

        row_prospecto = df_vendedor_pendiente[df_vendedor_pendiente[col_nombre] == prospecto_sel_nombre].iloc[0]

        lat_target = float(str(row_prospecto[col_lat]).replace(',', '.'))
        lon_target = float(str(row_prospecto[col_lon]).replace(',', '.'))

        num_intentos_previos = obtener_conteo_visitas_comercio(prospecto_sel_nombre)
        if num_intentos_previos == 1:
            st.warning("⚠️ **ATENCIÓN:** Este comercio se encuentra en **SEGUNDO INTENTO DE VISITA**.")

        st.markdown("### 🏬 Detalles del Comercio")
        with st.container():
            col_a, col_b = st.columns(2)
            rubro_val = str(row_prospecto.get('Rubro', row_prospecto.get('rubro', 'No especificado')))
            tel_val = str(row_prospecto.get('Telefono', row_prospecto.get('telefono', row_prospecto.get('phone', 'No disponible'))))
            web_val = str(row_prospecto.get('Sitio_Web', row_prospecto.get('website', row_prospecto.get('sitio_web', 'No disponible'))))
            
            col_a.markdown(f"**🏷 Rubro:** {rubro_val}")
            col_a.markdown(f"**📞 Teléfono Principal:** {tel_val}")
            col_b.markdown(f"**🌐 Sitio Web:** {web_val}")
            col_b.markdown(f"**📍 Coordenadas:** `{lat_target}, {lon_target}`")

        url_gmaps_navegacion = f"https://www.google.com/maps/dir/?api=1&destination={lat_target},{lon_target}"
        st.link_button("🗺 IR (Abrir Ruta en Google Maps)", url_gmaps_navegacion, use_container_width=True)

        st.divider()
        st.subheader("🛰️ Validación de Coordenada GPS")

        loc = get_geolocation()

        if loc:
            lat_vendedor = loc['coords']['latitude']
            lon_vendedor = loc['coords']['longitude']
            
            st.success(f"📍 GPS Capturado: `{lat_vendedor:.5f}, {lon_vendedor:.5f}`")
            
            distancia_m = calcular_distancia_haversine(lat_vendedor, lon_vendedor, lat_target, lon_target)
            RADIO_MAXIMO_M = 40.0
            
            st.metric(label="Distancia al Establecimiento", value=f"{distancia_m} metros")
            
            if distancia_m <= RADIO_MAXIMO_M:
                st.success("✅ **CHECK-IN HABILITADO:** Confirmado que estás presencialmente en el comercio.")
                
                st.markdown("### 📝 Formulario de Registro")
                
                estatus_visita = st.selectbox("Estatus de la Visita (*):", [
                    "Efectiva / Visita realizada", 
                    "Cerrado",
                    "Clausurado",
                    "No interesado", 
                    "Local no existe / Cambió de rubro"
                ])
                
                # -------------------------------------------------------------
                # CAPTURA DIRECTA Y RESPALDO EN SESSION STATE
                # -------------------------------------------------------------
                st.markdown("#### 📸 Captura de Evidencia Fotográfica (En Vivo)")
                
                foto_camara = st.camera_input("Tomar foto del local en tiempo real")

                # Si la cámara toma la foto, se comprime y se respalda INMEDIATAMENTE
                if foto_camara is not None:
                    bytes_raw = foto_camara.getvalue()
                    st.session_state['foto_comprimida_bytes'] = comprimir_y_procesar_foto(bytes_raw)

                # Mostrar visualmente al vendedor que la foto ya está asegurada
                if st.session_state.get('foto_comprimida_bytes') is not None:
                    st.success("📸 **Foto procesada y asegurada en el sistema.**")
                    st.image(st.session_state['foto_comprimida_bytes'], caption="Vista previa comprimida (~150 KB)", width=250)

                rif_cliente_input = st.text_input("📄 Número de RIF del Cliente (Sin guiones, Ej: J123456780) (* Obligatorio para visitas efectivas):")
                telefono_add = st.text_input("📞 Teléfono Adicional / Contacto Secundario:")
                
                st.markdown("---")
                st.markdown("#### 📊 Encuesta de Mercado (Opcional)")
                
                trabaja_bebidas_alimentos = st.radio("¿Vende o trabaja Ud. con Bebidas y Alimentos?", ["Sin responder", "SI", "NO"], horizontal=True)
                trabaja_embutidos = st.radio("¿Vende o trabaja Ud. con embutidos?", ["Sin responder", "SI", "NO"], horizontal=True)
                cuales_embutidos = st.text_input("¿Cuáles embutidos trabaja? (Opcional):")
                posee_nevera = st.radio("¿Posee Nevera / Exhibidor Refrigerado?", ["Sin responder", "SI", "NO"], horizontal=True)
                posee_rebanadora = st.radio("¿Posee rebanadora?", ["Sin responder", "SI", "NO"], horizontal=True)
                observaciones = st.text_area("Observaciones de la visita:")
                
                # BOTÓN FINAL DE REGISTRO
                if st.button("📌 Registrar Visita y Guardar Check-in", type="primary", use_container_width=True):
                    
                    # 1. VALIDACIÓN DE RIF
                    rif_limpio = limpiar_formato_rif(rif_cliente_input)
                    if estatus_visita == "Efectiva / Visita realizada":
                        if not rif_limpio:
                            st.error("❌ **CAMPO OBLIGATORIO:** Debes ingresar el RIF del cliente para registrar una visita Efectiva.")
                            st.stop()
                        elif len(rif_limpio) < 7:
                            st.error("❌ **FORMATO INVÁLIDO:** Por favor ingresa un RIF válido sin guiones (Ejemplo: J123456780).")
                            st.stop()

                    # 2. VALIDACIÓN DE FOTO (DESDE SESSION_STATE)
                    bytes_foto_final = st.session_state.get('foto_comprimida_bytes', None)
                    
                    if estatus_visita in ["Local no existe / Cambió de rubro", "Clausurado", "Efectiva / Visita realizada"] and bytes_foto_final is None:
                        st.error("❌ **FOTO REQUERIDA:** Debes tomar la foto con la cámara antes de guardar.")
                        st.stop()

                    # 3. ESCRIBIR FOTO OPTIMIZADA EN DISCO
                    ruta_foto_guardada = ""
                    if bytes_foto_final is not None:
                        ruta_foto_guardada = guardar_foto_disco(bytes_foto_final, prospecto_sel_nombre)

                    # 4. APPEND AL CSV
                    registro = pd.DataFrame([{
                        'Fecha_Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'Sucursal': sucursal_sel,
                        'Asesor': vendedor_sel,
                        'Comercio': prospecto_sel_nombre,
                        'Estatus': estatus_visita,
                        'Intento_Numero': num_intentos_previos + 1,
                        'RIF_Cliente': rif_limpio,
                        'Telefono_Adicional': telefono_add,
                        'Trabaja_Bebidas_Alimentos': trabaja_bebidas_alimentos,
                        'Trabaja_Embutidos': trabaja_embutidos,
                        'Cuales_Embutidos': cuales_embutidos,
                        'Posee_Nevera': posee_nevera,
                        'Posee_Rebanadora': posee_rebanadora,
                        'Distancia_Metros': distancia_m,
                        'Lat_GPS_Vendedor': lat_vendedor,
                        'Lon_GPS_Vendedor': lon_vendedor,
                        'Ruta_Foto_Evidencia': ruta_foto_guardada,
                        'Observaciones': observaciones
                    }])
                    
                    if not os.path.exists(RUTA_AUDITORIA):
                        registro.to_csv(RUTA_AUDITORIA, index=False, encoding='utf-8-sig')
                    else:
                        registro.to_csv(RUTA_AUDITORIA, mode='a', header=False, index=False, encoding='utf-8-sig')

                    # Limpiar estado de la foto para la siguiente toma
                    if 'foto_comprimida_bytes' in st.session_state:
                        del st.session_state['foto_comprimida_bytes']

                    st.cache_data.clear()
                    st.balloons()
                    
                    if estatus_visita in ["Cerrado", "No interesado"] and num_intentos_previos == 0:
                        st.warning("⚠️ **Visita Registrada (1er Intento):** El prospecto se mantendrá en tu lista para una segunda visita de verificación.")
                    else:
                        st.success("🎉 **¡Visita Auditada con Éxito!** Registro y foto guardados correctamente.")
                        
                    st.rerun()
            else:
                st.error(f"🚫 **CHECK-IN BLOQUEADO:** Te encuentras a {distancia_m} metros. Acércate a menos de {RADIO_MAXIMO_M} metros para habilitar el registro.")
        else:
            st.warning("⚠️ Oprime **Permitir** en la ventana flotante de tu navegador móvil para activar la lectura del GPS.")

# =============================================================================
# MODO 2: PANEL DE ADMINISTRACIÓN Y AUDITORÍA (COORDINACIÓN)
# =============================================================================
elif modo_app == "🔐 Panel Admin / Auditoría":
    st.title("🔐 Panel de Control de Auditoría")
    
    password = st.text_input("Ingresa la clave de administrador:", type="password")
    
    if password == "Geolab2026":
        st.success("🔓 Acceso concedido")
        
        if os.path.exists(RUTA_AUDITORIA):
            df_auditoria = pd.read_csv(RUTA_AUDITORIA)
            
            st.subheader("📊 Resumen General de Visitas")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Visitas Auditadas", len(df_auditoria))
            
            col_asesor_aud = 'Asesor' if 'Asesor' in df_auditoria.columns else 'id_vendedor'
            col2_val = df_auditoria[col_asesor_aud].nunique() if col_asesor_aud in df_auditoria.columns else 0
            col2.metric("Asesores Activos", col2_val)
            
            col3.metric("Visitas Efectivas", len(df_auditoria[df_auditoria['Estatus'].str.contains("Efectiva", na=False)]))
            
            st.subheader("📋 Registro Detallado de Check-ins y Encuesta")
            st.dataframe(df_auditoria, use_container_width=True)

            st.subheader("🖼️ Visor de Evidencias Fotográficas")
            df_con_fotos = df_auditoria[df_auditoria['Ruta_Foto_Evidencia'].notna() & (df_auditoria['Ruta_Foto_Evidencia'] != "")]
            
            if len(df_con_fotos) > 0:
                comercio_foto_sel = st.selectbox("Selecciona un comercio para ver su foto de evidencia:", df_con_fotos['Comercio'].unique())
                registro_foto = df_con_fotos[df_con_fotos['Comercio'] == comercio_foto_sel].iloc[-1]
                
                ruta_img = registro_foto['Ruta_Foto_Evidencia']
                if os.path.exists(ruta_img):
                    st.image(ruta_img, caption=f"Foto evidencia de {comercio_foto_sel} - Estatus: {registro_foto['Estatus']}")
                else:
                    st.warning("La foto registrada no se encuentra en el servidor.")
            else:
                st.info("No hay fotos de evidencia guardadas aún.")
            
            csv_data = df_auditoria.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            
            st.download_button(
                label="📥 Descargar Reporte Completo de Visitas (CSV / Excel)",
                data=csv_data,
                file_name=f"Reporte_Auditoria_Visitas_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("ℹ️ Aún no hay registros de visitas capturados en el sistema.")
    elif password != "":
        st.error("🔑 Clave de acceso incorrecta.")
