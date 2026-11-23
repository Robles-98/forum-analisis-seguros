"""
PASO 00 - Preparar catálogos
  1. Elimina el área "Cobranza" (si nadie la usa)
  2. Da de alta la campaña "Taxis" (si no existe)
  3. Agrega fecha_inicio_convenio a dim_aseguradoras y la llena
"""
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
print("PASO 00 · Preparando catálogos...")

# 1. Cobranza --------------------------------------------------------------
areas = bd.leer("SELECT id_area, nombre_area FROM dim_areas")
areas["n"] = areas["nombre_area"].map(cfg.norm)
cob = areas[areas["n"] == cfg.AREA_A_ELIMINAR]
if not cob.empty:
    id_cob = int(cob["id_area"].iloc[0])
    usos = (bd.leer(f"SELECT COUNT(*) AS n FROM dim_empleados WHERE id_area = {id_cob}")["n"].iloc[0]
            + bd.leer(f"SELECT COUNT(*) AS n FROM dim_campanas WHERE id_area = {id_cob}")["n"].iloc[0])
    if usos == 0:
        bd.ejecutar(f"DELETE FROM dim_areas WHERE id_area = {id_cob}")
        print(f"  ✔ Área Cobranza (id {id_cob}) eliminada")
    else:
        print(f"  ⚠ Cobranza tiene {usos} registros ligados; no se elimina")
else:
    print("  · Cobranza ya no existe")

id_area = dict(zip(areas["n"], areas["id_area"]))
for requerida in (cfg.AREA_DIRECCION, cfg.AREA_VENTA_NUEVA, cfg.AREA_RENOVACION,
                  cfg.AREA_ECOMMERCE, cfg.AREA_ATC):
    if requerida not in id_area:
        raise SystemExit(f"❌ No encuentro el área '{requerida}' en dim_areas")

# 2. Taxis -----------------------------------------------------------------
camp = bd.leer("SELECT * FROM dim_campanas")
if not (camp["nombre_campana"].map(cfg.norm) == "TAXIS").any():
    nuevo_id = int(camp["id_campana"].max()) + 1
    t = cfg.TAXIS_ALTA
    bd.ejecutar(
        "INSERT INTO dim_campanas (id_campana, nombre_campana, segmento, id_area, meta_conversion) "
        f"VALUES ({nuevo_id}, '{t['nombre_campana']}', '{t['segmento']}', "
        f"{int(id_area[cfg.AREA_VENTA_NUEVA])}, {t['meta_conversion']})"
    )
    print(f"  ✔ Campaña Taxis dada de alta (id {nuevo_id})")
else:
    print("  · Taxis ya existe")

camp = bd.leer("SELECT nombre_campana FROM dim_campanas")
faltan = set(cfg.CAMPANAS) - set(camp["nombre_campana"])
if faltan:
    raise SystemExit(f"❌ Estas campañas de config_forum.py no existen en dim_campanas: {faltan}")

# 3. Convenios -------------------------------------------------------------
if "fecha_inicio_convenio" not in bd.columnas("dim_aseguradoras"):
    bd.ejecutar("ALTER TABLE dim_aseguradoras ADD COLUMN fecha_inicio_convenio DATE NULL")
    print("  ✔ Columna fecha_inicio_convenio agregada")

aseg = bd.leer("SELECT id_aseguradora, nombre_aseguradora FROM dim_aseguradoras")
sin_fecha = []
for r in aseg.itertuples():
    fecha = cfg.CONVENIOS.get(cfg.norm(r.nombre_aseguradora))
    if fecha is None:
        sin_fecha.append(r.nombre_aseguradora)
        continue
    bd.ejecutar(f"UPDATE dim_aseguradoras SET fecha_inicio_convenio = '{fecha}' "
                f"WHERE id_aseguradora = {int(r.id_aseguradora)}")
if sin_fecha:
    raise SystemExit(f"❌ Aseguradoras sin fecha de convenio en config_forum.py: {sin_fecha}")
print(f"  ✔ Fechas de convenio cargadas para {len(aseg)} aseguradoras")
print("PASO 00 listo.\n")
