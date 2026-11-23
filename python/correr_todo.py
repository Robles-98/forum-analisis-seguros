"""
Corre el pipeline completo en orden. Uso:  python correr_todo.py
(haz respaldo de la base antes: se regeneran empleados, leads, pólizas, pagos y tickets)
"""
import os
import runpy
import sys
import time
import os

PASOS = [
    "00_preparar_catalogos.py",
    "01a_wfm_venta_nueva.py",
    "02_metas_y_plan_leads.py",
    "03_leads_y_polizas_vn.py",
    "01b_wfm_renovaciones_atc.py",
    "04_renovaciones.py",
    "05_pagos.py",
    "06_atencion_clientes.py",
    "07_validar.py",
]

aqui = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, aqui)
inicio = time.time()
for paso in PASOS:
    t = time.time()
    runpy.run_path(os.path.join(aqui, paso), run_name="__main__")
    print(f"   ⏱ {paso}: {time.time() - t:,.0f} s\n")
print(f"Pipeline completo en {(time.time() - inicio) / 60:,.1f} min")
