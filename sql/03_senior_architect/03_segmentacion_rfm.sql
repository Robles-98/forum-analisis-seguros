-- =============================================
-- Pregunta de negocio: ¿Cómo se compone la cartera de clientes: fieles, activos recientes o perdidos,
--          y cuánta prima aporta cada segmento?
-- Técnica: RFM adaptado a seguros. Cada cadena de póliza (id_lead: VN + sus renovaciones) es un cliente.
--          Recencia = última póliza, Frecuencia = número de pólizas, Monto = prima total.
--          Segmentos con reglas de negocio (CASE) y resumen con ventanas sobre agregados.
-- Calidad de datos: por id_cliente la frecuencia llegaba a 15 pólizas, cuando el máximo posible es 5
--          (VN 2022 + 4 renovaciones): la simulación reutilizó id_cliente al azar. Por eso se usa id_lead.
--          No se usan cuartiles (NTILE): la frecuencia solo vale de 1 a 5 y los empates repartirían
--          clientes idénticos en segmentos distintos.
-- Corte: 31-dic-2026. Un cliente sigue vigente si tiene una póliza emitida en 2026.
-- -- Hallazgo: los clientes fieles (vigentes con 3+ pólizas) son el 37.1% de la cartera pero aportan el 53.3%
--           de la prima: cada cliente fiel vale ~2.25 veces lo que un cliente perdido ($35,606 vs $15,821).
--           El 36.1% de los clientes se perdió, y en promedio solo tuvo 1.63 pólizas: la mayoría se va en la
--           primera o segunda renovación, que es donde conviene concentrar la gestión de Renovaciones.
--           Validación: 288,174 cadenas y $7,145M de prima, igual que el total de fact_polizas.
-- =============================================

WITH cartera AS (
    SELECT
        id_lead,
        MIN(fecha_emision) AS primera_poliza,
        MAX(fecha_emision) AS ultima_poliza,
        COUNT(*) AS polizas,
        SUM(prima_neta) AS prima_total
    FROM fact_polizas
    GROUP BY id_lead
),
segmentos AS (
    SELECT
        c.*,
        DATEDIFF('2026-12-31', c.ultima_poliza) AS dias_desde_ultima,
        CASE
            WHEN c.ultima_poliza < '2026-01-01' THEN 'Perdido'
            WHEN c.polizas >= 3 THEN 'Fiel'
            ELSE 'Activo reciente'
        END AS segmento
    FROM cartera c
)
SELECT
    segmento,
    COUNT(*) AS clientes,
    ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_clientes,
    ROUND(AVG(polizas), 2) AS polizas_promedio,
    ROUND(AVG(dias_desde_ultima)) AS dias_promedio_desde_ultima,
    ROUND(SUM(prima_total), 2) AS prima_total,
    ROUND(100 * SUM(prima_total) / SUM(SUM(prima_total)) OVER (), 1) AS pct_prima,
    ROUND(AVG(prima_total), 2) AS prima_promedio_cliente
FROM segmentos
GROUP BY segmento
ORDER BY prima_total DESC;