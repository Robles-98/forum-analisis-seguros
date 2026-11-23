-- =============================================
-- Pregunta de negocio: ¿Cómo evolucionó la prima neta mes contra mes (MoM) durante 2024?
-- Técnica: CTE + LAG() OVER (ORDER BY ...) para traer el mes anterior; variación absoluta y %
--          con NULLIF en el denominador; rango de fechas en el WHERE; meses en español con lc_time_names.
--Hallazgo: la prima neta creció 44% de enero ($115.7M) a diciembre ($166.8M) de 2024, con los mayores
--           saltos en marzo (+7.3%) y octubre (+8.0%). Validado por tipo de póliza: la renovación pasó de
--           $35.6M a $84.9M (+138.7%) mientras la VN solo creció 2.2% ($80.2M a $81.9M). El 96.6% del
--           crecimiento viene de las renovaciones (efecto bola de nieve de la cartera; ver EDA 5.1).
-- Nota: incluye venta nueva y renovaciones.
-- =============================================

SET lc_time_names = 'es_MX';

WITH ventas_mensuales AS (
    SELECT
        MONTH(fecha_emision) AS mes_emision,
        MONTHNAME(fecha_emision) AS nombre_mes,
        SUM(prima_neta) AS prima_mes_actual
    FROM fact_polizas
    WHERE fecha_emision >= '2024-01-01'
      AND fecha_emision <  '2025-01-01'
    GROUP BY MONTH(fecha_emision), MONTHNAME(fecha_emision)
),
calculo_mom AS (
    SELECT
        mes_emision,
        nombre_mes,
        prima_mes_actual,
        LAG(prima_mes_actual) OVER (ORDER BY mes_emision) AS prima_mes_anterior
    FROM ventas_mensuales
)
SELECT
    mes_emision,
    nombre_mes,
    prima_mes_actual,
    prima_mes_anterior,
    prima_mes_actual - prima_mes_anterior AS variacion_monto,
    ROUND(100 * (prima_mes_actual - prima_mes_anterior) / NULLIF(prima_mes_anterior, 0), 2) AS pct_crecimiento_mom
FROM calculo_mom
ORDER BY mes_emision;
