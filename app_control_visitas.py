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
# 1. CONFIGURACIÓN DE LA INTERFAZ MÓVIL
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Control de Visitas GeoLab", page_icon="📍", layout="centered")

st.title("📍 Control de Visitas de Campo")
st.subheader("Validación Geofencing y Navegación")

# -----------------------------------------------------------------------------
# 2. CÁLCULO DE DISTANCIA HAVERSINE (METROS)
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

# -----------------------------------------------------------------------------
# 3. CARGA DE PROSPECTOS ASIGNADOS (COMPATIBLE CON NUBE)
# -----------------------------------------------------------------------------
@st.cache_data
def cargar_prospectos():
    ruta_excel = "Prospectos_Asignados_y_Desbordamiento.xlsx"
    if not os.path.exists(ruta_excel):
        ruta_excel = r"D:\Usuarios\jmontesdeoca\Desktop\GeoLab\Exp2\Asignaciones\Prospectos_Asignados_y_Desbordamiento.xlsx"
    df = pd.read_excel(ruta_excel, sheet_name="Prospectos_Asignados")
    return df

try:
    df_prospectos = cargar_prospectos()
except Exception:
    st.error("❌ No se encontró el archivo 'Prospectos_Asignados_y_Desbordamiento.xlsx' en el repositorio.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. SELECCIÓN DE ASESOR Y PROSPECTO
# -----------------------------------------------------------------------------
vendedores_disponibles = sorted(df_prospectos['id_vendedor'].astype(str).unique())
vendedor_sel = st.selectbox("👤 Selecciona tu ID de Asesor:", vendedores_disponibles)

df_vendedor = df_prospectos[df_prospectos['id_vendedor'].astype(str) == vendedor_sel].copy()

st.info(f"📋 Tienes **{len(df_vendedor)}** prospectos asignados.")

col_nombre = 'Nombre' if 'Nombre' in df_vendedor.columns else 'nombre'
col_lat = 'Latitud' if 'Latitud' in df_vendedor.columns else 'lat'
col_lon = 'Longitud' if 'Longitud' in df_vendedor.columns else 'lon'

prospecto_sel_nombre = st.selectbox("🏪 Selecciona el comercio a visitar:", df_vendedor[col_nombre].values)

row_prospecto = df_vendedor[df_vendedor[col_nombre] == prospecto_sel_nombre].iloc[0]

lat_target = float(str(row_prospecto[col_lat]).replace(',', '.'))
lon_target = float(str(row_prospecto[col_lon]).replace(',', '.'))

st.markdown(f"**Ubicación Objetivo:** `{lat_target}, {lon_target}`")

# -----------------------------------------------------------------------------
# 5. BOTÓN 'IR' - NAVEGACIÓN EN GOOGLE MAPS
# -----------------------------------------------------------------------------
url_gmaps_navegacion = f"https://www.google.com/maps/dir/?api=1&destination={lat_target},{lon_target}"

st.link_button("🗺️ IR (Abrir Ruta en Google Maps)", url_gmaps_navegacion, use_container_width=True)

# -----------------------------------------------------------------------------
# 6. CAPTURA Y VALIDACIÓN GPS DE CAMPO
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🛰️ Validación de Coordenada GPS")

loc = get_geolocation()

if loc:
    lat_vendedor = loc['coords']['latitude']
    lon_vendedor = loc['coords']['longitude']
    
    st.success(f"📍 GPS Capturado: `{lat_vendedor:.5f}, {lon_vendedor:.5f}`")
    
    distancia_m = calcular_distancia_haversine(lat_vendedor, lon_vendedor, lat_target, lon_target)
    RADIO_MAXIMO_M = 50.0  # Radio máximo de tolerancia en metros
    
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
            foto = st.file_uploader("Adjuntar foto de la fachada:", type=["jpg", "png", "jpeg"])
            
            submit = st.form_submit_button("📌 Registrar Visita y Guardar Check-in")
            
            if submit:
                registro = pd.DataFrame([{
                    'Fecha_Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'id_vendedor': vendedor_sel,
                    'Comercio': prospecto_sel_nombre,
                    'Estatus': estatus_visita,
                    'Distancia_Metros': distancia_m,
                    'Lat_GPS_Vendedor': lat_vendedor,
                    'Lon_GPS_Vendedor': lon_vendedor,
                    'Observaciones': observaciones
                }])
                
                ruta_auditoria = "Auditoria_Visitas_Campo.csv"
                if not os.path.exists(ruta_auditoria):
                    registro.to_csv(ruta_auditoria, index=False, encoding='utf-8-sig')
                else:
                    registro.to_csv(ruta_auditoria, mode='a', header=False, index=False, encoding='utf-8-sig')
                
                st.balloons()
                st.success("🎉 ¡Visita auditada y guardada correctamente!")
    else:
        st.error(f"🚫 **CHECK-IN BLOQUEADO:** Te encuentras a {distancia_m} metros. Acércate a menos de {RADIO_MAXIMO_M} metros para habilitar el registro.")
else:
    st.warning("⚠️ Oprime **Permitir** en la ventana flotante de tu navegador móvil para activar la lectura del GPS.")
