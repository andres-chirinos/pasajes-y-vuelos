#!/usr/bin/env python3

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import logging
logging.basicConfig(level=logging.INFO)

# Configurar sys.path para mefp_datos
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ROOT_DIR = PROJECT_DIR.parent
if str(ROOT_DIR / "mefp_datos") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "mefp_datos"))

try:
    import mefp_datos
    from mefp_datos.ckan import sincronizar_datapackage, descargar_recurso
except ImportError:
    mefp_datos = None
    sincronizar_datapackage = None
    descargar_recurso = None

AEROPUERTOS = [
    "El ALTo", "Viru Viru", "Jorge Wilstermann", "Sucre", "Tarija", "Trinidad",
    "Uyuni", "Oruro", "Potosi", "Cobija", "Riberalta", "Rurrenabaque", "Guayamerin", "Yacuiba"
]

SESSION_URL = "https://fids.naabol.gob.bo/"
BASE_URL = "https://fids.naabol.gob.bo/Fids/itin/vuelos"
RUTA_SALIDA = Path("/tmp")
MAX_FETCH_ATTEMPTS = 3

COLUMNAS_ORDEN = [
    "fecha_consulta",
    "AEROPUERTO",
    "TIPO_OPERACION",
    "FECHA_HORA_FORMAT",
    "FECHA",
    "FECHA_HORA",
    "NRO_VUELO",
    "NOMBRE_AEROLINEA",
    "ID_EMPRESA",
    "RUTA0",
    "HORA_ESTIMADA",
    "HORA_REAL",
    "NRO_PUERTA",
    "OBSERVACION",
    "OBSERVACION_INGLES",
    "COD_COMENTARIO",
    "IDDW_ITINERARIO",
    "ID_ITINERARIO",
    "CORRELATIVO",
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
})
session.verify = False


def init_session():
    try:
        logging.info("Obteniendo cookies de https://fids.naabol.gob.bo/...")
        res = session.get(SESSION_URL, timeout=15)
        logging.info(f"Cookies obtenidas: {list(session.cookies.keys())}")
    except Exception as exc:
        logging.warning(f"No se pudieron obtener cookies iniciales: {exc}")


def _get_data(aero, tipo, now_str):
    params = {"aero": aero, "tipo": tipo}
    last_error = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            response = session.get(BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json()
                if isinstance(items, list):
                    for item in items:
                        item["fecha_consulta"] = now_str
                    return items
                return []
        except Exception as exc:
            last_error = exc
            logging.warning(f"Intento {attempt} falló para aeropuerto '{aero}' (tipo '{tipo}'): {exc}")
            if attempt < MAX_FETCH_ATTEMPTS:
                time.sleep(2)
    logging.error(f"Error al obtener datos para '{aero}' ({tipo}): {last_error}")
    return []


def get_all_fids_data(now_str):
    init_session()
    all_rows = []
    for aero in AEROPUERTOS:
        logging.info(f"Consultando FIDS para {aero} (Salidas)...")
        salidas = _get_data(aero, "S", now_str)
        all_rows.extend(salidas)

        logging.info(f"Consultando FIDS para {aero} (Llegadas)...")
        llegadas = _get_data(aero, "L", now_str)
        all_rows.extend(llegadas)

    if not all_rows:
        return pd.DataFrame(columns=COLUMNAS_ORDEN)

    df = pd.DataFrame(all_rows)
    for col in COLUMNAS_ORDEN:
        if col not in df.columns:
            df[col] = ""

    return df[COLUMNAS_ORDEN]


def format_columns(df):
    if df.empty:
        return df

    df = df.copy()
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip().replace(["nan", "None"], "")

    if "RUTA0" in df.columns:
        df = df[df["RUTA0"] != ""].reset_index(drop=True)

    cols = [c for c in COLUMNAS_ORDEN if c in df.columns]
    return df[cols]


def consolidate(df):
    logging.info("Consolidando eventos de vuelos FIDS...")
    csv_path = PROJECT_DIR / "data.csv"
    oldf = pd.DataFrame(columns=COLUMNAS_ORDEN)

    # Intentar descargar versión previa desde CKAN
    if descargar_recurso:
        try:
            ruta_guardado = RUTA_SALIDA / "vuelos_fids_guardado.parquet"
            descargar_recurso(
                "vuelos_fids_naabol",
                "vuelos_fids_naabol_parquet",
                path=ruta_guardado,
                sobrescribir=True,
            )
            if ruta_guardado.exists():
                oldf = pd.read_parquet(ruta_guardado)
        except Exception as exc:
            logging.info(f"No se pudo descargar recurso previo desde CKAN: {exc}")

    # Fallback a AIStor o local data.csv
    if oldf.empty and mefp_datos and hasattr(mefp_datos, "aistor"):
        try:
            ruta_base = mefp_datos.aistor.repo_prefix()
            reporte_ruta = ruta_base + "/data.parquet"
            if mefp_datos.aistor.existe_objeto(reporte_ruta):
                tmp_aistor_path = RUTA_SALIDA / "aistor_vuelos_fids.parquet"
                mefp_datos.aistor.descargar_objeto(reporte_ruta, tmp_aistor_path)
                oldf = pd.read_parquet(tmp_aistor_path)
        except Exception as exc:
            logging.warning(f"No se pudo consultar AIStor: {exc}")

    if oldf.empty and csv_path.exists():
        oldf = pd.read_csv(csv_path, na_filter=False)

    oldf = format_columns(oldf)
    df = format_columns(df)

    compare_cols = ["FECHA_HORA_FORMAT", "AEROPUERTO", "TIPO_OPERACION", "NRO_VUELO"]
    joindf = pd.concat([oldf, df], axis=0, ignore_index=True)
    # Eliminar duplicados literales exactos
    joindf = joindf.drop_duplicates()
    # Mantener el registro más reciente por clave de vuelo
    finaldf = joindf.drop_duplicates(subset=compare_cols, keep="last")
    finaldf = finaldf.sort_values(["FECHA_HORA_FORMAT", "AEROPUERTO", "NRO_VUELO"]).reset_index(drop=True)

    return format_columns(finaldf)


def metadata_tabla(tabla):
    timestamps = pd.to_datetime(tabla["FECHA_HORA_FORMAT"], errors="coerce").dropna()
    if timestamps.empty:
        timestamps = pd.to_datetime(tabla["fecha_consulta"], errors="coerce").dropna()
    return {
        "fecha_minima": timestamps.min().isoformat() if not timestamps.empty else "",
        "fecha_maxima": timestamps.max().isoformat() if not timestamps.empty else "",
        "filas": int(tabla.shape[0]),
    }


def actualizar():
    now_str = datetime.now(timezone(timedelta(hours=-4))).strftime("%Y-%m-%d %H:%M:%S")
    data = get_all_fids_data(now_str)
    tabla = consolidate(data)

    csv_path = PROJECT_DIR / "data.csv"
    tabla.to_csv(csv_path, index=False)
    logging.info(f"Guardado local CSV: {csv_path} ({len(tabla)} filas)")

    local_parquet = PROJECT_DIR / "vuelos_fids_naabol.parquet"
    tabla.to_parquet(local_parquet, index=False)

    ruta_salida_parquet = RUTA_SALIDA / "vuelos_fids_naabol.parquet"
    tabla.to_parquet(ruta_salida_parquet, index=False)

    excel_path = RUTA_SALIDA / "vuelos_fids_naabol.xlsx"
    tabla.to_excel(
        excel_path,
        index=False,
        columns=[c for c in COLUMNAS_ORDEN if c in tabla.columns],
    )

    # Actualizar dataset JSON para el dashboard estático
    try:
        from build_dashboard_dataset import build_dataset
        build_dataset()
    except Exception as exc:
        logging.warning(f"No se pudo actualizar el dataset del dashboard: {exc}")

    # Subir información a AIStor
    if mefp_datos and hasattr(mefp_datos, "aistor"):
        try:
            ruta_base = mefp_datos.aistor.repo_prefix()
            reporte_ruta = ruta_base + "/data.parquet"
            mefp_datos.aistor.subir_archivo(ruta_salida_parquet, reporte_ruta)
            logging.info(f"Reporte parquet subido a AIStor: {reporte_ruta}")
        except Exception as exc:
            logging.warning(f"No se pudo subir a AIStor: {exc}")

    metadata = metadata_tabla(tabla)

    return {
        "vuelos_fids_naabol.parquet": {
            "path": ruta_salida_parquet,
            "metadata": metadata,
        }
    }


if __name__ == "__main__":
    try:
        archivos = actualizar()
        datapackage_json = PROJECT_DIR / "datapackage.json"
        if not datapackage_json.exists():
            datapackage_json = PROJECT_DIR.parent / "datapackage.json"

        if sincronizar_datapackage and datapackage_json.exists() and os.getenv("CKAN_URL"):
            try:
                sincronizar_datapackage(str(datapackage_json), archivos, force_update=False)
                print("Proceso de sincronización completado.")
            except Exception as exc:
                logging.warning(f"No se pudo sincronizar con CKAN: {exc}")

        print("Proceso completado exitosamente.")
    except Exception as exc:
        sys.exit(f"Error al obtener o procesar itinerarios FIDS NAABOL: {exc}")
