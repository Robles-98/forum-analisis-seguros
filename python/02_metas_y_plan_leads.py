"""
PASO 02 - Metas de marketing y plan diario de ventas
Genera:
  · dim_temporadas_altas  (BD)  -> Buen Fin / Hot Sale 2022-2025
  · fact_meta_leads       (BD)  -> meta de marketing por campaña-día (para % cumplimiento en Power BI)
  · salidas/plan_diario.csv     -> leads reales y pólizas objetivo por campaña-día (lo usa el paso 03)

Reglas:
  meta_dia      = meta mensual / días del mes x rampa (HC activo / HC Limit Oper) x 1.20 en temporada
  leads_reales  = min(meta sin temporada, HC activo x 600 / días del mes) x temporada x ruido ±5%
  grandes       = 25-40 pólizas/día (piso 20), escalado por rampa y temporada
  chicas        = conversión entre 70% y 95% de SU meta_conversion
  Recuperacion Web    = conversión 30%-38%, nunca menos de 30%
"""
import numpy as np
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED + 2)
print("PASO 02 · Metas de leads y plan diario...")

# ------------------------------------------------------------------ TEMPORADAS
temp = pd.DataFrame(cfg.TEMPORADAS, columns=["evento", "fecha_inicio", "fecha_fin"])
temp.insert(0, "id_temporada", range(1, len(temp) + 1))
temp["fecha_inicio"] = pd.to_datetime(temp["fecha_inicio"])
temp["fecha_fin"] = pd.to_datetime(temp["fecha_fin"])
temp["factor_incremento"] = cfg.FACTOR_TEMPORADA

cal = pd.DataFrame({"fecha": pd.date_range(cfg.FECHA_INICIO, cfg.FECHA_FIN_VN, freq="D")})
cal["dias_mes"] = cal["fecha"].dt.days_in_month
cal["id_temporada"] = pd.array([pd.NA] * len(cal), dtype="Int64")
for t in temp.itertuples():
    cal.loc[cal["fecha"].between(t.fecha_inicio, t.fecha_fin), "id_temporada"] = t.id_temporada
cal["es_temporada_alta"] = cal["id_temporada"].notna().astype(int)
factor_temp = np.where(cal["es_temporada_alta"] == 1, cfg.FACTOR_TEMPORADA, 1.0)

# ------------------------------------------------------------------ CATÁLOGOS
camp = bd.leer("SELECT id_campana, nombre_campana, meta_conversion FROM dim_campanas")
camp = camp.set_index("nombre_campana")
emp = bd.leer("SELECT id_empleado, id_campana_actual, fecha_ingreso, fecha_baja "
              "FROM dim_empleados WHERE puesto = 'Ejecutivo' AND id_campana_actual IS NOT NULL")
emp["fecha_ingreso"] = cfg.a_fecha(emp["fecha_ingreso"])
emp["fecha_baja"] = cfg.a_fecha(emp["fecha_baja"])

planes = []
for nombre, c in cfg.CAMPANAS.items():
    id_camp = int(camp.loc[nombre, "id_campana"])
    meta_conv = float(camp.loc[nombre, "meta_conversion"])
    e = emp[emp["id_campana_actual"] == id_camp]
    df = cal.copy()
    df["id_campana"] = id_camp
    df["campana"] = nombre
    df["hc_activo"] = cfg.activos_en(df["fecha"], e["fecha_ingreso"], e["fecha_baja"]).sum(axis=1)
    df = df[(df["fecha"] >= pd.Timestamp(c["lanzamiento"])) & (df["hc_activo"] > 0)].copy()
    ft = factor_temp[df.index]
    n = len(df)

    df["factor_rampa"] = np.minimum(df["hc_activo"] / c["hc_limit"], 1.0)
    meta_base = c["meta_leads"] / df["dias_mes"] * df["factor_rampa"]
    df["meta_leads_dia"] = (meta_base * ft).round(2)

    capacidad = df["hc_activo"] * cfg.LEADS_MAX_EJECUTIVO_MES / df["dias_mes"]
    ruido = rng.uniform(*cfg.RUIDO_LEADS_DIA, n)
    df["leads_reales"] = np.round(np.minimum(meta_base, capacidad) * ft * ruido).astype(int)
    leads = df["leads_reales"].to_numpy()

    if c["tipo"] == "grande":
        base = rng.integers(cfg.VENTAS_GRANDES[0], cfg.VENTAS_GRANDES[1] + 1, n)
        esc = df["factor_rampa"].to_numpy() * ft
        pol = np.round(np.maximum(base, cfg.PISO_GRANDES) * esc).astype(int)
    elif c["tipo"] == "oro":
        conv = rng.uniform(*cfg.CONV_ORO, n)
        pol = np.maximum(np.round(leads * conv), np.ceil(leads * cfg.CONV_ORO[0])).astype(int)
    else:
        conv = meta_conv * rng.uniform(*cfg.CUMPL_CHICAS, n)
        pol = rng.binomial(leads, conv)
    df["polizas_objetivo"] = np.minimum(pol, leads)
    planes.append(df)

plan = pd.concat(planes, ignore_index=True)

# ------------------------------------------------------------------ GUARDAR
metas = plan[["fecha", "id_campana", "meta_leads_dia", "es_temporada_alta", "id_temporada"]].copy()
metas["fecha"] = metas["fecha"].dt.date
temp_bd = temp.assign(fecha_inicio=temp["fecha_inicio"].dt.date, fecha_fin=temp["fecha_fin"].dt.date)
bd.reemplazar(temp_bd, "dim_temporadas_altas")
bd.reemplazar(metas, "fact_meta_leads")
plan.drop(columns=["dias_mes"]).to_csv(f"{cfg.CARPETA_SALIDAS}/plan_diario.csv", index=False)

r = plan.assign(anio=plan["fecha"].dt.year).groupby(["campana", "anio"])[["leads_reales", "polizas_objetivo"]].sum()
r["conv_%"] = (r["polizas_objetivo"] / r["leads_reales"] * 100).round(2)
print(r.unstack("anio")["conv_%"].to_string())
print(f"  ✔ {len(metas):,} metas campaña-día · {plan['leads_reales'].sum():,} leads · "
      f"{plan['polizas_objetivo'].sum():,} pólizas planeadas")
print("PASO 02 listo.\n")
