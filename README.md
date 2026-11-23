# Forum Global Seguros – Análisis de un bróker de seguros de auto

Proyecto de análisis de datos *end-to-end* sobre **Forum Global Seguros**, un bróker de seguros de auto **simulado**, diseñado a partir de mi experiencia de más de 4 años en la operación de un bróker real, donde fui ejecutivo de ventas, supervisor y coordinador de campañas.

Los datos se generan con **Python** siguiendo reglas de negocio reales y se guardan en **MySQL**. Después se analizan con **SQL**, se exploran con **pandas** y se presentan en un **dashboard de Power BI**.

> ⚠️ Los datos son simulados. Los nombres de aseguradoras se usan solo como referencia del mercado mexicano.

**Herramientas:** MySQL · Python (pandas, NumPy, matplotlib, SQLAlchemy) · Power BI (DAX, Power Query) · Git

---

## Hallazgos principales

1. **La venta nueva llegó a un techo.** Casi se triplicó entre 2022 y 2025 (de 32,359 a 95,735 pólizas), pero desde 2024 se estancó en ~8,000 pólizas al mes (+0.4% en 2025). En ese mismo periodo, la plantilla de ejecutivos dejó de crecer (~290–304).
2. **Más leads no significa más ventas.** Descuentos, Alianza GNP y Alianza Qualitas recibieron más de 1 millón de leads cada una y convirtieron solo 4.0–4.3%. Recuperacion Web, con leads del web service, convierte 34%.
3. **La retención anual es de ~80%, en línea con la meta.** Pero se acumula: de cada 100 clientes de 2022, solo ~41 siguen en 2026. Con 85% anual seguirían ~52, lo que significa 25% más cartera.
4. **Los clientes fieles son el 37% de la cartera y aportan el 53% de la prima.** La mayoría de los clientes perdidos se va en la primera o segunda renovación.
5. **Hay una oportunidad en la forma de pago.** En 2025, 26,660 renovaciones (19.9%) seguían en pago mensual. Migrarlas a anual aumentaría la prima cobrada por adelantado.
6. **Atención a Clientes escaló sin perder velocidad.** Los tickets crecieron más de 40 veces y el tiempo de cierre se mantuvo en ~1 día, porque la plantilla de ATC creció al mismo ritmo (~450 tickets por ejecutivo al mes).
7. **La rotación es alta.** La rotación anual de 2024 fue de 66.8% (~5.5% mensual), y uno de cada cinco ejecutivos está en sus primeros 3 meses.

---

## Estructura del repositorio

```
forum-analisis-seguros/
├── python/       Pipeline que genera los datos y los carga en MySQL
├── sql/          10 consultas de análisis, de nivel básico a avanzado (con su README)
├── notebooks/    EDA en Python (casos_forum.ipynb)
├── powerbi/      Dashboard como proyecto de Power BI (.pbip, sin datos)
└── README.md
```

---

## 1. Datos: pipeline en Python

La base `forum_global_seguros` (MySQL) cubre de **enero de 2022 a diciembre de 2026**:

| Dato | Volumen |
|---|---:|
| Leads | 5,071,406 |
| Pólizas emitidas (venta nueva y renovación) | 703,436 |
| Tickets de Atención a Clientes | 491,118 |
| Empleados (activos y dados de baja) | 927 |
| Aseguradoras | 13 |
| Campañas | 18 |

El modelo sigue el flujo **Lead → Póliza → Pago → Renovación → Ticket de atención**, con un esquema estrella de tablas de hechos (`fact_leads`, `fact_polizas`, `fact_pagos`, `fact_atencion_clientes`) y dimensiones (`dim_empleados`, `dim_campanas`, `dim_aseguradoras`, entre otras).

| Script | Qué hace |
|---|---|
| `00_preparar_catalogos.py` | Catálogos: aseguradoras, campañas, coberturas y áreas |
| `01a_wfm_venta_nueva.py` | Plantilla de Venta Nueva: arranque por campaña, altas, rotación de ~5% mensual y 1 supervisor por cada 15 ejecutivos |
| `01b_wfm_renovaciones_atc.py` | Plantilla de Renovaciones y Atención a Clientes |
| `02_metas_y_plan_leads.py` | Metas mensuales de leads por campaña, limitadas por la capacidad de la plantilla |
| `03_leads_y_polizas_vn.py` | Leads y pólizas de venta nueva, con conversión por campaña y habilidad individual de cada ejecutivo |
| `04_renovaciones.py` | Renovaciones (meta de 80%) con ajuste de precio por año del vehículo |
| `05_pagos.py` | Estado del primer recibo de cada póliza |
| `06_atencion_clientes.py` | Tickets de Atención a Clientes |
| `07_validar.py` | Validaciones de consistencia entre tablas |
| `correr_todo.py` | Ejecuta el pipeline completo en orden |
| `config_forum.py` | Parámetros de la simulación y conexión a MySQL |

**Reglas de negocio tomadas de la operación real:**
- Rotación mensual de ~5%.
- Arranque escalonado de campañas y convenios con aseguradoras.
- Participación de mercado por aseguradora.
- Mezcla de forma de pago que migra hacia pago anual.
- Comisiones sobre prima neta.
- Renovación con vigencia anual.

---

## 2. Dashboard en Power BI

El dashboard tiene 5 páginas, en lienzo de 1920 × 1080. Se publica como **proyecto de Power BI (.pbip)**, para que las medidas DAX y las consultas de Power Query se puedan leer como texto, sin subir datos.

| Página | Qué responde |
|---|---|
| General | Pólizas, prima y conversión de toda la operación |
| Venta Nueva | Venta nueva por segmento, campaña y aseguradora |
| Renovaciones | % de renovación vs meta de 80%, monto renovado y comparativo contra el año anterior |
| Atención a Clientes | Volumen de tickets, motivos, tiempo de cierre, calidad de emisión y productividad |
| Recursos Humanos | Plantilla, altas y bajas, rotación y antigüedad |


![Página General](powerbi/capturas_powerbi/01_General_forum.png)
![Venta Nueva](powerbi/capturas_powerbi/02_Venta_nueva.png)
![Renovaciones](powerbi/capturas_powerbi/03_Renovaciones.png)
![Atención a Clientes](powerbi/capturas_powerbi/04_Atencion_al_cliente.png)
![Recursos Humanos](powerbi/capturas_powerbi/05_Recursos_humanos.png)

**Hallazgos del dashboard:**

- **Renovaciones:**
  - Retención de 79.96% (394,473 de 493,325 pólizas por renovar), con la meta cumplida en todas las carteras.
  - Efecto "bola de nieve": la cartera por renovar creció más de 15 veces entre el Q1-2023 y el Q4-2026.
  - El monto renovado crece más rápido que las pólizas (+240% vs +178%), porque el pago anual pasó de ~75–78% a ~92–95% del monto renovado entre 2023 y 2026.
- **Atención a Clientes:**
  - ~45% de los tickets son correcciones de emisión (endosos, reexpediciones, cambios de conductor y aclaraciones de cobro), es decir, ~30 por cada 100 pólizas.
  - Por cohorte de emisión, ~53% de las pólizas genera al menos un ticket, estable 2022–2025. La medida por fecha de ticket sugería un deterioro que no existe (de 38% a 63%), causado por el desfase de hasta 180 días entre la emisión y el ticket.
- **Recursos Humanos:**
  - La plantilla pasó de 161 a 304 ejecutivos (2022–2025).
  - En 2022–2023 las altas superan por mucho a las bajas (crecimiento). En 2024–2025 se emparejan (madurez).
  - Venta Nueva rota más que Renovaciones (~4.7% vs ~1.7% mensual).

**Decisiones de modelado:**
- Vistas SQL aplanadas para mantener el esquema estrella.
- Plantilla calculada a una fecha de corte con fechas de alta y baja, como medida semiaditiva.
- Medidas de cohorte con `TREATAS` y `REMOVEFILTERS`.
- Fechas de cierre conectadas a la tabla calendario como relación inactiva.

---

## 3. Consultas SQL

10 consultas organizadas en tres niveles. Cada archivo empieza con la pregunta de negocio, la técnica y el hallazgo. **[Ver resultados y hallazgos de cada consulta →](sql/README.md)**

| Nivel | Casos | Técnicas |
|---|---|---|
| `01_junior_screening` | Concentración por aseguradora, limpieza del RFC, leads sin póliza | `JOIN`, `GROUP BY`/`HAVING`, CTE, anti-join, `CASE` |
| `02_mid_analytics` | Ranking de ejecutivos, crecimiento mes contra mes, funnel de conversión | `DENSE_RANK`, `LAG`, `SUM() OVER (PARTITION BY)` |
| `03_senior_architect` | Pareto, cohortes de retención, segmentación RFM, organigrama | Acumulados con `ROWS BETWEEN`, cohortes, `SELF JOIN` |

---

## 4. Análisis exploratorio en Python

**[Ver notebook →](notebooks/casos_forum.ipynb)**

Las preguntas del análisis son:
- ¿Cómo evolucionó la venta nueva?
- ¿Qué porcentaje de las pólizas emitidas se paga?
- ¿La forma de pago explica el impago?

El notebook incluye revisión de calidad de datos (llaves, nulos, consistencia entre tablas), preparación de datos y gráficas con matplotlib.

**Conclusiones:**
- El 95% de las pólizas tiene su primer recibo cubierto, igual en venta nueva y en renovación.
- Todas las formas de pago tienen ~5% de impago, así que la forma de pago no explica quién paga y quién no.
- En la venta nueva, el pago anual pasó de 39% a 78% entre 2022 y 2025. En las renovaciones se conserva la mezcla anterior.

---

## Recomendaciones

1. **Investigar el techo de ~8,000 pólizas al mes antes de invertir en más leads.** Primero hay que revisar la plantilla, la conversión por campaña, la rotación y el tiempo de capacitación de los nuevos ingresos.
2. **Concentrar la retención en la primera y segunda renovación.** Ahí se pierde la mayoría de los clientes, y cada punto de retención se acumula año con año.
3. **Ofrecer pago anual a las renovaciones mensuales** en su siguiente renovación.
4. **Reducir la rotación de Venta Nueva** y medirla separando renuncias de movimientos internos.

## Limitaciones de los datos

Los datos simulados tienen distribuciones más uniformes que los reales:
- Retención de ~80% y estado de pago 85/10/5 en todos los grupos.
- La renovación copia la forma de pago original, sin modelar el cambio de mensual a anual.
- `id_cliente` y el VIN se reutilizan al azar. Por eso las cohortes y el RFM se calculan por cadena de póliza (`id_lead`).
- La venta nueva termina el 5 de enero de 2026. Venta Nueva se analiza en 2022–2025 y Renovaciones en 2023–2026.

---

## Cómo reproducirlo

1. Crea la base `forum_global_seguros` en MySQL.
2. Guarda la conexión en una variable de entorno. Así las credenciales nunca se escriben en el código:
   ```
   setx FORUM_CONN "mysql+pymysql://USUARIO:CONTRASEÑA@localhost:3306/forum_global_seguros"
   ```
3. Instala las librerías:
   ```
   pip install pandas numpy matplotlib sqlalchemy pymysql
   ```
4. Genera los datos con `python python/correr_todo.py`.
5. Corre las consultas de `sql/` y abre `notebooks/casos_forum.ipynb`.

---

## Autor

**Luis Fernando Robles Gutierrez**: Data Analyst en formación, con experiencia en operación comercial de seguros y en crédito y cobranza.

LinkedIn: [Luis Fernando Robles](https://www.linkedin.com/in/luis-fernando-robles-gutierrez/) · GitHub: [Robles-98](https://github.com/Robles-98)