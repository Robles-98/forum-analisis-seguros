-- =============================================
-- Pregunta de negocio: De los clientes que compraron venta nueva en un año, ¿qué % renueva al año 1, 2, 3 y 4?
-- Técnica: cohortes por año de venta nueva; las renovaciones se ligan a su VN por id_lead (cada renovación
--          reutiliza el id_lead de su venta original); conteo de renovaciones por lead; SUM condicional;
--          CASE para dejar en NULL los años que todavía no pueden ocurrir (los datos llegan a dic-2026).
-- Calidad de datos: id_cliente no sirve para cohortes, porque la simulación lo reutilizó al azar
--          (185,354 clientes para 703,436 pólizas); por eso se sigue la cadena de la póliza por id_lead.
-- -- Hallazgo: la retención anual es ~80% y constante en todas las cohortes: 80% renueva al año 1, 64% al año 2,
--           51% al año 3 y 41% al año 4 (= 0.8, 0.8², 0.8³, 0.8⁴). De cada 100 clientes de VN de 2022,
--           solo ~41 siguen en 2026. Cada punto de retención se acumula: con 85% anual, al año 4 seguirían
--           ~52 de cada 100 (25% más cartera). Los tamaños de cohorte cuadran con la VN anual del EDA.
-- Limitación: la simulación usa una retención fija de ~80%; en datos reales variaría por campaña, forma de
--           pago y antigüedad del cliente.
-- =============================================

WITH vn AS (
    SELECT
        id_lead,
        YEAR(fecha_emision) AS cohorte
    FROM fact_polizas
    WHERE tipo_emision = 'Venta Nueva'
      AND fecha_emision < '2026-01-01'
),
renovaciones_por_lead AS (
    SELECT
        id_lead,
        COUNT(*) AS renovaciones
    FROM fact_polizas
    WHERE tipo_emision = 'Renovacion'
    GROUP BY id_lead
)
SELECT
    v.cohorte,
    COUNT(*) AS clientes_vn,
    ROUND(100 * SUM(COALESCE(r.renovaciones, 0) >= 1) / COUNT(*), 1) AS pct_anio_1,
    CASE WHEN v.cohorte + 2 <= 2026
         THEN ROUND(100 * SUM(COALESCE(r.renovaciones, 0) >= 2) / COUNT(*), 1) END AS pct_anio_2,
    CASE WHEN v.cohorte + 3 <= 2026
         THEN ROUND(100 * SUM(COALESCE(r.renovaciones, 0) >= 3) / COUNT(*), 1) END AS pct_anio_3,
    CASE WHEN v.cohorte + 4 <= 2026
         THEN ROUND(100 * SUM(COALESCE(r.renovaciones, 0) >= 4) / COUNT(*), 1) END AS pct_anio_4
FROM vn v
    LEFT JOIN renovaciones_por_lead r
        ON v.id_lead = r.id_lead
GROUP BY v.cohorte
ORDER BY v.cohorte;