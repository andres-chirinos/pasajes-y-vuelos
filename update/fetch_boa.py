#!/usr/bin/env python3

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import logging
logging.basicConfig(level=logging.INFO)

# Setup sys.path to find mefp_datos if available
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ROOT_DIR = PROJECT_DIR.parent
if str(ROOT_DIR / "mefp_datos") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "mefp_datos"))

try:
    import mefp_datos
except ImportError:
    mefp_datos = None


BASE_URL = "https://transitabilidad.abc.gob.bo"
API_URL = f"{BASE_URL}/api/v1/data"
TIMEOUT = 30
MAX_FETCH_ATTEMPTS = 5

OUTPUT_COLUMNS = [
    "fecha_consulta",
    "fecha_reporte",
    "fecha_fin",
    "latitud",
    "longitud",
    "estado",
    "sección",
    "evento",
    "clima",
    "horario_de_corte",
    "tipo_de_carretera",
    "alternativa_de_circulación_o_desvios",
    "restricción_vehicular",
    "sector",
    "trabajos_de_conservación_vial",
]

HEADERS = {
    "User-Agent": "Dart/3.5 (dart:io)",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "es-ES, es;q=0.9, en;q=0.8",
}


def normalize(text: str, key: bool = False):
    if key:
        text = text.replace(":", "").replace(" ", "_")
    return text.lower().strip()


def format_columns(df):
    col = {
        "dates": ["fecha_reporte", "fecha_consulta", "fecha_fin"],
        "category": [
            "estado",
            "evento",
            "clima",
            "horario_de_corte",
            "tipo_de_carretera",
            "alternativa_de_circulación_o_desvios",
            "restricción_vehicular",
            "trabajos_de_conservación_vial",
        ],
        "string": ["sección", "sector"],
        "float": ["latitud", "longitud"],
    }
    for field in col["dates"]:
        df[field] = pd.to_datetime(df[field].fillna(pd.NaT))
    df[col["category"]] = df[col["category"]].astype("category")
    df[col["string"]] = df[col["string"]].astype("string")

    df[col["float"]] = (
        df[col["float"]]
        .apply(
            lambda _: (
                _.astype(str).str.strip().apply(lambda __: float(__) if __ else np.nan)
            )
        )
        .round(5)
    )
    return df


def fetch_events():
    api = requests.get(f"{BASE_URL}/api/v1/data", headers=HEADERS)
    if api.status_code == 200:
        return api.json()
    else:
        raise RuntimeError("Error fetching data")


def fetch_events_with_retries():
    last_error = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            return fetch_events()
        except Exception as exc:
            last_error = exc
            if attempt < MAX_FETCH_ATTEMPTS:
                print(f"Intento {attempt} falló: {exc}")
                time.sleep(10)
    raise last_error


def event_to_row(event, now):
    return dict(
        fecha_consulta=now,
        fecha_reporte=event["fecha_registro_hora"],
        fecha_fin="",
        latitud=event["latitud_inicio_seccion"],
        longitud=event["longitud_inicio_seccion"],
        estado=normalize(
            f"{event['estado']['codigo_estado']} - "
            f"{event['estado']['descripcion_estado']}"
        ),
        sección=normalize(f"{event['inicio_seccion']} - {event['fin_seccion']}"),
        evento=normalize(event["evento"]["descripcion_evento"]),
        clima=normalize(event["clima"]["descripcion_clima"]),
        horario_de_corte=normalize(
            event["horario_corte"]["descripcion_horario_de_corte"]
        ),
        tipo_de_carretera=normalize(
            event["tipo_carretera"]["descripcion_tipo_carretera"]
        ),
        alternativa_de_circulación_o_desvios=normalize(
            event["transitable_con_desvio"]["descripcion_transitable_con_desvio"]
        ),
        restricción_vehicular=normalize(
            event["restriccion_vehicular"]["descripcion_restriccion_vehicular"]
        ),
        sector=normalize(event["descr_sector"]) if event["descr_sector"] else "",
        trabajos_de_conservación_vial=normalize(
            event["trabajos_conservacion"]["descripcion_trabajos_conservacion_vial"]
        ),
    )


def get_data(now):
    print("Consultando eventos via API ...")
    events = fetch_events_with_retries()
    print(f"Se registran {len(events)} eventos")

    df = pd.DataFrame(
        [event_to_row(event, now) for event in events],
        columns=OUTPUT_COLUMNS,
    )
    df["fecha_consulta"] = df["fecha_consulta"].dt.tz_localize(None)
    df["fecha_fin"] = ""
    df = format_columns(df)
    return df.sort_values(["fecha_reporte", "sección"])


def consolidate(df, now):
    print("Consolidando eventos ...")
    csv_path = PROJECT_DIR / "data.csv"

    # Intentar descargar versión previa desde AIStor si está disponible
    if mefp_datos and hasattr(mefp_datos, "aistor"):
        try:
            ruta_base = mefp_datos.aistor.repo_prefix()
            reporte_ruta = ruta_base + "/data.parquet"
            if mefp_datos.aistor.existe_objeto(reporte_ruta):
                tmp_aistor_path = "/tmp/aistor_data.parquet"
                mefp_datos.aistor.descargar_objeto(reporte_ruta, tmp_aistor_path)
                oldf = pd.read_parquet(tmp_aistor_path)
                oldf = format_columns(oldf)
            elif csv_path.exists():
                oldf = pd.read_csv(csv_path, na_filter=False)
                oldf = format_columns(oldf)
            else:
                oldf = pd.DataFrame(columns=OUTPUT_COLUMNS)
                oldf = format_columns(oldf)
        except Exception as exc:
            logging.warning(f"No se pudo consultar AIStor, utilizando local data.csv: {exc}")
            if csv_path.exists():
                oldf = pd.read_csv(csv_path, na_filter=False)
                oldf = format_columns(oldf)
            else:
                oldf = pd.DataFrame(columns=OUTPUT_COLUMNS)
                oldf = format_columns(oldf)
    elif csv_path.exists():
        oldf = pd.read_csv(csv_path, na_filter=False)
        oldf = format_columns(oldf)
    else:
        oldf = pd.DataFrame(columns=OUTPUT_COLUMNS)
        oldf = format_columns(oldf)

    compare_cols = ["fecha_reporte", "latitud", "longitud"]
    joindf = pd.concat([oldf, df], axis=0, ignore_index=True)
    duplicates = joindf[joindf.duplicated(subset=compare_cols, keep="last")]

    expired = pd.concat([oldf, duplicates], axis=0, ignore_index=True)
    expired = expired[~expired.duplicated(subset=compare_cols, keep=False)]
    expired.loc[expired["fecha_fin"].isna() | (expired["fecha_fin"] == ""), ["fecha_fin"]] = now.replace(tzinfo=None)

    new = pd.concat([df, duplicates], axis=0, ignore_index=True)
    new = new[~new.duplicated(subset=compare_cols, keep=False)]

    finaldf = pd.concat(
        [expired, duplicates, new], axis=0, ignore_index=True
    ).sort_values(["fecha_reporte", "sección"])
    return format_columns(finaldf)


def write_data(df):
    csv_path = PROJECT_DIR / "data.csv"
    df.to_csv(csv_path, index=False)

    excel_path = "/tmp/transitabilidad_bolivia.xlsx"
    df.to_excel(
        excel_path,
        index=False,
        float_format="%.5f",
        columns=OUTPUT_COLUMNS,
    )

    # Subir información a AIStor
    if mefp_datos and hasattr(mefp_datos, "aistor"):
        try:
            ruta_base = mefp_datos.aistor.repo_prefix()
            reporte_ruta = ruta_base + "/data.parquet"
            tmp_parquet = "/tmp/data.parquet"
            df.to_parquet(tmp_parquet, index=False)
            mefp_datos.aistor.subir_archivo(tmp_parquet, reporte_ruta)
            logging.info(f"Reporte parquet subido a AIStor: {reporte_ruta}")
        except Exception as exc:
            logging.warning(f"No se pudo subir a AIStor: {exc}")

    # Sincronizar con CKAN
    datapackage_json = PROJECT_DIR / "datapackage.json"
    if mefp_datos and hasattr(mefp_datos, "ckan") and datapackage_json.exists():
        try:
            mefp_datos.ckan.sincronizar_datapackage(
                str(datapackage_json),
                {'transitabilidad_bolivia_xlsx': excel_path},
                force_update=True,
            )
        except Exception as exc:
            logging.warning(f"No se pudo sincronizar con CKAN: {exc}")


if __name__ == "__main__":
    now = datetime.now(timezone(timedelta(hours=-4)))
    try:
        data = get_data(now)
        write_data(consolidate(data, now))
        print("Proceso completado exitosamente.")
    except Exception as exc:
        sys.exit(f"Sin acceso al API de transitabilidad: {exc}")
