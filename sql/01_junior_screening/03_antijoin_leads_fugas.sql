-- =============================================
-- Pregunta de negocio: ¿Qué leads no se convirtieron en póliza y qué campaña convierte mejor?
-- Técnica: anti-join (LEFT JOIN + IS NULL) para encontrar leads sin póliza.
--          En la consulta 2 se une contra los id_lead DISTINTOS de fact_polizas,
--          porque las renovaciones reutilizan el id_lead de la venta nueva y duplicarían los conteos.
--Hallazgo: de 5,071,406 millones de leads, 288,174 se convirtieron en póliza (validado contra fact_polizas).
--           Recuperacion Web convierte 34.1% (web service), seguido de Digital (8.2%) y Telemarketing (6.5%).
--           Descuentos, Alianza GNP y Alianza Qualitas reciben más de 1 millón de leads cada una y convierten solo 4.0–4.3%:
--           más leads no significa más ventas si el HC no alcanza para atenderlos.
--Nota: aquí "convertido" = póliza emitida; en la operación, la VN cuenta solo con el primer recibo pagado (~95%).
-- =============================================

-- 1) Detalle: los 20 leads más recientes que no se convirtieron en póliza
SELECT
    l.id_lead,
    c.nombre_campana AS campana,
    l.origen_lead AS canal_de_lead,
    l.fecha_contacto,
    l.estatus_lead
FROM fact_leads l
    LEFT JOIN fact_polizas p
        ON l.id_lead = p.id_lead
    LEFT JOIN dim_campanas c
        ON l.id_campana = c.id_campana
WHERE p.id_lead IS NULL
ORDER BY l.fecha_contacto DESC
LIMIT 20;


-- 2) Resumen: conversión por campaña
SELECT
    c.nombre_campana AS campana,
    COUNT(*) AS leads,
    SUM(p.id_lead IS NOT NULL) AS convertidos,
    SUM(p.id_lead IS NULL) AS sin_poliza,
    ROUND(100 * SUM(p.id_lead IS NOT NULL) / COUNT(*), 2) AS pct_conversion
FROM fact_leads l
    LEFT JOIN (SELECT DISTINCT id_lead FROM fact_polizas) p
        ON l.id_lead = p.id_lead
    LEFT JOIN dim_campanas c
        ON l.id_campana = c.id_campana
GROUP BY c.nombre_campana
ORDER BY pct_conversion DESC;