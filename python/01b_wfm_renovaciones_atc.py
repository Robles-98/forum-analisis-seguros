"""
PASO 01b - WFM de Renovaciones y Atención a Clientes (se corre DESPUÉS del paso 03)
El tamaño de cada equipo sale del volumen real de pólizas:
  · Renovaciones: pólizas por vencer el mes siguiente / 250 por ejecutivo (arranca dic-2022)
  · ATC: tickets esperados (75% de las pólizas de los últimos 6 meses) / 450 por ejecutivo
Supervisores: 1 por cada 15 ejecutivos. Renovaciones reporta a sus 2 coordinadores; ATC al suyo.
"""
import math

import numpy as np
import pandas as pd
import os
import config_forum as cfg
from wfm_comun import Plantilla, simular_equipo

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED + 1)
print("PASO 01b · Motor WFM de Renovaciones y ATC...")

emp = bd.leer("SELECT * FROM dim_empleados")
areas = bd.leer("SELECT id_area, nombre_area FROM dim_areas")
AREA = {cfg.norm(n): int(i) for i, n in zip(areas["id_area"], areas["nombre_area"])}
A_REN, A_ATC = AREA[cfg.AREA_RENOVACION], AREA[cfg.AREA_ATC]

# Si se vuelve a correr, borra los equipos operativos de Renovaciones/ATC que ya existan
operativos = emp["puesto"].isin(["Supervisor", "Ejecutivo"]) & emp["id_area"].isin([A_REN, A_ATC])
if operativos.any():
    ids = ",".join(map(str, emp.loc[operativos, "id_empleado"]))
    bd.ejecutar(f"DELETE FROM dim_empleados WHERE id_empleado IN ({ids})")
    emp = emp[~operativos]

coords = emp[emp["puesto"] == "Coordinador"].copy()
coords["fecha_ingreso"] = cfg.a_fecha(coords["fecha_ingreso"])
coords_renov = coords[coords["id_area"] == A_REN].sort_values("id_empleado")
coord_atc = int(coords.loc[coords["id_area"] == A_ATC, "id_empleado"].iloc[0])

# ------------------------------------------------------------------ VOLUMEN ESPERADO
pol = bd.leer("SELECT fecha_emision FROM fact_polizas")
vn = cfg.a_fecha(pol["fecha_emision"]).dt.to_period("M").value_counts()
meses = pd.period_range(cfg.FECHA_INICIO, cfg.FECHA_FIN_SOPORTE, freq="M")
VN = vn.reindex(meses, fill_value=0).astype(float)
REN = pd.Series(0.0, index=meses)          # renovaciones esperadas (bola de nieve)
VENCE = pd.Series(0.0, index=meses)        # pólizas que vencen ese mes
for m in meses:
    if m - 12 in VN.index:
        VENCE[m] = VN[m - 12] + REN[m - 12]
        REN[m] = cfg.TASA_RETENCION * VENCE[m]
TOTAL = VN + REN
TICKETS = cfg.TASA_TICKETS * TOTAL.shift(1).rolling(6, min_periods=1).mean().fillna(0)

obj_renov = {m: max(1, math.ceil(VENCE.get(m + 1, VENCE[m]) / cfg.CAPACIDAD_RENOV)) for m in meses}
obj_atc = {m: max(2, math.ceil(TICKETS[m] / cfg.CAPACIDAD_ATC)) for m in meses}

plantilla = Plantilla(int(emp["id_empleado"].max()) + 1, rng, emp["correo_institucional"])
sups_por_coord = {int(c): 0 for c in coords_renov["id_empleado"]}


def coord_renov(fecha):
    disponibles = coords_renov.loc[coords_renov["fecha_ingreso"] <= fecha, "id_empleado"].astype(int).tolist() \
                  or [int(coords_renov["id_empleado"].iloc[0])]
    c = min(disponibles, key=lambda x: sups_por_coord[x])
    sups_por_coord[c] += 1
    return c


arr_ren = cfg.ARRANQUE_RENOV.to_period("M")
simular_equipo(
    plantilla,
    [dict(id_campana=np.nan, id_area=A_REN, lanzamiento=cfg.ARRANQUE_RENOV,
          inicial=min(obj_renov[arr_ren], max(3, math.ceil(obj_renov[arr_ren] * 0.5))),
          objetivo=lambda ms: obj_renov[ms.to_period("M")])],
    sup_max=99, sup_area=A_REN, sup_campana=np.nan, coord_de=coord_renov, fecha_fin=cfg.FECHA_FIN_SOPORTE,
)
arr_atc = cfg.ARRANQUE_ATC.to_period("M")
simular_equipo(
    plantilla,
    [dict(id_campana=np.nan, id_area=A_ATC, lanzamiento=cfg.ARRANQUE_ATC,
          inicial=obj_atc[arr_atc], objetivo=lambda ms: obj_atc[ms.to_period("M")])],
    sup_max=99, sup_area=A_ATC, sup_campana=np.nan, coord_de=lambda f: coord_atc,
    fecha_fin=cfg.FECHA_FIN_SOPORTE,
)

nuevos = plantilla.a_dataframe()[bd.columnas("dim_empleados")]
for c in ("fecha_ingreso", "fecha_baja"):
    nuevos[c] = cfg.a_fecha(nuevos[c]).dt.date
for c in ("id_supervisor", "id_campana_actual", "id_area"):
    nuevos[c] = nuevos[c].astype("Int64")
bd.insertar(nuevos, "dim_empleados")

for area, nombre in ((A_REN, "Renovaciones"), (A_ATC, "ATC")):
    d = nuevos[nuevos["id_area"] == area]
    print(f"  ✔ {nombre}: {(d['puesto'] == 'Ejecutivo').sum()} ejecutivos y "
          f"{(d['puesto'] == 'Supervisor').sum()} supervisores históricos "
          f"({((d['puesto'] == 'Ejecutivo') & d['fecha_baja'].isna()).sum()} ejecutivos activos al cierre)")
print("PASO 01b listo.\n")
