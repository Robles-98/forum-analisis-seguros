-- =============================================
-- Pregunta de negocio: ¿Qué aseguradoras concentran el volumen de pólizas y de prima?
-- Técnica: INNER JOIN + GROUP BY con agregaciones (COUNT, SUM, AVG) y HAVING
--          para quedarse solo con las aseguradoras de alto volumen (más de 30,000 pólizas).
-- Hallazgo: Quálitas y GNP concentran el 61.3% de la prima neta (36.2% y 25.0%) y el 62.1% de las pólizas.
--           La prima promedio es muy parecida entre aseguradoras (~$9,950 a ~$10,700),
--           así que lo que las diferencia es el volumen, no el precio.
-- =============================================

SELECT
    a.id_aseguradora,
    a.nombre_aseguradora AS aseguradora,
    COUNT(p.id_poliza) AS cantidad_polizas,
    SUM(p.prima_neta) AS total_prima,
    ROUND(AVG(p.prima_neta), 2) AS prima_promedio
FROM dim_aseguradoras a
    INNER JOIN fact_polizas p
        ON a.id_aseguradora = p.id_aseguradora
GROUP BY a.id_aseguradora, a.nombre_aseguradora
HAVING COUNT(p.id_poliza) > 30000
ORDER BY total_prima DESC;