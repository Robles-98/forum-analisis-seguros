"""
PASO 07 - Validación final (solo lectura). Si todo sale en verde, se congelan los datos.
"""
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
pd.set_option("display.width", 200)
print("PASO 07 · Validación\n")

emp = bd.leer("SELECT e.*, a.nombre_area FROM dim_empleados e JOIN dim_areas a ON a.id_area = e.id_area")
for c in ("fecha_ingreso", "fecha_baja"):
    emp[c] = cfg.a_fecha(emp[c])
camp = bd.leer("SELECT id_campana, nombre_campana FROM dim_campanas")
NOMBRE = dict(zip(camp["id_campana"], camp["nombre_campana"]))
leads = bd.leer("SELECT id_campana, id_empleado_asignado, fecha_contacto FROM fact_leads")
leads["fecha_contacto"] = cfg.a_fecha(leads["fecha_contacto"])
pol = bd.leer("""SELECT p.id_campana, p.id_empleado, p.tipo_emision, p.fecha_emision, p.prima_neta,
                        a.nombre_aseguradora, v.tipo_vehiculo
                 FROM fact_polizas p
                 JOIN dim_aseguradoras a ON a.id_aseguradora = p.id_aseguradora
                 JOIN dim_vehiculos v ON v.vin = p.vin""")
pol["fecha_emision"] = cfg.a_fecha(pol["fecha_emision"])
pol["campana"] = pol["id_campana"].map(NOMBRE)
tk = bd.leer("SELECT id_empleado, fecha_apertura FROM fact_atencion_clientes")
tk["fecha_apertura"] = cfg.a_fecha(tk["fecha_apertura"])

errores = 0


def check(nombre, malos):
    global errores
    ok = malos == 0
    errores += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {nombre}: {malos:,}")


def fuera_de_plantilla(df, col_emp, col_fecha):
    m = df.merge(emp[["id_empleado", "fecha_ingreso", "fecha_baja"]], left_on=col_emp, right_on="id_empleado", how="left")
    d = m[col_fecha].dt.normalize()
    return int((m["fecha_ingreso"].isna() | (d < m["fecha_ingreso"]) |
                (m["fecha_baja"].notna() & (d >= m["fecha_baja"]))).sum())


print("Integridad")
check("Leads asignados a alguien fuera de plantilla ese día", fuera_de_plantilla(leads, "id_empleado_asignado", "fecha_contacto"))
vn = pol[pol["tipo_emision"] == "Venta Nueva"]
lanz = {n: pd.Timestamp(c["lanzamiento"]) for n, c in cfg.CAMPANAS.items()}
check("Leads antes del lanzamiento de su campaña",
      int((leads["fecha_contacto"] < leads["id_campana"].map(NOMBRE).map(lanz)).sum()))
ren = pol[pol["tipo_emision"] == "Renovacion"].rename(columns={"id_empleado": "id_emp"})
check("Renovaciones con ejecutivo fuera de plantilla", fuera_de_plantilla(ren, "id_emp", "fecha_emision"))
check("Tickets con ejecutivo fuera de plantilla", fuera_de_plantilla(tk, "id_empleado", "fecha_apertura"))
conv = pd.to_datetime(pol["nombre_aseguradora"].map(cfg.norm).map(cfg.CONVENIOS))
check("Pólizas VN antes del convenio de su aseguradora", int((vn["fecha_emision"].dt.normalize() < conv[vn.index]).sum()))
tipos_ok = vn.apply(lambda r: cfg.norm(r["tipo_vehiculo"]) in cfg.CAMPANAS[r["campana"]]["vehiculos"], axis=1)
check("Pólizas VN con tipo de vehículo que no corresponde a su campaña", int((~tipos_ok).sum()))

print("\nConversión por campaña y año (%)")
l = leads.assign(anio=leads["fecha_contacto"].dt.year, campana=leads["id_campana"].map(NOMBRE))
v = vn.assign(anio=vn["fecha_emision"].dt.year)
t = (v.groupby(["campana", "anio"]).size() / l.groupby(["campana", "anio"]).size() * 100).round(2)
print(t.unstack("anio").to_string())

print("\nHC activo de ejecutivos (jun-2023 / dic-2025)")
ej = emp[emp["puesto"] == "Ejecutivo"]
for f in ("2023-06-15", "2025-12-15"):
    f = pd.Timestamp(f)
    a = ej[(ej["fecha_ingreso"] <= f) & (ej["fecha_baja"].isna() | (ej["fecha_baja"] > f))]
    grupo = a["id_campana_actual"].map(NOMBRE).fillna(a["nombre_area"])
    print(f"  {f.date()}: " + ", ".join(f"{k} {v}" for k, v in grupo.value_counts().items()))

print("\nParticipación de aseguradoras en VN (% por campaña)")
p = pd.crosstab(vn["campana"], vn["nombre_aseguradora"], normalize="index").mul(100).round(1)
print(p.loc[:, (p > 0).any()].to_string())

print("\nPrima neta VN promedio por tipo de vehículo")
print(vn.groupby("tipo_vehiculo")["prima_neta"].describe()[["count", "mean", "min", "max"]].round(0).to_string())

print("\nPólizas por año y tipo de emisión")
print(pol.groupby([pol["fecha_emision"].dt.year, "tipo_emision"]).size().unstack().to_string())

print("\n" + ("✅ TODO EN ORDEN: datos listos para congelar" if errores == 0 else f"❌ {errores} validaciones fallaron"))
