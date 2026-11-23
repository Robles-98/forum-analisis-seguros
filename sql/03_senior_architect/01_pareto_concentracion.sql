-- =============================================
-- Pregunta de negocio: ¿Qué porcentaje de los ejecutivos de venta nueva genera el 80% de la prima en 2025? (Pareto)
-- Técnica: CTE encadenados; acumulado con SUM() OVER (ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING
--          AND CURRENT ROW) con desempate por id_empleado; total con SUM() OVER (); clasificación con CASE;
--          resumen con COUNT y SUM sobre ventanas.
-- Alcance: solo venta nueva y solo 2025. Los ejecutivos de Renovaciones gestionan cartera asignada (no venden)
--          y sumar varios años mediría antigüedad, no desempeño.
-- Hallazgo: la VN de 2025 no sigue la regla 80/20: 149 de 318 ejecutivos (46.9%) generan el 79.7% de la prima.
--           La venta está repartida y no depende de un grupo pequeño de vendedores estrella, algo coherente con
--           campañas grandes de muchos ejecutivos con volúmenes parecidos. El "Resto 20%" incluye ejecutivos que
--           trabajaron solo parte del año (rotación ~5% mensual) o estaban en su rampa de aprendizaje.
-- Acción: retener y desarrollar antigüedad en los ejecutivos de VN, porque la rotación saca de la cuenta
--         a quienes ya dominan la venta. En la operación real esto es complejo: parte de la "rotación" son
--         movimientos internos (promociones a supervisor, cambios a Renovaciones) que se llevan a los mejores
--         vendedores; conviene separar renuncias de movimientos internos al medir la rotación.
-- =============================================

WITH ventas_ejecutivos AS (
    SELECT
        e.id_empleado,
        e.nombre_completo AS nombre_agente,
        COUNT(p.id_poliza) AS polizas,
        SUM(p.prima_neta) AS prima_neta
    FROM dim_empleados e
        INNER JOIN fact_polizas p
            ON e.id_empleado = p.id_empleado
    WHERE p.tipo_emision = 'Venta Nueva'
      AND p.fecha_emision >= '2025-01-01'
      AND p.fecha_emision <  '2026-01-01'
    GROUP BY e.id_empleado, e.nombre_completo
),
acumulado_pareto AS (
    SELECT
        id_empleado,
        nombre_agente,
        polizas,
        prima_neta,
        SUM(prima_neta) OVER (ORDER BY prima_neta DESC, id_empleado
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prima_acumulada,
        SUM(prima_neta) OVER () AS prima_total
    FROM ventas_ejecutivos
),
clasificados AS (
    SELECT
        id_empleado,
        nombre_agente,
        polizas,
        prima_neta,
        ROUND(100 * prima_acumulada / NULLIF(prima_total, 0), 2) AS pct_acumulado,
        CASE
            WHEN 100 * prima_acumulada / NULLIF(prima_total, 0) <= 80 THEN 'Top 80%'
            ELSE 'Resto 20%'
        END AS clasificacion
    FROM acumulado_pareto
)
SELECT
    clasificacion,
    COUNT(*) AS ejecutivos,
    ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_ejecutivos,
    ROUND(SUM(prima_neta), 2) AS prima_neta,
    ROUND(100 * SUM(prima_neta) / SUM(SUM(prima_neta)) OVER (), 1) AS pct_prima
FROM clasificados
GROUP BY clasificacion
ORDER BY clasificacion DESC;