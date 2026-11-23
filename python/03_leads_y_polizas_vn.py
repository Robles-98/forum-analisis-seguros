"""
PASO 03 - fact_leads + fact_polizas (Venta Nueva)
  · Genera EXACTAMENTE los leads del plan diario, repartidos entre los ejecutivos
    activos de cada campaña ese día (nadie recibe leads antes de su ingreso o después de su baja)
  · Convierte exactamente polizas_objetivo de esos leads, ponderando por habilidad individual
    y experiencia (rampa de 12 meses) -> conversión cuadra 1:1 con fact_leads
  · Aseguradora según el mapa de cada campaña y solo a partir de su fecha de convenio
  · Vehículo del tipo que corresponde a la campaña (Motocicletas=MOTO, Transporte Pesado=TRACTO, ...)
  · Prima por tipo de vehículo, cobertura e inflación; Transporte Pesado con su propia regla
"""
import numpy as np
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED + 3)
print("PASO 03 · Leads y pólizas de Venta Nueva...")

plan = pd.read_csv(f"{cfg.CARPETA_SALIDAS}/plan_diario.csv", parse_dates=["fecha"])
plan = plan[plan["leads_reales"] > 0].reset_index(drop=True)

# ------------------------------------------------------------------ CATÁLOGOS
emp = bd.leer("SELECT id_empleado, id_campana_actual, fecha_ingreso, fecha_baja FROM dim_empleados "
              "WHERE puesto = 'Ejecutivo' AND id_campana_actual IS NOT NULL")
emp["fecha_ingreso"] = cfg.a_fecha(emp["fecha_ingreso"])
emp["fecha_baja"] = cfg.a_fecha(emp["fecha_baja"])
emp["habilidad"] = np.clip(rng.normal(1.0, 0.22, len(emp)), 0.5, 1.7)
HABILIDAD = dict(zip(emp["id_empleado"], emp["habilidad"]))
INGRESO = dict(zip(emp["id_empleado"], emp["fecha_ingreso"]))
EQUIPOS = {c: g for c, g in emp.groupby("id_campana_actual")}

clientes = bd.leer("SELECT id_cliente FROM dim_clientes")["id_cliente"].to_numpy()
veh = bd.leer("SELECT vin, tipo_vehiculo FROM dim_vehiculos")
veh["tipo"] = veh["tipo_vehiculo"].map(cfg.norm)
TIPO_VIN = dict(zip(veh["vin"], veh["tipo"]))

camp = bd.leer("SELECT id_campana, nombre_campana FROM dim_campanas")
NOMBRE = dict(zip(camp["id_campana"], camp["nombre_campana"]))
VINS = {}
for nombre, c in cfg.CAMPANAS.items():
    pool = veh.loc[veh["tipo"].isin(c["vehiculos"]), "vin"].to_numpy()
    if len(pool) == 0:
        raise SystemExit(f"❌ No hay vehículos {c['vehiculos']} para {nombre}")
    VINS[nombre] = pool

aseg = bd.leer("SELECT id_aseguradora, nombre_aseguradora FROM dim_aseguradoras")
aseg["n"] = aseg["nombre_aseguradora"].map(cfg.norm)
ASEG_IDS = aseg["id_aseguradora"].to_numpy()
ASEG_CONV = pd.to_datetime(aseg["n"].map(cfg.CONVENIOS)).to_numpy()
PREFIJO = dict(zip(aseg["id_aseguradora"], aseg["n"].map(lambda n: cfg.PREFIJOS_ASEGURADORA.get(n, n[:3]))))
PESOS_ASEG = {}
for nombre, c in cfg.CAMPANAS.items():
    a = c["aseguradoras"]
    if a == cfg.TODAS:
        w = aseg["n"].map(cfg.PESO_MERCADO).fillna(0.03)
    elif isinstance(a, dict):
        w = aseg["n"].map(a).fillna(0)
    else:
        w = aseg["n"].map(lambda n: cfg.PESO_MERCADO.get(n, 0.03) if n in a else 0)
    PESOS_ASEG[nombre] = w.to_numpy(dtype=float)

cob = bd.leer("SELECT id_cobertura, nombre_cobertura FROM dim_coberturas")
COB_ID = {cfg.norm(n): i for i, n in zip(cob["id_cobertura"], cob["nombre_cobertura"])}


def elegir_cobertura(pesos, n):
    nombres = list(pesos)
    return rng.choice(nombres, size=n, p=np.array(list(pesos.values())) / sum(pesos.values()))


def pesos_forma_pago(anio):
    base = cfg.PESOS_FORMA_PAGO_POR_ANIO.get(anio, cfg.PESOS_FORMA_PAGO_POR_ANIO[2025])
    ruido = {k: max(0.01, v + rng.uniform(-0.05, 0.05)) for k, v in base.items()}
    tot = sum(ruido.values())
    return list(ruido), [v / tot for v in ruido.values()]


col_leads = bd.columnas("fact_leads")
col_pol = [c for c in bd.columnas("fact_polizas") if c != "id_poliza"]
siguiente_lead = 1
tot_leads = tot_pol = 0

# ------------------------------------------------------------------ BUCLE MENSUAL
for periodo, p in plan.groupby(plan["fecha"].dt.to_period("M")):
    p = p.reset_index(drop=True)
    partes = []
    for g, r in p.iterrows():
        e = EQUIPOS[r["id_campana"]]
        activos = e.loc[(e["fecha_ingreso"] <= r["fecha"]) &
                        (e["fecha_baja"].isna() | (e["fecha_baja"] > r["fecha"])), "id_empleado"].to_numpy()
        n = int(r["leads_reales"])
        partes.append(pd.DataFrame({
            "grp": g, "id_campana": r["id_campana"], "dia": r["fecha"],
            "id_empleado_asignado": rng.choice(activos, size=n),
            "vin": rng.choice(VINS[r["campana"]], size=n),
        }))
    L = pd.concat(partes, ignore_index=True)
    n = len(L)
    L["id_lead"] = np.arange(siguiente_lead, siguiente_lead + n)
    siguiente_lead += n
    L["id_cliente"] = rng.choice(clientes, size=n)
    L["origen_lead"] = rng.choice(["Sitio Web", "Facebook", "Google Ads", "WhatsApp"], size=n)
    L["estatus_lead"] = rng.choice(["Contactado", "Cotizado", "No Contesta", "Seguimiento"], size=n)
    L["fecha_contacto"] = (L["dia"] + pd.to_timedelta(rng.integers(9, 19, n), unit="h")
                           + pd.to_timedelta(rng.integers(0, 60, n), unit="m"))

    # ---- Conversión: muestreo ponderado sin reemplazo (Efraimidis-Spirakis) por campaña-día
    antig = (L["fecha_contacto"] - L["id_empleado_asignado"].map(INGRESO)).dt.days / 30.44
    peso = (0.5 + 0.5 * (antig.clip(lower=0) / 12).clip(upper=1)) * L["id_empleado_asignado"].map(HABILIDAD)
    L["_k"] = -np.log(rng.random(n)) / peso.to_numpy()
    L = L.sort_values(["grp", "_k"])
    L["_rank"] = L.groupby("grp").cumcount()
    V = L[L["_rank"] < L["grp"].map(p["polizas_objetivo"])].copy()
    m = len(V)

    # ---- Pólizas
    V["id_empleado"] = V["id_empleado_asignado"]
    V["fecha_emision"] = V["fecha_contacto"] + pd.to_timedelta(rng.integers(0, 6, m), unit="D")
    V["inicio_vigencia"] = V["fecha_emision"]
    V["fin_vigencia"] = V["inicio_vigencia"] + pd.Timedelta(days=365)
    V["nombre"] = V["id_campana"].map(NOMBRE)
    V["tipo_emision"] = "Venta Nueva"
    V["estatus_poliza"] = "Emitida"
    opciones, pesos = pesos_forma_pago(periodo.year)
    V["forma_pago"] = rng.choice(opciones, size=m, p=pesos)

    V["id_aseguradora"] = 0
    V["cob"] = ""
    for nombre, idx in V.groupby("nombre").groups.items():
        fechas = V.loc[idx, "fecha_emision"].to_numpy()[:, None]
        W = PESOS_ASEG[nombre][None, :] * (ASEG_CONV[None, :] <= fechas)
        W = W / W.sum(axis=1, keepdims=True)
        elec = (W.cumsum(axis=1) > rng.random(len(idx))[:, None]).argmax(axis=1)
        V.loc[idx, "id_aseguradora"] = ASEG_IDS[elec]
        pesos_cob = cfg.TRACTO_COBERTURAS if nombre == "Transporte Pesado" else cfg.PESOS_COBERTURA
        V.loc[idx, "cob"] = elegir_cobertura(pesos_cob, len(idx))
    V["id_cobertura"] = V["cob"].map(COB_ID)

    tipo = V["vin"].map(TIPO_VIN)
    rango = tipo.map(lambda t: cfg.RANGO_PRIMA_BASE_POR_TIPO.get(t, (7000.0, 12000.0)))
    prima = (rng.uniform(rango.str[0].to_numpy(float), rango.str[1].to_numpy(float))
             * V["cob"].map(cfg.MULTIPLICADOR_COBERTURA).fillna(1.0).to_numpy())
    es_tracto = (tipo == "TRACTO").to_numpy()
    if es_tracto.any():
        k = es_tracto.sum()
        tramos = cfg.TRACTO_PRIMA_RC
        t = rng.choice(len(tramos), size=k, p=[x[0] for x in tramos])
        base = rng.uniform([tramos[i][1] for i in t], [tramos[i][2] for i in t])
        mult = V.loc[es_tracto, "cob"].map(cfg.TRACTO_MULT_COBERTURA).fillna(1.0).to_numpy()
        prima[es_tracto] = base * mult
    prima = prima * V["fecha_emision"].dt.year.map(cfg.INFLACION_POR_ANIO).fillna(1.0).to_numpy()
    prima[es_tracto] = np.minimum(prima[es_tracto], cfg.TRACTO_PRIMA_MAX)   # tope real: 80 mil anual
    V["prima_neta"] = np.round(prima, 2)
    V["descuento_aplicado"] = np.where(rng.random(m) < 0.15, np.round(V["prima_neta"] * 0.10, 2), 0.0)
    V["iva"] = np.round((V["prima_neta"] - V["descuento_aplicado"]) * 0.16, 2)
    V["prima_total"] = np.round(V["prima_neta"] - V["descuento_aplicado"] + V["iva"], 2)
    V["numero_poliza"] = V["id_aseguradora"].map(PREFIJO) + "-" + V["id_lead"].astype(str)

    bd.insertar(L.sort_values("id_lead")[col_leads], "fact_leads")
    bd.insertar(V.sort_values("fecha_emision")[col_pol], "fact_polizas")
    tot_leads += n
    tot_pol += m
    print(f"  [{periodo}] {n:>7,} leads · {m:>6,} pólizas · conv {m / n:6.2%}")

print(f"  ✔ Total: {tot_leads:,} leads y {tot_pol:,} pólizas de Venta Nueva")
print("PASO 03 listo.\n")
