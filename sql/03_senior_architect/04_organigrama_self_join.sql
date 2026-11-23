-- =============================================
-- Pregunta de negocio: ¿Quién le reporta a quién dentro de la estructura de Forum?
-- Técnica: SELF JOIN (dim_empleados unida consigo misma: e = colaborador, s = supervisor);
--          LEFT JOIN para conservar a quien no tiene jefe (dirección) y COALESCE para reemplazar los NULL.
-- Nota: incluye empleados activos y dados de baja (historial completo de la estructura).
-- =============================================

SELECT 
    e.id_empleado,
    e.nombre_completo AS nombre_colaborador,
    e.puesto AS puesto_colaborador,
    COALESCE(s.nombre_completo, 'Sin Supervisor Directo') AS nombre_supervisor,
    COALESCE(s.puesto, 'Nivel Dirección') AS puesto_jefe_inmediato
FROM dim_empleados e
LEFT JOIN dim_empleados s
    ON e.id_supervisor = s.id_empleado
ORDER BY nombre_supervisor ASC, nombre_colaborador ASC;