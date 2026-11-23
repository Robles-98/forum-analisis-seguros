"""
CONFIGURACIÓN COMPARTIDA - Forum Global Seguros
===============================================
Única fuente de verdad para todos los scripts del pipeline.
Si quieres mover una fecha, una meta o un HC, cámbialo AQUÍ y vuelve a correr todo.
"""
import os
import unicodedata

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- CONEXIÓN
CONN_STR = os.environ.get("FORUM_CONN")
if not CONN_STR:
    raise RuntimeError("Falta la variable de entorno FORUM_CONN")

SEED = 42
CARPETA_SALIDAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salidas")
os.makedirs(CARPETA_SALIDAS, exist_ok=True)

FECHA_INICIO      = pd.Timestamp("2022-01-01")
FECHA_FIN_VN      = pd.Timestamp("2025-12-31")   # último día con leads / venta nueva
FECHA_FIN_SOPORTE = pd.Timestamp("2026-12-31")   # Renovaciones y ATC siguen operando en 2026


# ---------------------------------------------------------------- CAPA DE BASE DE DATOS
class BD:
    """Envoltura mínima: MySQL vía SQLAlchemy (tu caso) o sqlite3 (solo pruebas)."""

    def __init__(self, conn_str=CONN_STR):
        self.sqlite = conn_str.startswith("sqlite3:")
        if self.sqlite:
            import sqlite3
            self.con = sqlite3.connect(conn_str.split(":", 1)[1])
        else:
            from sqlalchemy import create_engine
            self.engine = create_engine(conn_str)

    def leer(self, sql):
        if self.sqlite:
            return pd.read_sql(sql, self.con)
        return pd.read_sql(sql, self.engine)

    def ejecutar(self, *sentencias):
        if self.sqlite:
            for s in sentencias:
                self.con.execute(s)
            self.con.commit()
            return
        from sqlalchemy import text
        with self.engine.begin() as conn:
            for s in sentencias:
                conn.execute(text(s))

    def columnas(self, tabla):
        return self.leer(f"SELECT * FROM {tabla} LIMIT 0").columns.tolist()

    def vaciar(self, *tablas):
        """TRUNCATE (reinicia autoincrementos) con llaves foráneas desactivadas."""
        if self.sqlite:
            self.ejecutar(*[f"DELETE FROM {t}" for t in tablas])
            return
        self.ejecutar("SET FOREIGN_KEY_CHECKS = 0",
                      *[f"TRUNCATE TABLE {t}" for t in tablas],
                      "SET FOREIGN_KEY_CHECKS = 1")

    def insertar(self, df, tabla, chunksize=10000):
        """Append respetando la estructura existente de la tabla (no la recrea)."""
        if df.empty:
            return
        if self.sqlite:
            df.to_sql(tabla, self.con, if_exists="append", index=False, chunksize=chunksize)
            return
        from sqlalchemy import text
        with self.engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            df.to_sql(tabla, conn, if_exists="append", index=False,
                      chunksize=chunksize, method="multi")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    def reemplazar(self, df, tabla):
        """Solo para tablas NUEVAS del pipeline (temporadas, metas)."""
        if self.sqlite:
            df.to_sql(tabla, self.con, if_exists="replace", index=False)
        else:
            df.to_sql(tabla, self.engine, if_exists="replace", index=False,
                      chunksize=10000, method="multi")


def norm(s):
    """Sin acentos, mayúsculas y espacios simples: 'El Águila' -> 'EL AGUILA'."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


def a_fecha(serie):
    return pd.to_datetime(serie, errors="coerce")


def activos_en(fechas, ingreso, baja):
    """Matriz booleana [fecha x empleado]: ingreso <= fecha < baja."""
    f = np.asarray(fechas, dtype="datetime64[ns]")[:, None]
    i = np.asarray(ingreso, dtype="datetime64[ns]")[None, :]
    b = np.asarray(pd.Series(baja).fillna(pd.Timestamp("2100-01-01")), dtype="datetime64[ns]")[None, :]
    return (i <= f) & (f < b)


# ---------------------------------------------------------------- ÁREAS (nombres normalizados)
AREA_DIRECCION   = "DIRECCION"
AREA_VENTA_NUEVA = "VENTA NUEVA"
AREA_RENOVACION  = "RENOVACIONES"
AREA_ECOMMERCE   = "ECOMMERCE"
AREA_ATC         = "ATENCION A CLIENTES"
AREA_A_ELIMINAR  = "COBRANZA"

# ---------------------------------------------------------------- CAMPAÑAS DE VENTA NUEVA
# Llave = nombre EXACTO en dim_campanas.  tipo: grande | chica | oro
# grupo = equipo de supervisión (Motocicletas, Taxis y Transporte Pesado comparten supervisor con Plataformas)
TODAS = "TODAS"
CAMPANAS = {
    "Descuentos":         dict(lanzamiento="2022-01-03", meta_leads=29000, hc_limit=41, tipo="grande", grupo="Descuentos",
                           vehiculos=["AUTO", "SUV"], aseguradoras=TODAS),
    "Alianza Qualitas": dict(lanzamiento="2022-01-03", meta_leads=30000, hc_limit=38, tipo="grande", grupo="Alianza Qualitas",
                           vehiculos=["AUTO", "SUV"], aseguradoras=["QUALITAS"]),
    "Alianza GNP":      dict(lanzamiento="2022-01-03", meta_leads=28000, hc_limit=39, tipo="grande", grupo="Alianza GNP",
                           vehiculos=["AUTO", "SUV"], aseguradoras=["GNP"]),
    "Bancaseguros":         dict(lanzamiento="2022-01-03", meta_leads=8500,  hc_limit=14, tipo="chica", grupo="Bancaseguros",
                           vehiculos=["AUTO", "SUV"], aseguradoras=["BANORTE", "INBURSA", "AFIRME"]),
    "Plataformas":         dict(lanzamiento="2022-06-01", meta_leads=8500,  hc_limit=14, tipo="chica", grupo="Plataformas",
                           vehiculos=["AUTO"], aseguradoras=["AXA", "QUALITAS", "GNP", "BANORTE"]),
    "Motocicletas":          dict(lanzamiento="2022-06-01", meta_leads=4000,  hc_limit=7,  tipo="chica", grupo="Plataformas",
                           vehiculos=["MOTO"], aseguradoras={"QUALITAS": 0.70, "GNP": 0.25, "MAPFRE": 0.05}),
    "Multimarcas":    dict(lanzamiento="2023-01-02", meta_leads=8500,  hc_limit=14, tipo="chica", grupo="Multimarcas",
                           vehiculos=["AUTO", "SUV"],
                           aseguradoras=["MAPFRE", "HDI", "ZURICH", "EL AGUILA", "PRIMERO SEGUROS"]),
    "Digital":         dict(lanzamiento="2023-05-02", meta_leads=8700,  hc_limit=15, tipo="chica", grupo="Digital",
                           vehiculos=["AUTO", "SUV"], aseguradoras=TODAS),
    "Telemarketing":     dict(lanzamiento="2023-07-03", meta_leads=8700,  hc_limit=15, tipo="chica", grupo="Telemarketing",
                           vehiculos=["AUTO", "SUV"], aseguradoras=TODAS),
    "Recuperacion Web":     dict(lanzamiento="2023-09-01", meta_leads=6000,  hc_limit=10, tipo="oro",   grupo="Recuperacion Web",
                           vehiculos=["AUTO", "SUV"], aseguradoras=TODAS),
    "Taxis":          dict(lanzamiento="2024-02-01", meta_leads=1500,  hc_limit=3,  tipo="chica", grupo="Plataformas",
                           vehiculos=["AUTO"], aseguradoras=["AFIRME", "QUALITAS", "BANORTE"]),
    "Transporte Pesado": dict(lanzamiento="2024-05-06", meta_leads=450,   hc_limit=1,  tipo="chica", grupo="Plataformas",
                           vehiculos=["TRACTO"], aseguradoras=["QUALITAS", "GNP"]),
}
TAXIS_ALTA = dict(nombre_campana="Taxis", segmento="Comparadores", meta_conversion=0.06)

# Equipos de supervisión: tope de supervisores (tu tabla) y coordinador que los lleva.
# coord = posición del coordinador de Venta Nueva ordenado por id_empleado (hoy ids 4 a 9).
GRUPOS = {
    "Descuentos":         dict(sup_max=3, coord=0),
    "Alianza Qualitas": dict(sup_max=3, coord=1),
    "Alianza GNP":      dict(sup_max=3, coord=2),
    "Bancaseguros":         dict(sup_max=1, coord=3),
    "Multimarcas":    dict(sup_max=1, coord=3),
    "Plataformas":         dict(sup_max=1, coord=4),   # Plataformas + Motocicletas + Taxis + Transporte Pesado
    "Digital":         dict(sup_max=1, coord=5),
    "Telemarketing":     dict(sup_max=1, coord=5),
    "Recuperacion Web":     dict(sup_max=1, coord=5),
}

# ---------------------------------------------------------------- ESTRUCTURA DIRECTIVA
FECHA_DIRECCION        = pd.Timestamp("2022-01-01")
FECHA_SUBGERENTE_RENOV = pd.Timestamp("2022-11-01")
FECHAS_COORD_RENOV     = [pd.Timestamp("2022-11-15"), pd.Timestamp("2024-01-15")]
ATC_DIRECTIVOS = [  # se crean si no existen (puesto, fecha)
    ("Gerente", pd.Timestamp("2022-01-01")),
    ("Coordinador", pd.Timestamp("2022-01-01")),
]
ARRANQUE_RENOV = pd.Timestamp("2022-12-01")
ARRANQUE_ATC   = pd.Timestamp("2022-01-03")

# ---------------------------------------------------------------- MOTOR WFM
ARRANQUE_PCT_HC       = 0.25     # una campaña nace con ~25% de su HC Limit Oper (Descuentos: 10)
ROTACION_EJECUTIVOS   = 0.05     # Fase A: 5% mensual
ROTACION_SUPERVISORES = 0.015
ALTAS_POR_MES         = (2, 6)   # Fase B
EJECUTIVOS_POR_SUP    = 15
CAPACIDAD_RENOV       = 250      # pólizas por vencer que gestiona un ejecutivo de Renovaciones al mes
CAPACIDAD_ATC         = 450      # tickets que resuelve un ejecutivo de ATC al mes
TASA_RETENCION        = 0.80
TASA_TICKETS          = 0.75

# ---------------------------------------------------------------- LEADS
LEADS_MAX_EJECUTIVO_MES = 600
RUIDO_LEADS_DIA         = (0.95, 1.05)
FACTOR_TEMPORADA        = 1.20
TEMPORADAS = [
    ("Hot Sale", "2022-05-23", "2022-05-31"), ("Buen Fin", "2022-11-18", "2022-11-21"),
    ("Hot Sale", "2023-05-29", "2023-06-06"), ("Buen Fin", "2023-11-17", "2023-11-20"),
    ("Hot Sale", "2024-05-27", "2024-06-04"), ("Buen Fin", "2024-11-15", "2024-11-18"),
    ("Hot Sale", "2025-05-26", "2025-06-03"), ("Buen Fin", "2025-11-14", "2025-11-17"),
]

# ---------------------------------------------------------------- VENTAS
VENTAS_GRANDES = (25, 40)       # pólizas/día en operación estable
PISO_GRANDES   = 20
CUMPL_CHICAS   = (0.70, 0.95)   # % de SU meta_conversion (dim_campanas)
CONV_ORO       = (0.30, 0.38)

# ---------------------------------------------------------------- ASEGURADORAS
PESO_MERCADO = {
    "QUALITAS": 0.32, "GNP": 0.14, "CHUBB": 0.09, "AXA": 0.09, "HDI": 0.06,
    "BANORTE": 0.05, "INBURSA": 0.04, "MAPFRE": 0.03, "ANA SEGUROS": 0.03,
    "AFIRME": 0.03, "ZURICH": 0.03, "EL AGUILA": 0.045, "PRIMERO SEGUROS": 0.045,
}
CONVENIOS = {
    # Fase 1: convenios iniciales
    "QUALITAS": "2022-01-01", "GNP": "2022-01-01", "BANORTE": "2022-01-01", "CHUBB": "2022-01-01",
    "AXA": "2022-01-01", "ANA SEGUROS": "2022-01-01", "HDI": "2022-01-01", "MAPFRE": "2022-01-01",
    # Fase 2: escalonada enero-junio 2023
    "ZURICH": "2023-01-16", "EL AGUILA": "2023-02-15", "INBURSA": "2023-03-15",
    "AFIRME": "2023-05-15", "PRIMERO SEGUROS": "2023-06-15",
}
PREFIJOS_ASEGURADORA = {
    "QUALITAS": "QTL", "GNP": "GNP", "BANORTE": "BAN", "AXA": "AXA", "HDI": "HDI",
    "CHUBB": "ABA", "MAPFRE": "MAP", "AFIRME": "AFI", "ZURICH": "ZUR",
    "ANA SEGUROS": "ANA", "EL AGUILA": "AGL", "PRIMERO SEGUROS": "PRI", "INBURSA": "INB",
}

# ---------------------------------------------------------------- COBERTURAS Y PRIMAS
PESOS_COBERTURA = {"AMPLIA": 0.45, "LIMITADA": 0.30, "RESPONSABILIDAD CIVIL": 0.15, "AMPLIA PLUS": 0.10}
TRACTO_COBERTURAS = {"RESPONSABILIDAD CIVIL": 0.75, "LIMITADA": 0.15, "AMPLIA": 0.10}
RANGO_PRIMA_BASE_POR_TIPO = {"MOTO": (3000.0, 6000.0), "AUTO": (7000.0, 12000.0), "SUV": (10000.0, 16000.0)}
MULTIPLICADOR_COBERTURA = {"RESPONSABILIDAD CIVIL": 0.30, "LIMITADA": 0.60, "AMPLIA": 1.00, "AMPLIA PLUS": 1.30}
# Transporte Pesado: PNC anual propia. (probabilidad, mínimo, máximo) para RC
TRACTO_PRIMA_RC = [(0.94, 15000.0, 35000.0), (0.05, 40000.0, 60000.0), (0.01, 60000.0, 80000.0)]
TRACTO_MULT_COBERTURA = {"RESPONSABILIDAD CIVIL": 1.00, "LIMITADA": 1.30, "AMPLIA": 1.60}
TRACTO_PRIMA_MAX = 80000.0
INFLACION_POR_ANIO = {2022: 1.00, 2023: 1.07, 2024: 1.15, 2025: 1.23, 2026: 1.30}
PESOS_FORMA_PAGO_POR_ANIO = {
    2022: {"Anual": 0.40, "Mensual": 0.30, "Semestral": 0.15, "Trimestral": 0.15},
    2023: {"Anual": 0.55, "Mensual": 0.25, "Semestral": 0.12, "Trimestral": 0.08},
    2024: {"Anual": 0.68, "Mensual": 0.18, "Semestral": 0.09, "Trimestral": 0.05},
    2025: {"Anual": 0.78, "Mensual": 0.12, "Semestral": 0.06, "Trimestral": 0.04},
}

# ---------------------------------------------------------------- RENOVACIONES
# Campaña de VN -> palabra clave de su campaña de Renovaciones. Lo demás va a Multimarcas.
RENOVACION_DESTINO = {"Bancaseguros": "Bancaseguros", "Alianza GNP": "GNP", "Alianza Qualitas": "QUALITAS",
                      "Motocicletas": "Motocicletas", "Plataformas": "Plataformas"}
RENOVACION_DEFAULT = "MULTIMARCAS"
