-- =============================================
-- Pregunta de negocio: ¿Quiénes son los 10 mejores ejecutivos de cada campaña en 2024 y cuánto pesan en su campaña?
-- Técnica: CTE encadenados; SUM() OVER (PARTITION BY) para el total de cada campaña;
--          DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...) para el ranking;
--          NULLIF para evitar la división entre cero; rango de fechas en el WHERE (permite usar índices).

-- -- Hallazgo: la concentración depende del tamaño de la campaña. El ejecutivo #1 aporta 3.8% del monto en Descuentos
--           y 3.9% en Alianza GNP (campañas grandes), pero 8.1% en Bancaseguros y 9.5% en Plataformas.
--           En Plataformas, los 4 primeros ejecutivos concentran ~36% del monto y hay un salto después del #4:
--           riesgo de concentración si alguno de ellos se va (la rotación mensual ronda 5%).

-- Nota: cuenta pólizas emitidas; en la operación, la VN cuenta solo con el primer recibo pagado (~95%).
-- =============================================

WITH ventas_2024 AS (
    SELECT
        ag.id_empleado,
        p.id_campana,
        ag.nombre_completo AS nombre_agente,
        c.nombre_campana AS campana,
        COUNT(p.id_poliza) AS polizas_vendidas,
        SUM(p.prima_neta) AS monto_venta
    FROM fact_polizas p
        JOIN dim_empleados ag
            ON ag.id_empleado = p.id_empleado
        JOIN dim_campanas c
            ON p.id_campana = c.id_campana
    WHERE p.fecha_emision >= '2024-01-01'
      AND p.fecha_emision <  '2025-01-01'
    GROUP BY ag.id_empleado, p.id_campana, ag.nombre_completo, c.nombre_campana
),
ranking_ejecutivos AS (
    SELECT
        id_empleado,
        nombre_agente,
        campana,
        polizas_vendidas,
        monto_venta,
        SUM(monto_venta) OVER (PARTITION BY id_campana) AS venta_total_campana,
        DENSE_RANK() OVER (PARTITION BY id_campana ORDER BY monto_venta DESC) AS rank_ejecutivo
    FROM ventas_2024
)
SELECT
    id_empleado,
    nombre_agente,
    campana,
    polizas_vendidas,
    monto_venta,
    venta_total_campana,
    rank_ejecutivo,
    ROUND(100 * monto_venta / NULLIF(venta_total_campana, 0), 2) AS pct_participacion
FROM ranking_ejecutivos
WHERE rank_ejecutivo <= 10
ORDER BY campana ASC, rank_ejecutivo ASC;