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

# Tarifas Máximas de Referencia (TMR) - Transporte Aéreo Doméstico de Pasajeros (En Bs.)
TARIFAS_REFERENCIA_VUELOS = {
    ("LPB", "CBB"): {"origen": "La Paz", "destino": "Cochabamba", "tmr": 539.0, "dua": 15.0, "valor_billete": 554.0},
    ("CBB", "LPB"): {"origen": "Cochabamba", "destino": "La Paz", "tmr": 539.0, "dua": 15.0, "valor_billete": 554.0},
    ("LPB", "VVI"): {"origen": "La Paz", "destino": "Santa Cruz", "tmr": 1103.0, "dua": 15.0, "valor_billete": 1118.0},
    ("VVI", "LPB"): {"origen": "Santa Cruz", "destino": "La Paz", "tmr": 1103.0, "dua": 15.0, "valor_billete": 1118.0},
    ("CBB", "VVI"): {"origen": "Cochabamba", "destino": "Santa Cruz", "tmr": 698.0, "dua": 15.0, "valor_billete": 713.0},
    ("VVI", "CBB"): {"origen": "Santa Cruz", "destino": "Cochabamba", "tmr": 698.0, "dua": 15.0, "valor_billete": 713.0},
    ("LPB", "SRE"): {"origen": "La Paz", "destino": "Sucre", "tmr": 773.0, "dua": 15.0, "valor_billete": 788.0},
    ("SRE", "LPB"): {"origen": "Sucre", "destino": "La Paz", "tmr": 773.0, "dua": 15.0, "valor_billete": 788.0},
    ("LPB", "TJA"): {"origen": "La Paz", "destino": "Tarija", "tmr": 1143.0, "dua": 15.0, "valor_billete": 1158.0},
    ("TJA", "LPB"): {"origen": "Tarija", "destino": "La Paz", "tmr": 1143.0, "dua": 15.0, "valor_billete": 1158.0},
    ("SRE", "VVI"): {"origen": "Sucre", "destino": "Santa Cruz", "tmr": 566.0, "dua": 15.0, "valor_billete": 581.0},
    ("VVI", "SRE"): {"origen": "Santa Cruz", "destino": "Sucre", "tmr": 566.0, "dua": 15.0, "valor_billete": 581.0},
    ("TJA", "VVI"): {"origen": "Tarija", "destino": "Santa Cruz", "tmr": 948.0, "dua": 15.0, "valor_billete": 963.0},
    ("VVI", "TJA"): {"origen": "Santa Cruz", "destino": "Tarija", "tmr": 948.0, "dua": 15.0, "valor_billete": 963.0},
    ("LPB", "TDD"): {"origen": "La Paz", "destino": "Trinidad", "tmr": 1340.0, "dua": 15.0, "valor_billete": 1355.0},
    ("TDD", "LPB"): {"origen": "Trinidad", "destino": "La Paz", "tmr": 1340.0, "dua": 15.0, "valor_billete": 1355.0},
    ("TDD", "VVI"): {"origen": "Trinidad", "destino": "Santa Cruz", "tmr": 1186.0, "dua": 15.0, "valor_billete": 1201.0},
    ("VVI", "TDD"): {"origen": "Santa Cruz", "destino": "Trinidad", "tmr": 1186.0, "dua": 15.0, "valor_billete": 1201.0},
    ("LPB", "RBQ"): {"origen": "La Paz", "destino": "Rurrenabaque", "tmr": 918.0, "dua": 15.0, "valor_billete": 933.0},
    ("RBQ", "LPB"): {"origen": "Rurrenabaque", "destino": "La Paz", "tmr": 918.0, "dua": 15.0, "valor_billete": 933.0},
    ("LPB", "CIJ"): {"origen": "La Paz", "destino": "Cobija", "tmr": 1537.0, "dua": 15.0, "valor_billete": 1552.0},
    ("CIJ", "LPB"): {"origen": "Cobija", "destino": "La Paz", "tmr": 1537.0, "dua": 15.0, "valor_billete": 1552.0},
    ("CBB", "TJA"): {"origen": "Cochabamba", "destino": "Tarija", "tmr": 862.0, "dua": 15.0, "valor_billete": 877.0},
    ("TJA", "CBB"): {"origen": "Tarija", "destino": "Cochabamba", "tmr": 862.0, "dua": 15.0, "valor_billete": 877.0},
    ("CBB", "SRE"): {"origen": "Cochabamba", "destino": "Sucre", "tmr": 524.0, "dua": 15.0, "valor_billete": 539.0},
    ("SRE", "CBB"): {"origen": "Sucre", "destino": "Cochabamba", "tmr": 524.0, "dua": 15.0, "valor_billete": 539.0},
    ("CBB", "TDD"): {"origen": "Cochabamba", "destino": "Trinidad", "tmr": 639.0, "dua": 15.0, "valor_billete": 654.0},
    ("TDD", "CBB"): {"origen": "Trinidad", "destino": "Cochabamba", "tmr": 639.0, "dua": 15.0, "valor_billete": 654.0},
    ("SRE", "TJA"): {"origen": "Sucre", "destino": "Tarija", "tmr": 578.0, "dua": 15.0, "valor_billete": 593.0},
    ("TJA", "SRE"): {"origen": "Tarija", "destino": "Sucre", "tmr": 578.0, "dua": 15.0, "valor_billete": 593.0},
    ("LPB", "PSZ"): {"origen": "La Paz", "destino": "Puerto Suarez", "tmr": 1653.0, "dua": 15.0, "valor_billete": 1668.0},
    ("PSZ", "LPB"): {"origen": "Puerto Suarez", "destino": "La Paz", "tmr": 1653.0, "dua": 15.0, "valor_billete": 1668.0},
    ("CBB", "PSZ"): {"origen": "Cochabamba", "destino": "Puerto Suarez", "tmr": 521.0, "dua": 15.0, "valor_billete": 536.0},
    ("PSZ", "CBB"): {"origen": "Puerto Suarez", "destino": "Cochabamba", "tmr": 521.0, "dua": 15.0, "valor_billete": 536.0},
    ("LPB", "UYU"): {"origen": "La Paz", "destino": "Uyuni", "tmr": 1430.0, "dua": 15.0, "valor_billete": 1445.0},
    ("UYU", "LPB"): {"origen": "Uyuni", "destino": "La Paz", "tmr": 1430.0, "dua": 15.0, "valor_billete": 1445.0},
    ("ORU", "VVI"): {"origen": "Oruro", "destino": "Santa Cruz", "tmr": 972.0, "dua": 15.0, "valor_billete": 987.0},
    ("VVI", "ORU"): {"origen": "Santa Cruz", "destino": "Oruro", "tmr": 972.0, "dua": 15.0, "valor_billete": 987.0},
    ("CBB", "ORU"): {"origen": "Cochabamba", "destino": "Oruro", "tmr": 582.0, "dua": 15.0, "valor_billete": 597.0},
    ("ORU", "CBB"): {"origen": "Oruro", "destino": "Cochabamba", "tmr": 582.0, "dua": 15.0, "valor_billete": 597.0},
    ("TDD", "RIB"): {"origen": "Trinidad", "destino": "Riberalta", "tmr": 1005.0, "dua": 15.0, "valor_billete": 1020.0},
    ("RIB", "TDD"): {"origen": "Riberalta", "destino": "Trinidad", "tmr": 1005.0, "dua": 15.0, "valor_billete": 1020.0},
    ("TDD", "GYA"): {"origen": "Trinidad", "destino": "Guayaramerín", "tmr": 989.0, "dua": 15.0, "valor_billete": 1004.0},
    ("GYA", "TDD"): {"origen": "Guayaramerín", "destino": "Trinidad", "tmr": 989.0, "dua": 15.0, "valor_billete": 1004.0},
}

# ATT-DJ-RAR-TR LP 32 2025 - Banda Tarifaria Transporte Terrestre Interdepartamental
BANDAS_TARIFARIAS_BUSES = [
    {"origen": "COCHABAMBA", "destino": "SANTA CRUZ", "detalle": "nueva carretera (n)", "normal": (70, 90), "semicama": (92, 125), "cama": (148, 183)},
    {"origen": "COCHABAMBA", "destino": "SANTA CRUZ", "detalle": "carretera antigua (a)", "normal": (87, 106), "semicama": (106, 143), "cama": (162, 207)},
    {"origen": "COCHABAMBA", "destino": "ORURO", "detalle": "", "normal": (29, 43), "semicama": (36, 56), "cama": (85, 95)},
    {"origen": "COCHABAMBA", "destino": "SUCRE", "detalle": "", "normal": (67, 94), "semicama": (78, 123), "cama": (148, 192)},
    {"origen": "COCHABAMBA", "destino": "POTOSI", "detalle": "", "normal": (67, 87), "semicama": (106, 129), "cama": (162, 186)},
    {"origen": "COCHABAMBA", "destino": "TARIJA", "detalle": "", "normal": (155, 183), "semicama": (190, 246), "cama": (288, 358)},
    {"origen": "COCHABAMBA", "destino": "UYUNI", "detalle": "", "normal": (95, 140), "semicama": (141, 203), "cama": (211, 291)},
    {"origen": "LA PAZ", "destino": "ORURO", "detalle": "", "normal": (27, 39), "semicama": (36, 53), "cama": (78, 85)},
    {"origen": "LA PAZ", "destino": "COCHABAMBA", "detalle": "", "normal": (55, 73), "semicama": (78, 102), "cama": (120, 148)},
    {"origen": "LA PAZ", "destino": "SANTA CRUZ", "detalle": "nueva carretera (n)", "normal": (113, 153), "semicama": (176, 224), "cama": (232, 308)},
    {"origen": "LA PAZ", "destino": "SANTA CRUZ", "detalle": "carretera antigua (a)", "normal": (127, 161), "semicama": (190, 234), "cama": (246, 319)},
    {"origen": "LA PAZ", "destino": "POTOSI", "detalle": "", "normal": (67, 88), "semicama": (106, 129), "cama": (148, 181)},
    {"origen": "LA PAZ", "destino": "SUCRE", "detalle": "", "normal": (91, 126), "semicama": (120, 175), "cama": (183, 252)},
    {"origen": "LA PAZ", "destino": "TARIJA", "detalle": "", "normal": (155, 185), "semicama": (190, 248), "cama": (295, 363)},
    {"origen": "LA PAZ", "destino": "VILLAZON", "detalle": "", "normal": (155, 185), "semicama": (190, 248), "cama": (274, 351)},
    {"origen": "LA PAZ", "destino": "UYUNI", "detalle": "", "normal": (95, 133), "semicama": (140, 192), "cama": (211, 276)},
    {"origen": "ORURO", "destino": "POTOSI", "detalle": "", "normal": (38, 53), "semicama": (57, 74), "cama": (85, 105)},
    {"origen": "ORURO", "destino": "SUCRE", "detalle": "", "normal": (64, 88), "semicama": (78, 118), "cama": (127, 175)},
    {"origen": "ORURO", "destino": "UYUNI", "detalle": "", "normal": (55, 69), "semicama": (98, 106), "cama": (148, 154)},
    {"origen": "ORURO", "destino": "VILLAZON", "detalle": "", "normal": (115, 143), "semicama": (0, 0), "cama": (0, 0)},
    {"origen": "ORURO", "destino": "TARIJA", "detalle": "", "normal": (118, 144), "semicama": (0, 0), "cama": (0, 0)},
    {"origen": "POTOSI", "destino": "SUCRE", "detalle": "", "normal": (18, 29), "semicama": (29, 43), "cama": (43, 60)},
    {"origen": "POTOSI", "destino": "TARIJA", "detalle": "", "normal": (78, 102), "semicama": (92, 134), "cama": (127, 186)},
    {"origen": "SANTA CRUZ", "destino": "TRINIDAD", "detalle": "", "normal": (69, 87), "semicama": (106, 127), "cama": (169, 188)},
    {"origen": "SANTA CRUZ", "destino": "YACUIBA", "detalle": "", "normal": (66, 85), "semicama": (106, 127), "cama": (148, 176)},
    {"origen": "SANTA CRUZ", "destino": "SUCRE", "detalle": "", "normal": (106, 134), "semicama": (120, 176), "cama": (148, 238)},
    {"origen": "SANTA CRUZ", "destino": "TARIJA", "detalle": "", "normal": (143, 183), "semicama": (211, 266), "cama": (258, 356)},
    {"origen": "SUCRE", "destino": "UYUNI", "detalle": "", "normal": (64, 83), "semicama": (92, 116), "cama": (141, 167)},
    {"origen": "TARIJA", "destino": "VILLAZON", "detalle": "", "normal": (52, 63), "semicama": (0, 0), "cama": (0, 0)},
    {"origen": "TARIJA", "destino": "SUCRE", "detalle": "", "normal": (111, 139), "semicama": (0, 0), "cama": (0, 0)},
]

def obtener_rutas_flota():
    rutas = set()
    for b in BANDAS_TARIFARIAS_BUSES:
        orig = b["origen"].strip().upper()
        dest = b["destino"].strip().upper()
        rutas.add((orig, dest))
        rutas.add((dest, orig))
    return sorted(list(rutas))

RUTAS_VUELOS = list(TARIFAS_REFERENCIA_VUELOS.keys())
RUTAS_FLOTA = obtener_rutas_flota()

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

    logging.info(f"Rutas predefinidas: {len(RUTAS_VUELOS)} rutas de vuelo y {len(RUTAS_FLOTA)} rutas de flota terrestre.")

    all_rows = []

    # Consultar para los próximos 3 días
    for day_offset in range(3):
        target_date = (now + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        logging.info(f"Consultando pasajes para la fecha {target_date}...")

        f_rows = get_flights_data(token, target_date, now_str, RUTAS_VUELOS)
        b_rows = get_bus_data(token, target_date, now_str, RUTAS_FLOTA)

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
    oldf = pd.DataFrame(columns=COLUMNAS_ORDEN)

    # Intentar descargar versión previa desde CKAN
    if descargar_recurso:
        try:
            ruta_guardado = RUTA_SALIDA / "vuelos_pasajes_guardado.parquet"
            descargar_recurso(
                "vuelos",
                "vuelos_pasajes.parquet",
                path=ruta_guardado,
                sobrescribir=True,
            )
            if ruta_guardado.exists():
                oldf = pd.read_parquet(ruta_guardado)
        except Exception as exc:
            logging.info(f"No se pudo descargar recurso previo desde CKAN: {exc}")

    # Fallback a AIStor o local parquet/csv
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

    local_parquet = PROJECT_DIR / "vuelos_pasajes.parquet"
    if oldf.empty and local_parquet.exists():
        try:
            oldf = pd.read_parquet(local_parquet)
        except Exception:
            pass

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

    ruta_salida_parquet = RUTA_SALIDA / "vuelos_pasajes.parquet"
    tabla.to_parquet(ruta_salida_parquet, index=False)

    excel_path = RUTA_SALIDA / "vuelos_pasajes.xlsx"
    tabla.to_excel(
        excel_path,
        index=False,
        columns=[c for c in COLUMNAS_ORDEN if c in tabla.columns],
    )

    # Actualizar dataset JSON para el dashboard estático si está presente
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
