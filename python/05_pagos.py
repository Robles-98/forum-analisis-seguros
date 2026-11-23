"""
PASO 05 - fact_pagos (primer recibo). Es TU script, sin cambios de lógica;
solo usa la conexión compartida y se corre después de Renovaciones.
"""
import numpy as np
import pandas as pd
import os
import config_forum as cfg

bd = cfg.BD()
rng = np.random.default_rng(cfg.SEED + 5)
print("PASO 05 · Primer recibo de cada póliza...")
bd.vaciar("fact_pagos")

df_polizas = bd.leer("""
    SELECT p.id_poliza, p.prima_neta, p.prima_total, p.forma_pago, p.inicio_vigencia, a.nombre_aseguradora
    FROM fact_polizas p JOIN dim_aseguradoras a ON p.id_aseguradora = a.id_aseguradora
""")
recibos = {"Anual": 1, "Semestral": 2, "Trimestral": 4, "Mensual": 12}
div = df_polizas["forma_pago"].map(recibos)
n = len(df_polizas)

df = pd.DataFrame({
    "id_poliza": df_polizas["id_poliza"],
    "numero_recibo": 1,
    "total_recibos": div,
    "monto_recibo": np.round(df_polizas["prima_total"] / div, 2),
    "prima_neta_recibo": np.round(df_polizas["prima_neta"] / div, 2),
    "fecha_limite_pago": cfg.a_fecha(df_polizas["inicio_vigencia"]).dt.normalize(),
})

es_qualitas = (df_polizas["nombre_aseguradora"].map(cfg.norm) == "QUALITAS").to_numpy()
fp = df_polizas["forma_pago"].to_numpy()
metodo = np.empty(n, dtype=object)
metodo[fp == "Mensual"] = "Domiciliación"
m = np.isin(fp, ["Semestral", "Trimestral"])
metodo[m] = rng.choice(["Tarjeta de Débito", "Tarjeta de Crédito"], size=m.sum())
m = (fp == "Anual") & es_qualitas
metodo[m] = rng.choice(["Meses sin Intereses", "Tarjeta de Débito", "Transferencia", "Depósito Bancario",
                        "Pago de Servicios"], size=m.sum(), p=[0.30, 0.20, 0.20, 0.15, 0.15])
m = (fp == "Anual") & ~es_qualitas
metodo[m] = rng.choice(["Meses sin Intereses", "Tarjeta de Débito", "Depósito Bancario", "Pago de Servicios"],
                       size=m.sum(), p=[0.35, 0.25, 0.20, 0.20])
df["metodo_pago"] = metodo

df["estatus_pago"] = rng.choice(["Pagado", "Pagado con Atraso", "Vencido / Impago"], size=n, p=[0.85, 0.10, 0.05])
dias = np.where(df["estatus_pago"] == "Pagado", rng.integers(-3, 1, n),
                np.where(df["estatus_pago"] == "Pagado con Atraso", rng.integers(1, 16, n), 0))
df["fecha_pago_aplicado"] = df["fecha_limite_pago"] + pd.to_timedelta(dias, unit="D")
df.loc[df["estatus_pago"] == "Vencido / Impago", "fecha_pago_aplicado"] = pd.NaT

cols = [c for c in bd.columnas("fact_pagos") if c in df.columns]
bd.insertar(df[cols], "fact_pagos")
print(f"  ✔ {n:,} primeros recibos")
print("PASO 05 listo.\n")
