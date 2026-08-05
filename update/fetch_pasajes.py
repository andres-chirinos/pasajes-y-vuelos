#!/usr/bin/env python3

import logging
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

logging.basicConfig(level=logging.INFO)

# Configurar sys.path para mefp_datos
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ROOT_DIR = PROJECT_DIR.parent
if str(ROOT_DIR / "mefp_datos") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "mefp_datos"))

try:
    import mefp_datos
    from mefp_datos.ckan import descargar_recurso, sincronizar_datapackage
except ImportError:
    mefp_datos = None
    sincronizar_datapackage = None
    descargar_recurso = None

AUTH_URL = "https://tsag.transclicksolutions.com/uaa/client"
CITIES_URL = "https://tsag.transclicksolutions.com/sl/api/v1/cities"
FLIGHTS_URL = "https://tsag.transclicksolutions.com/amadeus/api/flights/merge?user_login=%40mobile_todo_pasaje&appType=ANDROID"
BUS_URL = "https://tsag.transclicksolutions.com/sl/api/v1/departures"
BUS_WINDOWS_URL = "https://tsag.transclicksolutions.com/sl/api/v1/departures/windows"

RUTA_SALIDA = Path("/tmp")
MAX_FETCH_ATTEMPTS = 3
REQUEST_DELAY = 0.3  # Pausa en segundos para evitar rate limits

RUTAS_VUELOS = [
    ("LPB", "VVI"),
    ("LPB", "CBB"),
    ("LPB", "TJA"),
    ("LPB", "SRE"),
    ("LPB", "TDD"),
    ("LPB", "CIJ"),
    ("VVI", "LPB"),
    ("VVI", "CBB"),
    ("VVI", "SRE"),
    ("SRE", "LPB"),
    ("CBB", "LPB"),
    ("TJA", "LPB"),
]

COLUMNAS_ORDEN = [
    "fecha_consulta",
    "tipo_transporte",
    "fecha_salida",
    "origen_codigo",
    "origen_nombre",
    "destino_codigo",
    "destino_nombre",
    "empresa_aerolinea",
    "codigo_empresa",
    "numero_vuelo_bus",
    "fecha_hora_salida",
    "fecha_hora_llegada",
    "categoria_cabina",
    "detalles_vehiculo",
    "escalas_duracion",
    "es_escala",
    "numero_escalas",
    "precio_bob",
    "precio_max_bob",
    "precio_minimo_bob",
]

session = requests.Session()
session.verify = False


def obtener_token():
    headers_auth = {
        "User-Agent": "Dart/3.8 (dart:io)",
        "Authorization": "Basic d2lkZ2V0X3RvZG9fcGFzYWplOnRjc193MWRnM3RfdDBkMF9wNHM0ajM=",
        "AuthorizationBasic": "d2lkZ2V0X3RvZG9fcGFzYWplOnRjc193MWRnM3RfdDBkMF9wNHM0ajM=",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data_auth = (
        "grant_type=client_credentials&client_id=widget_todo_pasaje"
        "&username=widget_todo_pasaje&password=tcs_w1dg3t_t0d0_p4s4j3"
    )
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            res = session.post(AUTH_URL, headers=headers_auth, data=data_auth, timeout=15)
            if res.status_code == 200:
                token = res.json().get("access_token")
                logging.info("Token de acceso obtenido exitosamente.")
                return token
        except Exception as exc:
            logging.warning(f"Intento {attempt} de autenticación falló: {exc}")
            time.sleep(2)
    logging.error("No se pudo obtener el token de autenticación.")
    return None


def obtener_ciudades(token):
    headers = {
        "User-Agent": "Dart/3.8 (dart:io)",
        "Authorization": f"Bearer {token}",
        "Access": token,
        "AuthorizationBasic": "bW9iaWxlX3RvZG9fcGFzYWplOnRjc19tMGIxbDNfdDBkMF9wNHM0ajM=",
    }
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            res = session.get(CITIES_URL, headers=headers, timeout=15)
            if res.status_code == 200:
                items = res.json()
                ciudades = sorted(list(set(c.get("city", "").strip() for c in items if c.get("city"))))
                logging.info(f"Se obtuvieron {len(ciudades)} ciudades de la API: {ciudades}")
                return ciudades
        except Exception as exc:
            logging.warning(f"Intento {attempt} de obtener ciudades falló: {exc}")
            time.sleep(2)
    return [
        "LA PAZ", "EL ALTO", "SANTA CRUZ", "COCHABAMBA", "SUCRE", "TARIJA",
        "ORURO", "POTOSI", "BENI", "COBIJA", "TRINIDAD", "UYUNI", "VILLAZON",
        "YACUIBA", "RIBERALTA", "GUAYARAMERIN", "DESAGUADERO", "CAMARGO"
    ]


def generar_rutas_flota(ciudades):
    # Ciudades principales de origen frecuente
    origenes_principales = {
        "LA PAZ", "EL ALTO", "SANTA CRUZ", "COCHABAMBA", "SUCRE", "TARIJA",
        "ORURO", "POTOSI", "TRINIDAD", "COBIJA", "UYUNI", "VILLAZON",
        "YACUIBA", "RIBERALTA", "GUAYARAMERIN", "DESAGUADERO", "CAMARGO"
    }
    rutas = []
    for orig in ciudades:
        if orig in origenes_principales:
            for dest in ciudades:
                if orig != dest:
                    rutas.append((orig, dest))
    return rutas

CIUDAD_A_IATA = {
    "LA PAZ": "LPB",
    "EL ALTO": "LPB",
    "SANTA CRUZ": "VVI",
    "COCHABAMBA": "CBB",
    "SUCRE": "SRE",
    "TARIJA": "TJA",
    "TRINIDAD": "TDD",
    "COBIJA": "CIJ",
    "UYUNI": "UYU",
    "ORURO": "ORU",
    "RIBERALTA": "RIB",
    "GUAYARAMERIN": "GYA",
    "YACUIBA": "BYC",
    "BUENOS AIRES": "EZE",
    "SAO PAULO": "GRU",
    "CUIABA": "CGB",
    "CORDOBA - AR": "COR",
    "MENDOZA - AR": "MDZ",
}


def generar_rutas_vuelos(ciudades):
    iatas = set(["LPB", "VVI", "CBB", "SRE", "TJA", "TDD", "CIJ", "UYU"])
    for c in ciudades:
        c_upper = c.upper().strip()
        if c_upper in CIUDAD_A_IATA:
            iatas.add(CIUDAD_A_IATA[c_upper])

    rutas = []
    lista_iatas = sorted(list(iatas))
    for orig in lista_iatas:
        for dest in lista_iatas:
            if orig != dest:
                rutas.append((orig, dest))
    return rutas


def get_flights_data(token, target_date, now_str, rutas_vuelos):
    headers = {
        "User-Agent": "Dart/3.8 (dart:io)",
        "Authorization": f"Bearer {token}",
        "Access": token,
        "AuthorizationBasic": "bW9iaWxlX3RvZG9fcGFzYWplOnRjc19tMGIxbDNfdDBkMF9wNHM0ajM=",
        "Content-Type": "application/json",
    }
    rows = []
    for orig, dest in rutas_vuelos:
        payload = {
            "adt": 1,
            "chd": 0,
            "inf": 0,
            "hasElderlyPassenger": False,
            "roundTrip": False,
            "cabinId": "Y",
            "origin": orig,
            "destiny": dest,
            "departureDate": target_date,
            "returnDate": target_date,
            "currencyCode": "BOB",
            "marginManagerEnabled": False,
            "agencyId": -1,
            "agencyCode": "",
            "travelInter": False,
        }
        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
            try:
                time.sleep(REQUEST_DELAY)
                res = session.post(FLIGHTS_URL, json=payload, headers=headers, timeout=15)
                if res.status_code == 429:
                    logging.warning("Rate limit (429) detectado en vuelos, pausando 5s...")
                    time.sleep(5)
                    continue
                if res.status_code == 200:
                    data = res.json()
                    groups = data.get("groups", [])
                    for g in groups:
                        price = g.get("priceTotal", 0.0)
                        for fl in g.get("departureFlights", []):
                            airline_info = fl.get("airline", {})
                            orig_info = fl.get("airportOrigin", {})
                            dest_info = fl.get("airportDestiny", {})
                            
                            connections = fl.get("connections", []) or []
                            flight_nums = []
                            intermediate_stops = []
                            for idx, conn in enumerate(connections):
                                fn = conn.get("flightNumber")
                                if fn:
                                    flight_nums.append(str(fn))
                                if idx < len(connections) - 1:
                                    stop_iata = conn.get("destinyAirport", {}).get("iataCode") or conn.get("destinyAirport", {}).get("city")
                                    if stop_iata:
                                        intermediate_stops.append(stop_iata)
                            
                            flight_no_str = " / ".join(flight_nums) if flight_nums else (fl.get("flightNumber") or "")
                            num_stops = max(0, len(connections) - 1)
                            is_stop = num_stops > 0
                            duration_str = fl.get("duration", "")

                            if is_stop:
                                stops_desc = f"{num_stops} escala ({', '.join(intermediate_stops)})" if intermediate_stops else f"{num_stops} escala"
                                if duration_str:
                                    stops_desc += f" - {duration_str}"
                            else:
                                stops_desc = f"Directo ({duration_str})" if duration_str else "Directo"

                            rows.append({
                                "fecha_consulta": now_str,
                                "tipo_transporte": "VUELO",
                                "fecha_salida": target_date,
                                "origen_codigo": orig_info.get("iataCode", orig),
                                "origen_nombre": orig_info.get("city", orig),
                                "destino_codigo": dest_info.get("iataCode", dest),
                                "destino_nombre": dest_info.get("city", dest),
                                "empresa_aerolinea": airline_info.get("name", ""),
                                "codigo_empresa": airline_info.get("iata", ""),
                                "numero_vuelo_bus": flight_no_str,
                                "fecha_hora_salida": fl.get("departureDatetime", ""),
                                "fecha_hora_llegada": fl.get("arrivalDatetime", ""),
                                "categoria_cabina": "ECONOMICA",
                                "detalles_vehiculo": "AVION",
                                "escalas_duracion": stops_desc,
                                "es_escala": is_stop,
                                "numero_escalas": num_stops,
                                "precio_bob": float(price),
                                "precio_max_bob": float(price),
                                "precio_minimo_bob": float(price),
                            })
                    break
            except Exception as exc:
                logging.warning(f"Intento {attempt} falló para vuelo {orig}->{dest}: {exc}")
                time.sleep(1)
    return rows


def get_bus_data(token, target_date, now_str, rutas_flota):
    headers = {
        "User-Agent": "Dart/3.8 (dart:io)",
        "Authorization": f"Bearer {token}",
        "Access": token,
        "AuthorizationBasic": "bW9iaWxlX3RvZG9fcGFzYWplOnRjc19tMGIxbDNfdDBkMF9wNHM0ajM=",
    }
    rows = []
    for orig, dest in rutas_flota:
        for url_endpoint in [BUS_URL, BUS_WINDOWS_URL]:
            params = {
                "date": target_date,
                "origin": orig,
                "destination": dest,
                "seats": 1,
                "enterprise": 0,
                "enableDemo": "false",
                "agencyCode": "",
                "user_login": "null@mobile_todo_pasaje",
            }
            for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
                try:
                    time.sleep(REQUEST_DELAY)
                    res = session.get(url_endpoint, params=params, headers=headers, timeout=15)
                    if res.status_code == 429:
                        logging.warning("Rate limit (429) detectado en flota, pausando 5s...")
                        time.sleep(5)
                        continue
                    if res.status_code == 200:
                        items = res.json()
                        if isinstance(items, list):
                            for item in items:
                                price = float(item.get("price", 0.0))
                                price_max = float(item.get("priceMax", price))
                                price_min = float(item.get("minimum", price))
                                hours = item.get("hours", 0)
                                mins = item.get("minutes", 0)
                                rows.append({
                                    "fecha_consulta": now_str,
                                    "tipo_transporte": "BUS",
                                    "fecha_salida": target_date,
                                    "origen_codigo": item.get("origin", orig),
                                    "origen_nombre": item.get("origin", orig),
                                    "destino_codigo": item.get("destination", dest),
                                    "destino_nombre": item.get("destination", dest),
                                    "empresa_aerolinea": item.get("nameCompany", ""),
                                    "codigo_empresa": str(item.get("company", "")),
                                    "numero_vuelo_bus": str(item.get("codBus", "")) or str(item.get("departureCode", "")),
                                    "fecha_hora_salida": item.get("departureDate", ""),
                                    "fecha_hora_llegada": item.get("arrivalDate", ""),
                                    "categoria_cabina": item.get("category", "") or "",
                                    "detalles_vehiculo": item.get("typeBus", "") or "",
                                    "escalas_duracion": f"Directo ({hours}h {mins}m)",
                                    "es_escala": False,
                                    "numero_escalas": 0,
                                    "precio_bob": price,
                                    "precio_max_bob": price_max,
                                    "precio_minimo_bob": price_min,
                                })
                        break
                except Exception as exc:
                    logging.warning(f"Intento {attempt} falló para flota {orig}->{dest}: {exc}")
                    time.sleep(1)
    return rows


def get_all_pasajes_data(now):
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    token = obtener_token()
    if not token:
        return pd.DataFrame(columns=COLUMNAS_ORDEN)

    ciudades = obtener_ciudades(token)
    rutas_flota = generar_rutas_flota(ciudades)
    rutas_vuelos = generar_rutas_vuelos(ciudades)
    logging.info(f"Generadas {len(rutas_vuelos)} rutas para vuelos y {len(rutas_flota)} rutas para flota terrestre.")

    all_rows = []

    # Consultar para los próximos 3 días
    for day_offset in range(3):
        target_date = (now + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        logging.info(f"Consultando pasajes para la fecha {target_date}...")

        f_rows = get_flights_data(token, target_date, now_str, rutas_vuelos)
        b_rows = get_bus_data(token, target_date, now_str, rutas_flota)

        logging.info(f"Fecha {target_date}: {len(f_rows)} vuelos, {len(b_rows)} pasajes de flota encontrados.")

        all_rows.extend(f_rows)
        all_rows.extend(b_rows)

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
        if col in ["precio_bob", "precio_max_bob", "precio_minimo_bob"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = df[col].astype(str).str.strip().replace(["nan", "None"], "")

    cols = [c for c in COLUMNAS_ORDEN if c in df.columns]
    return df[cols]


def consolidate(df):
    logging.info("Consolidando eventos de pasajes y vuelos...")
    csv_path = PROJECT_DIR / "vuelos_pasajes.csv"
    oldf = pd.DataFrame(columns=COLUMNAS_ORDEN)

    # Intentar descargar versión previa desde CKAN
    if descargar_recurso:
        try:
            ruta_guardado = RUTA_SALIDA / "vuelos_pasajes_guardado.parquet"
            descargar_recurso(
                "vuelos_pasajes",
                "vuelos_pasajes_parquet",
                path=ruta_guardado,
                sobrescribir=True,
            )
            if ruta_guardado.exists():
                oldf = pd.read_parquet(ruta_guardado)
        except Exception as exc:
            logging.info(f"No se pudo descargar recurso previo desde CKAN: {exc}")

    # Fallback a AIStor o local csv
    if oldf.empty and mefp_datos and hasattr(mefp_datos, "aistor"):
        try:
            ruta_base = mefp_datos.aistor.repo_prefix()
            reporte_ruta = ruta_base + "/vuelos_pasajes.parquet"
            if mefp_datos.aistor.existe_objeto(reporte_ruta):
                tmp_aistor_path = RUTA_SALIDA / "aistor_vuelos_pasajes.parquet"
                mefp_datos.aistor.descargar_objeto(reporte_ruta, tmp_aistor_path)
                oldf = pd.read_parquet(tmp_aistor_path)
        except Exception as exc:
            logging.warning(f"No se pudo consultar AIStor: {exc}")

    if oldf.empty and csv_path.exists():
        oldf = pd.read_csv(csv_path, na_filter=False)

    oldf = format_columns(oldf)
    df = format_columns(df)

    compare_cols = [
        "tipo_transporte",
        "fecha_salida",
        "origen_codigo",
        "destino_codigo",
        "empresa_aerolinea",
        "numero_vuelo_bus",
        "fecha_hora_salida",
        "es_escala",
    ]
    joindf = pd.concat([oldf, df], axis=0, ignore_index=True)
    joindf = joindf.drop_duplicates()
    finaldf = joindf.drop_duplicates(subset=compare_cols, keep="last")
    finaldf = finaldf.sort_values(
        ["fecha_salida", "tipo_transporte", "origen_codigo", "fecha_hora_salida"]
    ).reset_index(drop=True)

    return format_columns(finaldf)


def metadata_tabla(tabla):
    timestamps = pd.to_datetime(tabla["fecha_hora_salida"], errors="coerce").dropna()
    if timestamps.empty:
        timestamps = pd.to_datetime(tabla["fecha_consulta"], errors="coerce").dropna()
    return {
        "fecha_minima": timestamps.min().isoformat() if not timestamps.empty else "",
        "fecha_maxima": timestamps.max().isoformat() if not timestamps.empty else "",
        "filas": int(tabla.shape[0]),
    }


def actualizar():
    now = datetime.now(timezone(timedelta(hours=-4)))
    data = get_all_pasajes_data(now)
    tabla = consolidate(data)

    csv_path = PROJECT_DIR / "vuelos_pasajes.csv"
    tabla.to_csv(csv_path, index=False)
    logging.info(f"Guardado local CSV: {csv_path} ({len(tabla)} filas)")

    local_parquet = PROJECT_DIR / "vuelos_pasajes.parquet"
    tabla.to_parquet(local_parquet, index=False)

    ruta_salida_parquet = RUTA_SALIDA / "vuelos_pasajes.parquet"
    tabla.to_parquet(ruta_salida_parquet, index=False)

    excel_path = RUTA_SALIDA / "vuelos_pasajes.xlsx"
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
            reporte_ruta = ruta_base + "/vuelos_pasajes.parquet"
            mefp_datos.aistor.subir_archivo(ruta_salida_parquet, reporte_ruta)
            logging.info(f"Reporte parquet subido a AIStor: {reporte_ruta}")
        except Exception as exc:
            logging.warning(f"No se pudo subir a AIStor: {exc}")

    metadata = metadata_tabla(tabla)

    return {
        "vuelos_pasajes.parquet": {
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
        sys.exit(f"Error al obtener o procesar pasajes y vuelos: {exc}")
