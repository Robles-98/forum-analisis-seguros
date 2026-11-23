-- =============================================
-- Pregunta de negocio: ¿Qué edad tienen los clientes y cuántos tienen una fecha de nacimiento poco confiable?
-- Técnica: CTE encadenados, STR_TO_DATE sobre el RFC, CASE para corregir el siglo,
--          TIMESTAMPDIFF para la edad y COALESCE + NULLIF para el contacto prioritario.
-- Nota: en los datos simulados el RFC trae la fecha como DDMMAA (el RFC real usa AAMMDD).
-- Reglas de negocio:
--   * Si la fecha da menos de 18 años, se asume que nació en el siglo pasado (se restan 100 años).
--   * Una edad es válida entre 18 y 80 años; fuera de ese rango se marca para revisión.
-- Hallazgo: de 8,678 clientes con RFC válido, 3,254 (37.5%) tienen una edad fuera de 18–80
--           y deben revisarse; en la simulación, la fecha del RFC se asignó al azar.
-- =============================================

WITH clientes_con_fecha AS (
    SELECT 
        id_cliente,
        UPPER(nombre_completo) AS nombre_cliente,
        rfc,
        STR_TO_DATE(SUBSTRING(rfc, 5, 6), '%d%m%y') AS fecha_raw,
        COALESCE(
            NULLIF(TRIM(correo_electronico), ''), 
            NULLIF(TRIM(telefono), ''), 
            'SIN REGISTRO'
        ) AS contacto_prioritario
    FROM dim_clientes
    WHERE LENGTH(TRIM(rfc)) = 13
),
clientes_normalizados AS (
    SELECT 
        id_cliente,
        nombre_cliente,
        rfc,
        contacto_prioritario,
        CASE 
            WHEN fecha_raw > DATE_SUB(CURDATE(), INTERVAL 18 YEAR) THEN DATE_SUB(fecha_raw, INTERVAL 100 YEAR)
            ELSE fecha_raw
        END AS fecha_nacimiento
    FROM clientes_con_fecha
    WHERE fecha_raw IS NOT NULL
) 
SELECT
    id_cliente,
    nombre_cliente,
    rfc,
    fecha_nacimiento,
    TIMESTAMPDIFF(YEAR, fecha_nacimiento, CURDATE()) AS edad_cliente,
    CASE
        WHEN TIMESTAMPDIFF(YEAR, fecha_nacimiento, CURDATE()) BETWEEN 18 AND 80 THEN 'Válida'
        ELSE 'Revisar'
    END AS estatus_edad,
    contacto_prioritario
FROM clientes_normalizados
ORDER BY id_cliente ASC
LIMIT 15;