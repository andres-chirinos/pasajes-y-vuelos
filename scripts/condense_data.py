#!/usr/bin/env python3

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"


def condense():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_bolivia = datetime.now(timezone(timedelta(hours=-4)))
    hoy_str = now_bolivia.strftime("%Y-%m-%d")

    pasajes_path = DATA_DIR / "vuelos_pasajes.parquet"
    if not pasajes_path.exists():
        pasajes_path = DATA_DIR / "vuelos_pasajes.csv"

    fids_path = DATA_DIR / "vuelos_fids_naabol.parquet"
    if not fids_path.exists():
        fids_path = DATA_DIR / "vuelos_fids_naabol.csv"

    # 1. Procesar Pasajes
    df_pasajes = pd.DataFrame()
    if pasajes_path.exists():
        try:
            if pasajes_path.suffix == ".parquet":
                df_pasajes = pd.read_parquet(pasajes_path)
            else:
                df_pasajes = pd.read_csv(pasajes_path)
            logging.info(f"Cargados {len(df_pasajes)} registros históricos de pasajes.")
        except Exception as exc:
            logging.error(f"Error al leer pasajes: {exc}")

    # 2. Procesar FIDS
    df_fids = pd.DataFrame()
    if fids_path.exists():
        try:
            if fids_path.suffix == ".parquet":
                df_fids = pd.read_parquet(fids_path)
            else:
                df_fids = pd.read_csv(fids_path)
            logging.info(f"Cargados {len(df_fids)} registros históricos de FIDS.")
        except Exception as exc:
            logging.error(f"Error al leer FIDS: {exc}")

    # Condensado 1: Pasajes Activos / Próximas Salidas (últimos 7 días y futuros)
    limite_fecha_pasajes = (now_bolivia - timedelta(days=2)).strftime("%Y-%m-%d")
    df_pasajes_activos = pd.DataFrame()
    if not df_pasajes.empty:
        df_p = df_pasajes.copy()
        df_p["precio_bob"] = pd.to_numeric(df_p["precio_bob"], errors="coerce").fillna(0.0)
        df_p["fecha_salida"] = df_p["fecha_salida"].astype(str)
        
        # Filtrar pasajes recientes y futuros
        df_pasajes_activos = df_p[df_p["fecha_salida"] >= limite_fecha_pasajes].copy()
        
        # En caso de dataset histórico sin salidas futuras recientes, tomar los registros más recientes
        if df_pasajes_activos.empty:
            fechas_disponibles = sorted(df_p["fecha_salida"].unique())
            ultimas_fechas = fechas_disponibles[-5:] if len(fechas_disponibles) >= 5 else fechas_disponibles
            df_pasajes_activos = df_p[df_p["fecha_salida"].isin(ultimas_fechas)].copy()

        # Deduplicar para mantener la última consulta por itinerario
        subset_keys = [
            "tipo_transporte", "fecha_salida", "origen_codigo", "destino_codigo",
            "empresa_aerolinea", "numero_vuelo_bus", "fecha_hora_salida"
        ]
        existing_keys = [k for k in subset_keys if k in df_pasajes_activos.columns]
        df_pasajes_activos = df_pasajes_activos.drop_duplicates(subset=existing_keys, keep="last")
        df_pasajes_activos = df_pasajes_activos.sort_values(
            ["fecha_salida", "tipo_transporte", "origen_nombre", "precio_bob"]
        )

    out_pasajes_activos = DATA_DIR / "condensed_pasajes_activos.csv"
    df_pasajes_activos.to_csv(out_pasajes_activos, index=False, encoding="utf-8")
    logging.info(f"Guardado pasajes activos condensados: {out_pasajes_activos} ({len(df_pasajes_activos)} filas)")

    # Condensado 2: Resumen Agregado de Tarifas por Ruta y Empresa
    df_resumen_rutas = pd.DataFrame()
    if not df_pasajes.empty:
        df_valid_prices = df_pasajes[df_pasajes["precio_bob"] > 0].copy()
        if not df_valid_prices.empty:
            df_resumen_rutas = df_valid_prices.groupby(
                ["tipo_transporte", "origen_nombre", "destino_nombre", "empresa_aerolinea", "categoria_cabina"],
                as_index=False
            ).agg(
                precio_min=("precio_bob", "min"),
                precio_avg=("precio_bob", lambda x: round(x.mean(), 1)),
                precio_max=("precio_bob", "max"),
                total_ofertas=("precio_bob", "count"),
                ultima_fecha_vista=("fecha_salida", "max")
            )
            df_resumen_rutas["ruta"] = df_resumen_rutas["origen_nombre"] + " ➔ " + df_resumen_rutas["destino_nombre"]
            df_resumen_rutas = df_resumen_rutas.sort_values(["ruta", "tipo_transporte", "precio_min"])

    out_resumen_rutas = DATA_DIR / "condensed_resumen_rutas.csv"
    df_resumen_rutas.to_csv(out_resumen_rutas, index=False, encoding="utf-8")
    logging.info(f"Guardado resumen de rutas: {out_resumen_rutas} ({len(df_resumen_rutas)} filas)")

    # Condensado 3: FIDS Operaciones Activas (últimas 48 horas de operaciones)
    df_fids_activos = pd.DataFrame()
    if not df_fids.empty:
        df_f = df_fids.copy()
        # Ordenar por fecha más reciente y mantener últimas operaciones
        if "FECHA_HORA_FORMAT" in df_f.columns:
            df_f = df_f.sort_values("FECHA_HORA_FORMAT", ascending=False)
        elif "fecha_consulta" in df_f.columns:
            df_f = df_f.sort_values("fecha_consulta", ascending=False)

        # Quedarse con las operaciones más recientes (máx 300 eventos)
        df_fids_activos = df_f.head(300).copy()

    out_fids_activos = DATA_DIR / "condensed_fids_activos.csv"
    df_fids_activos.to_csv(out_fids_activos, index=False, encoding="utf-8")
    logging.info(f"Guardado FIDS activos condensados: {out_fids_activos} ({len(df_fids_activos)} filas)")

    # Condensado 4: KPIs Globales
    kpis = {
        "generado_el": now_bolivia.strftime("%Y-%m-%d %H:%M:%S"),
        "total_historico_pasajes": int(len(df_pasajes)),
        "total_historico_fids": int(len(df_fids)),
        "total_pasajes_activos": int(len(df_pasajes_activos)),
        "total_fids_activos": int(len(df_fids_activos)),
        "total_rutas_unicas": int(df_resumen_rutas["ruta"].nunique()) if not df_resumen_rutas.empty else 0,
        "total_empresas": int(df_resumen_rutas["empresa_aerolinea"].nunique()) if not df_resumen_rutas.empty else 0,
        "precio_promedio_general": float(round(df_resumen_rutas["precio_avg"].mean(), 1)) if not df_resumen_rutas.empty else 0.0,
    }
    out_kpis = DATA_DIR / "condensed_kpis.json"
    with open(out_kpis, "w", encoding="utf-8") as f:
        json.dump(kpis, f, ensure_ascii=False, indent=2)
    logging.info(f"Guardado KPIs condensados en {out_kpis}")


if __name__ == "__main__":
    condense()
