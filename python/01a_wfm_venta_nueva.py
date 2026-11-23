"""
PASO 01a - Reconstrucción de dim_empleados: Dirección + Venta Nueva
  · Conserva id, nombre y correo de Director, Subgerentes y Coordinadores (solo ajusta fechas y áreas)
  · Crea Gerente y Coordinador de Atención a Clientes si no existen
  · Reconstruye supervisores y ejecutivos de Venta Nueva con el Motor WFM,
    respetando la fecha de lanzamiento y el HC Limit Oper de cada campaña
  · Renovaciones y ATC se construyen en el paso 01b (dependen del volumen de pólizas)
ATENCIÓN: vacía fact_leads, fact_polizas, fact_pagos y fact_atencion_clientes.
"""
import numpy as np
import pandas as pd
import os
import config_forum as cfg
from wfm_comun import Plantilla, simular_equipo

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED)
print("PASO 01a · Motor WFM de Venta Nueva...")

bd.vaciar("fact_atencion_clientes", "fact_pagos", "fact_polizas", "fact_leads")
print("  ✔ Tablas de hechos vaciadas")

emp = bd.leer("SELECT * FROM dim_empleados")
areas = bd.leer("SELECT id_area, nombre_area FROM dim_areas")
AREA = {cfg.norm(n): int(i) for i, n in zip(areas["id_area"], areas["nombre_area"])}
camp = bd.leer("SELECT id_campana, nombre_campana, id_area FROM dim_campanas")
CAMP_ID = dict(zip(camp["nombre_campana"], camp["id_campana"].astype(int)))
CAMP_AREA = dict(zip(camp["nombre_campana"], camp["id_area"].astype(int)))

# ------------------------------------------------------------------ 1. DIRECTIVOS
directivos = emp[emp["puesto"].isin(["Director Comercial", "Subgerente", "Coordinador", "Gerente"])].copy()
directivos["fecha_ingreso"] = cfg.a_fecha(directivos["fecha_ingreso"])
directivos["fecha_baja"] = pd.NaT
director = int(directivos.loc[directivos["puesto"] == "Director Comercial", "id_empleado"].iloc[0])

coords = directivos[directivos["puesto"] == "Coordinador"]
coords_no_atc = coords[coords["id_area"] != AREA[cfg.AREA_ATC]]
subgs = directivos[directivos["puesto"] == "Subgerente"]["id_empleado"].astype(int).tolist()
carga = coords_no_atc["id_supervisor"].value_counts()
sub_vn = int(carga.idxmax())
sub_renov = [s for s in subgs if s != sub_vn][0]
coords_vn = sorted(coords_no_atc.loc[coords_no_atc["id_supervisor"] == sub_vn, "id_empleado"].astype(int))
coords_renov = sorted(coords_no_atc.loc[coords_no_atc["id_supervisor"] == sub_renov, "id_empleado"].astype(int))
if len(coords_vn) != 6 or len(coords_renov) != 2:
    raise SystemExit(f"❌ Esperaba 6 coordinadores de VN y 2 de Renovaciones; encontré {len(coords_vn)} y {len(coords_renov)}")

lanz_grupo = {g: min(pd.Timestamp(c["lanzamiento"]) for c in cfg.CAMPANAS.values() if c["grupo"] == g)
              for g in cfg.GRUPOS}


def fijar(emp_id, area, sup, fecha):
    m = directivos["id_empleado"] == emp_id
    directivos.loc[m, ["id_area", "id_supervisor", "fecha_ingreso", "id_campana_actual"]] = [area, sup, fecha, np.nan]


fijar(director, AREA[cfg.AREA_DIRECCION], np.nan, cfg.FECHA_DIRECCION)
fijar(sub_vn, AREA[cfg.AREA_VENTA_NUEVA], director, cfg.FECHA_DIRECCION)
fijar(sub_renov, AREA[cfg.AREA_RENOVACION], director, cfg.FECHA_SUBGERENTE_RENOV)
for k, c in enumerate(coords_vn):
    arranque = min(lanz_grupo[g] for g, v in cfg.GRUPOS.items() if v["coord"] == k)
    fecha = max(cfg.FECHA_DIRECCION, arranque - pd.Timedelta(days=14))
    area = AREA[cfg.AREA_ECOMMERCE] if k == 5 else AREA[cfg.AREA_VENTA_NUEVA]
    fijar(c, area, sub_vn, fecha)
for c, fecha in zip(coords_renov, cfg.FECHAS_COORD_RENOV):
    fijar(c, AREA[cfg.AREA_RENOVACION], sub_renov, fecha)

plantilla = Plantilla(int(directivos["id_empleado"].max()) + 1, rng, directivos["correo_institucional"])

# Gerente y Coordinador de ATC
gerente_atc = directivos.loc[directivos["puesto"] == "Gerente", "id_empleado"]
if gerente_atc.empty:
    gerente_atc = plantilla.alta("Gerente", AREA[cfg.AREA_ATC], np.nan, director, cfg.ATC_DIRECTIVOS[0][1])
else:
    gerente_atc = int(gerente_atc.iloc[0])
    fijar(gerente_atc, AREA[cfg.AREA_ATC], director, cfg.ATC_DIRECTIVOS[0][1])
coord_atc = coords.loc[coords["id_area"] == AREA[cfg.AREA_ATC], "id_empleado"]
if coord_atc.empty:
    plantilla.alta("Coordinador", AREA[cfg.AREA_ATC], np.nan, gerente_atc, cfg.ATC_DIRECTIVOS[1][1])
else:
    fijar(int(coord_atc.iloc[0]), AREA[cfg.AREA_ATC], gerente_atc, cfg.ATC_DIRECTIVOS[1][1])

# ------------------------------------------------------------------ 2. VENTA NUEVA (WFM)
for grupo, gcfg in cfg.GRUPOS.items():
    unidades = []
    for nombre, c in cfg.CAMPANAS.items():
        if c["grupo"] != grupo:
            continue
        unidades.append(dict(
            id_campana=CAMP_ID[nombre], id_area=CAMP_AREA[nombre], lanzamiento=c["lanzamiento"],
            inicial=max(1, round(c["hc_limit"] * cfg.ARRANQUE_PCT_HC)),
            objetivo=lambda mes, lim=c["hc_limit"]: lim,
        ))
    coord = coords_vn[gcfg["coord"]]
    simular_equipo(plantilla, unidades, gcfg["sup_max"], CAMP_AREA[grupo], CAMP_ID[grupo],
                   coord_de=lambda f, c=coord: c, fecha_fin=cfg.FECHA_FIN_VN)

# ------------------------------------------------------------------ 3. GUARDAR
nuevos = plantilla.a_dataframe()
directivos["estatus"] = "ACTIVO"
final = pd.concat([directivos, nuevos], ignore_index=True)
columnas = bd.columnas("dim_empleados")
final = final[columnas]
for c in ("fecha_ingreso", "fecha_baja"):
    final[c] = cfg.a_fecha(final[c]).dt.date
for c in ("id_supervisor", "id_campana_actual", "id_area"):
    final[c] = final[c].astype("Int64")

bd.vaciar("dim_empleados")
bd.insertar(final.sort_values("id_empleado"), "dim_empleados")

vn = final[(final["puesto"] == "Ejecutivo")]
print(f"  ✔ {len(final):,} empleados guardados ({len(vn):,} ejecutivos de VN históricos)")
print("  HC activo de ejecutivos al cierre de 2025 por campaña:")
activos = vn[vn["fecha_baja"].isna()].merge(camp, left_on="id_campana_actual", right_on="id_campana")
print(activos.groupby("nombre_campana").size().to_string())
print("PASO 01a listo.\n")
