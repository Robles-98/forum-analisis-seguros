"""
PASO 04 - Renovaciones (bola de nieve 2023-2026)
Se conserva tu lógica: 80% de retención, vigencia en el aniversario, nueva póliza por renovación,
precio -4% para modelos < 2015 y +2% a +5% para el resto, mapeo de campañas de Renovaciones.
Cambios:
  · El ejecutivo se elige entre los de Renovaciones ACTIVOS en la fecha de emisión
  · Mapeo por nombre de campaña (Taxis y cualquier campaña nueva van a Renovaciones Multimarcas)
"""
import numpy as np
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED + 4)
print("PASO 04 · Renovaciones...")

bd.ejecutar("DELETE FROM fact_polizas WHERE tipo_emision = 'Renovacion'")

areas = bd.leer("SELECT id_area, nombre_area FROM dim_areas")
A_REN = int(areas.loc[areas["nombre_area"].map(cfg.norm) == cfg.AREA_RENOVACION, "id_area"].iloc[0])
ren = bd.leer(f"SELECT id_empleado, fecha_ingreso, fecha_baja FROM dim_empleados "
              f"WHERE puesto = 'Ejecutivo' AND id_area = {A_REN}")
ren["fecha_ingreso"] = cfg.a_fecha(ren["fecha_ingreso"])
ren["fecha_baja"] = cfg.a_fecha(ren["fecha_baja"])
if ren.empty:
    raise SystemExit("❌ No hay ejecutivos de Renovaciones. Corre primero el paso 01b.")

camp = bd.leer("SELECT id_campana, nombre_campana FROM dim_campanas")
camp["n"] = camp["nombre_campana"].map(cfg.norm)
es_ren = camp["n"].str.startswith("RENOVACIONES")


def id_renovacion(clave):
    m = camp[es_ren & camp["n"].str.contains(clave)]
    if m.empty:
        raise SystemExit(f"❌ No encuentro la campaña de Renovaciones '{clave}'")
    return int(m["id_campana"].iloc[0])


MAPEO = {}
for r in camp.itertuples():
    if r.n.startswith("RENOVACIONES"):
        MAPEO[r.id_campana] = r.id_campana
    else:
        MAPEO[r.id_campana] = id_renovacion(cfg.RENOVACION_DESTINO.get(r.nombre_campana, cfg.RENOVACION_DEFAULT))

veh = bd.leer("SELECT vin, anio_modelo FROM dim_vehiculos")
ANIO_MODELO = dict(zip(veh["vin"], veh["anio_modelo"]))

cols = [c for c in bd.columnas("fact_polizas") if c != "id_poliza"]
pool = bd.leer(f"SELECT {', '.join(cols)} FROM fact_polizas")
for c in ("fecha_emision", "inicio_vigencia", "fin_vigencia"):
    pool[c] = cfg.a_fecha(pool[c])

for anio in range(2023, cfg.FECHA_FIN_SOPORTE.year + 1):
    vencen = pool[pool["fin_vigencia"].dt.year == anio]
    if vencen.empty:
        continue
    R = vencen.sample(frac=cfg.TASA_RETENCION, random_state=int(rng.integers(1e9))).copy()
    R["inicio_vigencia"] = R["inicio_vigencia"] + pd.DateOffset(years=1)
    R = R[R["inicio_vigencia"] <= cfg.FECHA_FIN_SOPORTE]
    n = len(R)
    R["fecha_emision"] = R["inicio_vigencia"]
    R["fin_vigencia"] = R["inicio_vigencia"] + pd.Timedelta(days=365)
    R["tipo_emision"] = "Renovacion"
    R["estatus_poliza"] = "Emitida"
    R["numero_poliza"] = R["numero_poliza"].astype(str).str.split("-R").str[0] + f"-R{anio}"
    R["id_campana"] = R["id_campana"].map(MAPEO)

    # Ejecutivo de Renovaciones activo el día de la emisión
    R["id_empleado"] = 0
    for dia, idx in R.groupby(R["fecha_emision"].dt.normalize()).groups.items():
        act = ren.loc[(ren["fecha_ingreso"] <= dia) & (ren["fecha_baja"].isna() | (ren["fecha_baja"] > dia)),
                      "id_empleado"].to_numpy()
        if len(act) == 0:   # respaldo: el que entró más cerca de esa fecha
            act = ren.iloc[[(ren["fecha_ingreso"] - dia).abs().argmin()]]["id_empleado"].to_numpy()
        R.loc[idx, "id_empleado"] = rng.choice(act, size=len(idx))

    antiguo = (R["vin"].map(ANIO_MODELO) < 2015).to_numpy()
    factor = np.where(antiguo, 0.96, 1 + rng.uniform(0.02, 0.05, n))
    R["prima_neta"] = np.round(R["prima_neta"] * factor, 2)
    R["descuento_aplicado"] = 0.0
    R["iva"] = np.round(R["prima_neta"] * 0.16, 2)
    R["prima_total"] = np.round(R["prima_neta"] + R["iva"], 2)

    bd.insertar(R[cols].sort_values("fecha_emision"), "fact_polizas")
    pool = pd.concat([pool, R[cols]], ignore_index=True)
    print(f"  [{anio}] {len(vencen):,} vencen -> {n:,} renovadas")

print("PASO 04 listo.\n")
