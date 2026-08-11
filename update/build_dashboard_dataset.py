#!/usr/bin/env python3

import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DOCS_DIR = PROJECT_DIR / "docs"

PASAJES_PARQUET = Path("/tmp/vuelos_pasajes.parquet")
PASAJES_PARQUET_ALT = PROJECT_DIR / "vuelos_pasajes.parquet"

FIDS_PARQUET = Path("/tmp/vuelos_fids_naabol.parquet")
FIDS_PARQUET_ALT = PROJECT_DIR / "vuelos_fids_naabol.parquet"

OUTPUT_JSON = DOCS_DIR / "data_dashboard.json"


def build_dataset():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    pasajes_path = PASAJES_PARQUET if PASAJES_PARQUET.exists() else PASAJES_PARQUET_ALT
    fids_path = FIDS_PARQUET if FIDS_PARQUET.exists() else FIDS_PARQUET_ALT

    pasajes_records = []
    if pasajes_path.exists():
        try:
            df_pasajes = pd.read_parquet(pasajes_path)
            df_pasajes = df_pasajes.fillna("").astype(str)
            pasajes_records = df_pasajes.to_dict(orient="records")
            logging.info(f"Cargados {len(pasajes_records)} registros de pasajes desde {pasajes_path}")
        except Exception as exc:
            logging.warning(f"Error al leer {pasajes_path}: {exc}")

    fids_records = []
    if fids_path.exists():
        try:
            df_fids = pd.read_parquet(fids_path)
            df_fids = df_fids.fillna("").astype(str)
            fids_records = df_fids.to_dict(orient="records")
            logging.info(f"Cargados {len(fids_records)} registros de FIDS desde {fids_path}")
        except Exception as exc:
            logging.warning(f"Error al leer {fids_path}: {exc}")

    dataset = {
        "metadata": {
            "total_pasajes": len(pasajes_records),
            "total_fids": len(fids_records),
            "fechas_pasajes": sorted(list(set(r.get("fecha_salida") for r in pasajes_records if r.get("fecha_salida")))),
            "fechas_fids": sorted(list(set(r.get("FECHA", "").split(" ")[0] for r in fids_records if r.get("FECHA")))),
            "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "pasajes": pasajes_records,
        "fids": fids_records,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False)

    logging.info(f"Archivo de dashboard generado en {OUTPUT_JSON} ({os.path.getsize(OUTPUT_JSON)} bytes)")


if __name__ == "__main__":
    build_dataset()
