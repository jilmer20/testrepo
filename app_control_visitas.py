#!/usr/bin/env python
# coding: utf-8

# In[ ]:

import os
import math
import pandas as pd
from datetime import datetime
import streamlit as st
from streamlit_js_eval import get_geolocation

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA INTERFAZ MÓVIL Y ESTILOS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Control de Visitas GeoLab", page_icon="📍", layout="centered")

# Archivo de persistencia para el historial de respuestas de campo
RUTA_AUDITORIA = "Auditoria_Visitas_Campo.csv"

# MENÚ LATERAL DE NAVEGACIÓN (VENDEDOR vs ADMINISTRADOR)
st.sidebar.title("📌 Menú GeoLab")
modo_app = st.sidebar.radio("Selecciona el perfil:", [
    "📱 Registro de Visitas (Vendedor)", 
    "🔐 Panel Admin / Auditoría"
])

# -----------------------------------------------------------------------------
# 2. FUNCIONES DE APOYO Y CÁLCULO DE DISTANCIA (HAVERSINE)
# -----------------------------------------------------------------------------
def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia exacta en metros entre dos coordenadas geográficas."""
    R = 6371000  # Radio terrestre en metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

@st.cache_data
def cargar_prospectos():
    """Carga los prospectos desde el Excel en la nube o entorno local."""
    ruta_excel = "Prospectos_Asignados_y_Desbordamiento.xlsx"
    if not os.path.exists(ruta_excel):
        ruta_excel = r"D:\Usuarios\jmontesdeoca\Desktop\GeoLab\Exp2\Asignaciones\Prospectos_Asignados_y_Desbordamiento.xlsx"
    df = pd.read_excel(ruta_excel, sheet_name="Prospectos_Asignados")
    return df

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

    # Utilizar 'ID-Nombre' si existe en el archivo, o 'id_vendedor' como fallback
    col_asesor = 'ID-Nombre' if 'ID-Nombre' in df_prospectos.columns else 'id_vendedor'
    
    vendedores_disponibles = sorted(df_prospectos[col_asesor].astype(str).unique())
    vendedor_sel = st.selectbox("👤 Selecciona tu Asesor (ID - Nombre):", vendedores_disponibles)

    df_vendedor = df_prospectos[df_prospectos[col_asesor].astype(str) == vendedor_sel].copy()
    st.info(f"📋 Tienes **{len(df_vendedor)}** prospectos asignados.")

    # Selección del comercio
    col_nombre = 'Nombre' if 'Nombre' in df_vendedor.columns else 'nombre'
    col_lat = 'Latitud' if 'Latitud' in df_vendedor.columns else 'lat'
    col_lon = 'Longitud' if 'Longitud' in df_vendedor.columns else 'lon'

    prospecto_sel_nombre = st.selectbox("🏪 Selecciona el comercio a visitar:", df_vendedor[col_nombre].values)

    row_prospecto = df_vendedor[df_vendedor[col_nombre] == prospecto_sel_nombre].iloc[0]

    lat_target = float(str(row_prospecto[col_lat]).replace(',', '.'))
    lon_target = float(str(row_prospecto[col_lon]).replace(',', '.'))

    st.markdown(f"**Ubicación Objetivo:** `{lat_target}, {lon_target}`")

    # BOTÓN DE NAVEGACIÓN DIRECTA A GOOGLE MAPS
    url_gmaps_navegacion = f"https://www.google.com/maps/dir/?api=1&destination={lat_target},{lon_target}"
    st.link_button("🗺️ IR (Abrir Ruta en Google Maps)", url_gmaps_navegacion, use_container_width=True)

    st.divider()
    st.subheader("🛰️️ Validación de Coordenada GPS")

    # Lectura del GPS nativo del teléfono
    loc = get_geolocation()

    if loc:
        lat_vendedor = loc['coords']['latitude']
        lon_vendedor = loc['coords']['longitude']
        
        st.success(f"📍 GPS Capturado: `{lat_vendedor:.5f}, {lon_vendedor:.5f}`")
        
        distancia_m = calcular_distancia_haversine(lat_vendedor, lon_vendedor, lat_target, lon_target)
        RADIO_MAXIMO_M = 20.0  # Tolerancia máxima permitida en metros
        
        st.metric(label="Distancia al Establecimiento", value=f"{distancia_m} metros")
        
        if distancia_m <= RADIO_MAXIMO_M:
            st.success("✅ **CHECK-IN HABILITADO:** Confirmado que estás presencialmente en el comercio.")
            
            with st.form("form_visita"):
                estatus_visita = st.selectbox("Estatus de la Visita:", [
                    "Efectiva / Venta realizada", 
                    "Cerrado temporalmente", 
                    "No desea ser visitado", 
                    "Local no existe / Cambió de rubro"
                ])
                observaciones = st.text_area("Observaciones de la visita:")
                
                submit = st.form_submit_button("📌 Registrar Visita y Guardar Check-in")
                
                if submit:
                    registro = pd.DataFrame([{
                        'Fecha_Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'Asesor': vendedor_sel,
                        'Comercio': prospecto_sel_nombre,
                        'Estatus': estatus_visita,
                        'Distancia_Metros': distancia_m,
                        'Lat_GPS_Vendedor': lat_vendedor,
                        'Lon_GPS_Vendedor': lon_vendedor,
                        'Observaciones': observaciones
                    }])
                    
                    if not os.path.exists(RUTA_AUDITORIA):
                        registro.to_csv(RUTA_AUDITORIA, index=False, encoding='utf-8-sig')
                    else:
                        registro.to_csv(RUTA_AUDITORIA, mode='a', header=False, index=False, encoding='utf-8-sig')
                    
                    st.balloons()
                    st.success("🎉 ¡Visita auditada y guardada correctamente!")
        else:
            st.error(f"🚫 **CHECK-IN BLOQUEADO:** Te encuentras a {distancia_m} metros. Acércate a menos de {RADIO_MAXIMO_M} metros para habilitar el registro.")
    else:
        st.warning("⚠️ Oprime **Permitir** en la ventana flotante de tu navegador móvil para activar la lectura del GPS.")

# =============================================================================
# MODO 2: PANEL DE ADMINISTRACIÓN Y AUDITORÍA (COORDINACIÓN)
# =============================================================================
elif modo_app == "🔐 Panel Admin / Auditoría":
    st.title("🔐 Panel de Control de Auditoría")
    
    # CLAVE DE ACCESO
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
            
            st.subheader("📋 Registro Detallado de Check-ins")
            st.dataframe(df_auditoria, use_container_width=True)
            
            # BOTÓN DE DESCARGA
            csv_data = df_auditoria.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            
            st.download_button(
                label="📥 Descargar Reporte de Visitas (CSV / Excel)",
                data=csv_data,
                file_name=f"Reporte_Auditoria_Visitas_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("ℹ️ Aún no hay registros de visitas capturados en el sistema.")
    elif password != "":
        st.error("🔑 Clave de acceso incorrecta.")
