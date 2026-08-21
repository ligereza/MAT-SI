# Phase 4B — transferencia desde experiencia real

Phase 4B reemplaza los fixtures sintéticos de 4A por evidencia local preexistente.
No se copiaron historiales privados al repositorio; solo se congelaron sus rutas,
timestamps, hashes, procedencia y roles.

## Fuentes congeladas

La congelación ocurrió en `7a2ebb2` antes de diseñar adaptadores:

- A: bitácora real de una sesión operativa, 5.947 bytes;
- B: export JSON real de evidencia/eventos de investigación, 5.745.417 bytes;
- C: catálogo CSV real de sesiones, reservado como held-out.

No se escribieron eventos a mano ni se sintetizaron reemplazos.

## Adaptación sin inventar semántica

A produjo 13 bloques markdown ordenados. Se derivaron profundidad de encabezado,
conteo de líneas, bytes y rangos de línea. Acción, outcome y costo quedaron
`UNKNOWN`.

B produjo 42 eventos explícitos. Se conservaron índice de hoja y estados observables
de evento/fecha/enlace/duplicación. Los estados no se promovieron a acciones,
outcomes ni costos; esos tres campos quedaron `UNKNOWN`.

Cada derivación conserva `RAW_SOURCE`, `DERIVATION`, `LOSS`, `RESIDUE` y
`PROVENANCE`. Los nombres de dominio, productores, archivos y etiquetas humanas se
ocultan en el pass ciego.

## Ataque al envelope

El envelope de 4A puede transportar los registros si acepta campos desconocidos, por
lo que no se concluye que sea una representación incorrecta. Pero A+B no ofrecen una
tríada comparable de:

`action + measured outcome + cost`.

El mecanismo genérico intentó igualdad y aumento sobre campos derivados y encontró
22 coincidencias estructurales de contexto/observación, pero cero relaciones
conductuales elegibles. No se inventó una predicción a partir de ellas.

## C y contaminación del held-out

Durante la inspección inicial se consultó accidentalmente el encabezado y una muestra
de C antes de congelar G. C no participó en la adaptación, descubrimiento ni
predicción, pero su evaluación held-out queda invalidada por esa contaminación. El
resultado la registra explícitamente y no afirma transferencia real.

## Gate

**B — DATA/OBSERVABILITY IS THE BOTTLENECK.**

La idea sigue siendo comprobable, pero las historias reales disponibles no registran
observables comparables suficientes para congelar G. No se implementaron productos ni
se avanzó a Phase 5.

Resultado reproducible: `results/phase4b-real-experience-transfer-results.json`.
