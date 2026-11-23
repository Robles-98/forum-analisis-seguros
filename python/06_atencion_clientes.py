"""
PASO 06 - fact_atencion_clientes
Se conserva tu lógica (75% de contacto, tipos de solicitud, 1-180 días después de la emisión,
tiempos de cierre). Cambio: cada ticket lo atiende un ejecutivo de Atención a Clientes ACTIVO
el día en que se abrió. Tickets posteriores al cierre del periodo (2026) no se generan.
"""
import numpy as np
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED + 6)
print("PASO 06 · Tickets de Atención a Clientes...")
bd.vaciar("fact_atencion_clientes")

areas = bd.leer("SELECT id_area, nombre_area FROM dim_areas")
A_ATC = int(areas.loc[areas["nombre_area"].map(cfg.norm) == cfg.AREA_ATC, "id_area"].iloc[0])
atc = bd.leer(f"SELECT id_empleado, fecha_ingreso, fecha_baja FROM dim_empleados "
              f"WHERE puesto = 'Ejecutivo' AND id_area = {A_ATC}")
atc["fecha_ingreso"] = cfg.a_fecha(atc["fecha_ingreso"])
atc["fecha_baja"] = cfg.a_fecha(atc["fecha_baja"])

pol = bd.leer("SELECT id_poliza, fecha_emision FROM fact_polizas")
n = int(len(pol) * cfg.TASA_TICKETS)
s = pol.sample(n=n, replace=True, random_state=int(rng.integers(1e9))).reset_index(drop=True)

t = pd.DataFrame({"id_poliza": s["id_poliza"]})
t["tipo_solicitud"] = rng.choice(["SOLICITUD_FACTURA", "ACLARACION_COBRO", "CANCELACION_POLIZA",
                                  "CAMBIO_CONDUCTOR", "ENDOSO_DOMICILIO", "REEXPEDICION"],
                                 size=n, p=[0.45, 0.25, 0.10, 0.10, 0.05, 0.05])
t["fecha_apertura"] = (cfg.a_fecha(s["fecha_emision"]).dt.normalize()
                       + pd.to_timedelta(rng.integers(1, 180, n), unit="D")
                       + pd.to_timedelta(rng.integers(9, 18, n), unit="h")
                       + pd.to_timedelta(rng.integers(0, 60, n), unit="m"))
t = t[t["fecha_apertura"] <= cfg.FECHA_FIN_SOPORTE + pd.Timedelta(hours=23)].reset_index(drop=True)
n = len(t)
t["estatus_ticket"] = rng.choice(["CERRADO", "EN_PROCESO", "ESCALADO"], size=n, p=[0.88, 0.07, 0.05])
t["fecha_cierre"] = t["fecha_apertura"] + pd.to_timedelta(rng.integers(1, 48, n), unit="h")
t.loc[t["estatus_ticket"] != "CERRADO", "fecha_cierre"] = pd.NaT

t["id_empleado"] = 0
for dia, idx in t.groupby(t["fecha_apertura"].dt.normalize()).groups.items():
    act = atc.loc[(atc["fecha_ingreso"] <= dia) & (atc["fecha_baja"].isna() | (atc["fecha_baja"] > dia)),
                  "id_empleado"].to_numpy()
    if len(act) == 0:
        act = atc.iloc[[(atc["fecha_ingreso"] - dia).abs().argmin()]]["id_empleado"].to_numpy()
    t.loc[idx, "id_empleado"] = rng.choice(act, size=len(idx))

cols = [c for c in bd.columnas("fact_atencion_clientes") if c in t.columns]
bd.insertar(t[cols], "fact_atencion_clientes")
print(f"  ✔ {n:,} tickets")
print("PASO 06 listo.\n")
