-- =============================================
-- Pregunta de negocio: ¿En qué etapa del funnel se pierden los leads de cada campaña?
-- Técnica: validación de calidad (estatus_lead vs pólizas), CTE con una fila por lead de venta nueva,
--          LEFT JOIN para conservar los leads sin venta, COUNT/SUM condicional y NULLIF.
-- -- Calidad de datos: estatus_lead parece reflejar el último intento por llamada ("No Contesta" puede convertir
--          por WhatsApp o correo; ~80% de los clientes tiene el filtro de spam para llamadas). Aun así no sirve
--          como etapa del funnel: los 4 estatus tienen ~25% de los leads y convierten igual (~5.7%), cuando un
--          lead "Cotizado" debería convertir mucho más. Por eso el funnel usa solo etapas de las tablas de hechos:
--          lead → póliza emitida → primer recibo pagado.
-- -- Hallazgo: la pérdida ocurre casi toda en la primera etapa (lead → emisión): solo 4–8% de los leads se emite,
--           excepto Recuperacion Web (34.1%). De emitida a pagada la tasa es ~95% en todas las campañas.
--           Contando la venta solo con el primer recibo pagado, la conversión real va de 32.4% (Recuperacion Web)
--           a 3.8% (Descuentos); las tres campañas con más de 1 millón de leads (Descuentos, Alianza GNP y Alianza Qualitas)
--           son las que menos convierten (3.8–4.1%). Para vender más hay que trabajar el contacto y la calidad
--           del lead, no la cobranza.
-- =============================================

-- 1) Validación: ¿el estatus del lead coincide con la venta?
SELECT
    l.estatus_lead,
    COUNT(*) AS leads,
    SUM(p.id_lead IS NOT NULL) AS con_poliza
FROM fact_leads l
    LEFT JOIN (SELECT DISTINCT id_lead FROM fact_polizas) p
        ON l.id_lead = p.id_lead
GROUP BY l.estatus_lead
ORDER BY leads DESC;

-- 2) Funnel por campaña: leads → emitidas → pagadas
WITH ventas_vn AS (
    SELECT
        p.id_lead,
        MAX(pg.estado_del_pago IN ('Pagado', 'Pagado con Atraso')) AS pagada
    FROM fact_polizas p
        JOIN vw_fact_pagos pg
            ON p.id_poliza = pg.id_poliza
    WHERE p.tipo_emision = 'Venta Nueva'
    GROUP BY p.id_lead
)
SELECT
    c.nombre_campana AS campana,
    COUNT(*) AS leads,
    COUNT(v.id_lead) AS emitidas,
    COALESCE(SUM(v.pagada), 0) AS pagadas,
    ROUND(100 * COUNT(v.id_lead) / COUNT(*), 2) AS pct_lead_a_emision,
    ROUND(100 * SUM(v.pagada) / NULLIF(COUNT(v.id_lead), 0), 2) AS pct_emision_a_pago,
    ROUND(100 * SUM(v.pagada) / COUNT(*), 2) AS pct_conversion_real
FROM fact_leads l
    LEFT JOIN ventas_vn v
        ON l.id_lead = v.id_lead
    LEFT JOIN dim_campanas c
        ON l.id_campana = c.id_campana
GROUP BY c.nombre_campana
ORDER BY pct_conversion_real DESC;