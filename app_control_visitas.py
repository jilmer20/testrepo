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

RUTA_AUDITORIA = "Auditoria_Visitas_Campo.csv"

st.sidebar.title("📌 Menú GeoLab")
modo_app = st.sidebar.radio("Selecciona el perfil:", [
    "📱 Registro de Visitas (Vendedor)", 
    "🔐 Panel Admin / Auditoría"
])

# -----------------------------------------------------------------------------
# 2. FUNCIONES DE APOYO Y CÁLCULO DE DISTANCIA
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

@st.cache_data
def cargar_prospectos():
    ruta_excel = "Prospectos_Asignados_y_Desbordamiento.xlsx"
    if not os.path.exists(ruta_excel):
        ruta_excel = r"D:\Usuarios\jmontesdeoca\Desktop\GeoLab\Exp2\Asignaciones\Prospectos_Asignados_y_Desbordamiento.xlsx"
    df = pd.read_excel(ruta_excel, sheet_name="Prospectos_Asignados")
    return df

def obtener_comercio_visitados():
    """Obtiene la lista de comercios que ya tienen registro guardado en la auditoría."""
    if os.path.exists(RUTA_AUDITORIA):
        try:
            df_aud = pd.read_csv(RUTA_AUDITORIA)
            if 'Comercio' in df_aud.columns:
                return df_aud['Comercio'].dropna().unique().tolist()
        except Exception:
            return []
    return []

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

    # 1. PASO 1: SELECCIÓN DE SUCURSAL
    col_sucursal = 'Sucursal' if 'Sucursal' in df_prospectos.columns else 'Estado'
    sucursales_disponibles = sorted(df_prospectos[col_sucursal].dropna().astype(str).unique())
    
    sucursal_sel = st.selectbox("🏢 1. Selecciona tu Sucursal:", sucursales_disponibles)

    # Filtrar el DataFrame según la Sucursal elegida
    df_sucursal = df_prospectos[df_prospectos[col_sucursal].astype(str) == sucursal_sel].copy()

    # 2. PASO 2: SELECCIÓN DE ASESOR DE DICHA SUCURSAL
    col_asesor = 'ID-Nombre' if 'ID-Nombre' in df_sucursal.columns else 'id_vendedor'
    vendedores_disponibles = sorted(df_sucursal[col_asesor].dropna().astype(str).unique())
    
    vendedor_sel = st.selectbox("👤 2. Selecciona tu Asesor (ID - Nombre):", vendedores_disponibles)

    df_vendedor_total = df_sucursal[df_sucursal[col_asesor].astype(str) == vendedor_sel].copy()
    
    # FILTRADO DINÁMICO: Excluir comercios que ya han sido visitados
    visitados = obtener_comercio_visitados()
    col_nombre = 'Nombre' if 'Nombre' in df_vendedor_total.columns else 'nombre'
    
    df_vendedor_pendiente = df_vendedor_total[~df_vendedor_total[col_nombre].isin(visitados)].copy()
    
    total_asignados = len(df_vendedor_total)
    restantes = len(df_vendedor_pendiente)
    completados = total_asignados - restantes

    st.info(f"📋 **Progreso de Cartera:** Quedan **{restantes}** pendientes de {total_asignados} asignados ({completados} visitados).")

    if restantes == 0:
        st.balloons()
        st.success("🎉 **¡Felicidades!** Has completado la visita de todos tus prospectos asignados.")
    else:
        col_lat = 'Latitud' if 'Latitud' in df_vendedor_pendiente.columns else 'lat'
        col_lon = 'Longitud' if 'Longitud' in df_vendedor_pendiente.columns else 'lon'

        prospecto_sel_nombre = st.selectbox("🏪 Selecciona el comercio a visitar:", df_vendedor_pendiente[col_nombre].values)

        row_prospecto = df_vendedor_pendiente[df_vendedor_pendiente[col_nombre] == prospecto_sel_nombre].iloc[0]

        lat_target = float(str(row_prospecto[col_lat]).replace(',', '.'))
        lon_target = float(str(row_prospecto[col_lon]).replace(',', '.'))

        # TARJETA CON DETALLES DEL COMERCIO SELECCIONADO
        st.markdown("### 🏬 Detalles del Comercio")
        with st.container():
            col_a, col_b = st.columns(2)
            rubro_val = str(row_prospecto.get('Rubro', row_prospecto.get('rubro', 'No especificado')))
            tel_val = str(row_prospecto.get('Telefono', row_prospecto.get('telefono', row_prospecto.get('phone', 'No disponible'))))
            web_val = str(row_prospecto.get('Sitio_Web', row_prospecto.get('website', row_prospecto.get('sitio_web', 'No disponible'))))
            
            col_a.markdown(f"**🏷️️ Rubro:** {rubro_val}")
            col_a.markdown(f"**📞 Teléfono:** {tel_val}")
            col_b.markdown(f"**🌐 Sitio Web:** {web_val}")
            col_b.markdown(f"**📍 Coordenadas:** `{lat_target}, {lon_target}`")

        # BOTÓN DE NAVEGACIÓN DIRECTA EN GOOGLE MAPS
        url_gmaps_navegacion = f"https://www.google.com/maps/dir/?api=1&destination={lat_target},{lon_target}"
        st.link_button("🗺️ IR (Abrir Ruta en Google Maps)", url_gmaps_navegacion, use_container_width=True)

        st.divider()
        st.subheader("🛰️ Validación de Coordenada GPS")

        loc = get_geolocation()

        if loc:
            lat_vendedor = loc['coords']['latitude']
            lon_vendedor = loc['coords']['longitude']
            
            st.success(f"📍 GPS Capturado: `{lat_vendedor:.5f}, {lon_vendedor:.5f}`")
            
            distancia_m = calcular_distancia_haversine(lat_vendedor, lon_vendedor, lat_target, lon_target)
            RADIO_MAXIMO_M = 20.0  # Radio máximo permitido en metros
            
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
                            'Sucursal': sucursal_sel,
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
                        
                        st.cache_data.clear()
                        st.balloons()
                        st.success("🎉 ¡Visita auditada! El prospecto ha sido descontado de tu lista de pendientes.")
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
            
            st.subheader("📋 Registro Detallado de Check-ins")
            st.dataframe(df_auditoria, use_container_width=True)
            
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
