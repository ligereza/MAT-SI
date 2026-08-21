# Phase 4C — observabilidad mínima

Phase 4C parte del commit `6df7498` y trabaja en la rama
`phase4-minimum-observability`. Congela dos salidas preexistentes antes de mapear
campos:

- MAT-SI: `results/phase2-self-reference-results.json`;
- VIBECODEINE: export JSON real congelado en `corpus/phase4c-observability-manifest.json`.

No se reescribieron historiales y no se fabricaron acciones, outcomes, éxito,
progreso ni costos ausentes.

## Resultado mínimo

El contrato mínimo que sobrevive a los contraejemplos es:

```text
before       observación opaca del estado o snapshot medido
intervention token opaco de la frontera/evento observado
after        observación opaca del estado o snapshot posterior
provenance   fuente + derivación + pérdida + residuo + procedencia
```

`resources` es opcional. Si existe, conserva dimensiones independientes medidas
(`instruction_count`, `cpu_ms`, `bytes_written`, etc.); no se colapsa a un costo
escalar. Los valores de dominio permanecen en el snapshot/residuo, no en un
catálogo de etiquetas universales.

`action`, `outcome`, `success`, `progress` y `stuck` no sobreviven como campos
semánticos obligatorios. Una acción puede aparecer más tarde como interpretación
de `intervention`; un resultado puede derivarse de comparar `before` y `after` bajo
una hipótesis explícita. Ninguna de esas interpretaciones se incrusta en el registro
base.

## Falsificación del contrato

Se construyeron pares analíticos, no históricos, que difieren solo en cada campo:

- sin `before`, dos transiciones con distinto estado inicial parecen iguales;
- sin `intervention`, la misma transición puede atribuirse a eventos distintos;
- sin `after`, no existe efecto observable que pueda refutar una hipótesis;
- sin `provenance`, una observación medida y una derivada con los mismos valores son
  indistinguibles y no auditables.

Por ello los cuatro campos son mínimos para una futura prueba de trayectoria. La
auditoría de cada campo contiene exactamente `RAW_SOURCE`, `DERIVATION`, `LOSS`,
`RESIDUE` y `PROVENANCE`.

## Dos sistemas existentes

MAT-SI ya contenía la frontera necesaria en su salida de Phase 2: reglas
representadas antes/después, transformación representada, procedencia y una medida
`instruction_count`. Sus tres candidatos emiten el mismo contrato; el nombre del
candidato se enmascara como posición de fila.

VIBECODEINE tiene 42 eventos y observaciones enlazadas por `event_id`. Se producen
40 registros `evento → observaciones` a partir de esos enlaces existentes. El evento
se usa como `before`, el identificador como intervención opaca y las observaciones
como `after`, sin afirmar que el cambio tenga significado operacional. Dos eventos
no tienen observaciones enlazadas y quedan en `unavailable_after`; no se inventa su
posterior. Esta adaptación demuestra transporte del contrato, no disponibilidad de
acción semántica, outcome medido o recursos.

La autoaplicación MAT-SI emite el mismo contrato sin instrumentación nueva: su salida
de Phase 2 ya contiene los cuatro elementos. Para VIBECODEINE, el hook mínimo futuro
es append-only en el cierre de cada evento: `before_state_digest`, token opaco,
`after_state_digest` cuando el bloque de observaciones cierre, `source_ref` y cada
recurso medido como dimensión independiente. Los valores faltantes permanecen
ausentes.

## Límites y semántica de almacenamiento

El registro no permite observar por sí solo significado de dominio, éxito o un delta
semántico: para eso debe conservarse el residuo referenciado. MAT-SI no tiene
wall-clock/CPU/memoria en la salida congelada; VIBECODEINE no tiene acción, outcome
medido ni vector de recursos. El JSON y el filesystem son transporte; solo aparecen
en procedencia y no aportan semántica.

Resultado reproducible: `results/phase4c-minimum-observability-results.json`.

## Gate

**A — MINIMUM OBSERVABILITY IDENTIFIED.**

Se identificó el contrato mínimo `before + intervention opaca + after + provenance`.
Esto no declara transferencia predictiva ni inicia Phase 5; únicamente resuelve qué
debe observarse para poder falsarla después y cuál es el hook mínimo para los datos
que todavía no lo registran.
