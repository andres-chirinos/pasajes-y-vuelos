#!/usr/bin/env python3

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

AEROPUERTOS = [
    "El ALTo", "Viru Viru", "Jorge Wilstermann", "Sucre", "Tarija", "Trinidad",
    "Uyuni", "Oruro", "Potosi", "Cobija", "Riberalta", "Rurrenabaque", "Guayamerin", "Yacuiba"
]

SESSION_URL = "https://fids.naabol.gob.bo/"
BASE_URL = "https://fids.naabol.gob.bo/Fids/itin/vuelos"
MAX_FETCH_ATTEMPTS = 3
REQUEST_TIMEOUT = 30  # Timeout en segundos para requests HTTP

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
        res = session.get(SESSION_URL, timeout=REQUEST_TIMEOUT)
        logging.info(f"Cookies obtenidas: {list(session.cookies.keys())}")
    except Exception as exc:
        logging.warning(f"No se pudieron obtener cookies iniciales: {exc}")


def _get_data(aero, tipo, now_str):
    params = {"aero": aero, "tipo": tipo}
    last_error = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            response = session.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
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
        df[col] = df[col].astype(str).str.strip().replace(["nan", "None", "<NA>"], "")

    if "RUTA0" in df.columns:
        df = df[df["RUTA0"] != ""].reset_index(drop=True)

    cols = [c for c in COLUMNAS_ORDEN if c in df.columns]
    return df[cols]


def consolidate(df, data_dir: Path):
    logging.info("Consolidando eventos de vuelos FIDS...")
    oldf = pd.DataFrame(columns=COLUMNAS_ORDEN)

    candidates = [
        data_dir / "vuelos_fids_naabol.parquet",
        PROJECT_DIR / "vuelos_fids_naabol.parquet",
        data_dir / "vuelos_fids_naabol.csv",
    ]

    for cand in candidates:
        if cand.exists() and oldf.empty:
            try:
                if cand.suffix == ".parquet":
                    oldf = pd.read_parquet(cand)
                elif cand.suffix == ".csv":
                    oldf = pd.read_csv(cand, dtype=str)
                logging.info(f"Datos previos cargados desde {cand} ({len(oldf)} filas)")
                break
            except Exception as exc:
                logging.warning(f"No se pudo leer archivo previo {cand}: {exc}")

    oldf = format_columns(oldf)
    df = format_columns(df)

    compare_cols = ["FECHA_HORA_FORMAT", "AEROPUERTO", "TIPO_OPERACION", "NRO_VUELO"]
    joindf = pd.concat([oldf, df], axis=0, ignore_index=True)
    joindf = joindf.drop_duplicates()
    finaldf = joindf.drop_duplicates(subset=compare_cols, keep="last")
    finaldf = finaldf.sort_values(["FECHA_HORA_FORMAT", "AEROPUERTO", "NRO_VUELO"]).reset_index(drop=True)

    return format_columns(finaldf)


def save_dataframe(df, base_filename, data_dir: Path, execution_id: str, output_formats: list[str]):
    if df.empty:
        logging.info(f"No hay datos para guardar en {base_filename}")
        return

    for fmt in output_formats:
        fmt = fmt.strip().lower()
        filename = f"{base_filename}_{execution_id}.{fmt}" if execution_id else f"{base_filename}.{fmt}"
        filepath = data_dir / filename

        if fmt == "csv":
            df.to_csv(filepath, index=False, encoding="utf-8")
        elif fmt == "parquet":
            df.columns = df.columns.astype(str)
            df.to_parquet(filepath, index=False)
        elif fmt in ["xlsx", "excel"]:
            df.to_excel(filepath, index=False, columns=[c for c in COLUMNAS_ORDEN if c in df.columns])
        else:
            logging.warning(f"Formato no soportado: {fmt}")
            continue

        logging.info(f"Guardado exitosamente: {filepath} ({len(df)} registros)")


def actualizar(data_dir: Path = None, output_formats: list[str] = None, execution_id: str = ""):
    if data_dir is None:
        data_dir = PROJECT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if output_formats is None:
        output_formats = ["parquet", "csv"]

    now_str = datetime.now(timezone(timedelta(hours=-4))).strftime("%Y-%m-%d %H:%M:%S")
    data = get_all_fids_data(now_str)
    tabla = consolidate(data, data_dir)

    save_dataframe(
        df=tabla,
        base_filename="vuelos_fids_naabol",
        data_dir=data_dir,
        execution_id=execution_id,
        output_formats=output_formats,
    )

    # Actualizar dataset JSON para el dashboard estático si el módulo existe
    try:
        from build_dashboard_dataset import build_dataset
        build_dataset()
    except Exception:
        try:
            from scripts.build_dashboard_dataset import build_dataset
            build_dataset()
        except Exception:
            pass

    return tabla


def main():
    parser = argparse.ArgumentParser(
        description="Extrae itinerarios FIDS de NAABOL, consolida y guarda en formatos especificados."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_DIR / "data",
        help="Directorio donde guardar los datos. Default: data/",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="parquet,csv",
        help="Formatos de salida separados por coma (csv, parquet, xlsx). Default: parquet,csv",
    )
    parser.add_argument(
        "--append-timestamp",
        action="store_true",
        help="Añadir marca de tiempo al nombre del archivo de salida.",
    )
    args = parser.parse_args()

    execution_id = datetime.now().strftime("%Y%m%d_%H%M%S") if args.append_timestamp else ""
    output_formats = [f.strip().lower() for f in args.format.split(",")]

    try:
        actualizar(
            data_dir=args.data_dir,
            output_formats=output_formats,
            execution_id=execution_id,
        )
        logging.info("Extracción de FIDS completada exitosamente.")
    except Exception as exc:
        sys.exit(f"Error al obtener o procesar itinerarios FIDS NAABOL: {exc}")


if __name__ == "__main__":
    main()
