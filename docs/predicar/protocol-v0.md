# PREDICAR v0 — protocolo de preparación

## Estado

Este documento prepara una investigación; no la ejecuta. No se han cargado
datasets, ajustado modelos, calculado scores ni elegido un dominio aplicado.

PREDICAR es un laboratorio neutral de predicción probabilística de estados
finitos con cardinalidad exacta. MAT-SI aporta representación, procedencia,
holdouts, controles negativos y replay; PREDICAR aporta modelos de transición,
observación y distribución predictiva.

## Pregunta

¿Qué estructuras matemáticas, tomadas de áreas maduras y formalmente distintas,
permiten predecir mejor un estado futuro cuando cada estado es un subconjunto de
cardinalidad fija?

El banco inicial es:

```text
universe_size = 25
cardinality = 14
state = binary vector of width 25 with exactly 14 active entries
```

El nombre del banco no identifica un dominio externo. Es sólo una especificación
de cardinalidad y queda parametrizado para futuras variantes `(N, K)`.

## Invariantes

1. Toda observación válida tiene exactamente `K` elementos.
2. Ningún modelo puede devolver estados fuera del soporte válido.
3. El corte temporal de entrenamiento siempre precede al dato puntuado.
4. La distribución completa, no sólo una selección puntual, es el objeto previsto.
5. Las mejoras se comparan contra el mismo baseline, folds y placebos.
6. Una mejora predictiva no se interpreta como causalidad ni control del sistema.
7. Una fuente no disponible permanece `UNAVAILABLE`; nunca se sustituye en silencio.
8. Cada artefacto registra versión de código, configuración, fuente y residuo.

## Familias preparadas

| ID | Familia | Rol inicial |
|---|---|---|
| `uniform_exact` | uniforme sobre el soporte | baseline mínimo |
| `conditional_cardinality` | pesos individuales condicionados a `K` | baseline marginal |
| `pairwise_gibbs` | energía con interacciones | modelo estructural |
| `finite_set_bayes` | filtro bayesiano de conjunto | transferencia RFS |
| `noisy_channel` | recuperación desde observación ruidosa | transferencia de códigos |
| `memory_kernel` | dinámica temporal con memoria | transferencia de procesos puntuales |
| `constraint_weighted` | inferencia bajo restricciones | transferencia CP/SAT |
| `complex_amplitude` | amplitud/fase como challenger | sólo después de baselines |

Las implementaciones concretas aún no se invocan. Sus contratos están en
`src/predicar/` y sus áreas de origen en `src/predicar/adapters/`.

## Evaluación futura

La unidad de evaluación será un boundary prequential:

```text
fit(history <= cutoff)
predict(next state)
observe(after)
score(prediction, after)
append evidence
```

Scores previstos:

- `set_log_score`: log-probabilidad del estado completo observado;
- `marginal_brier`: calibración de cada componente binario;
- `calibration_error`: calibración agrupada por probabilidad;
- `posterior_entropy`: incertidumbre declarada;
- `compute_cost`: coste de inferencia registrado como dimensión separada.

Placebos previstos:

- `temporal_shuffle`;
- `label_permutation`;
- `history_cutoff_shuffle`;
- `random_parameter_placebo`.

## Gates

### Gate P0 — contrato

El estado, el soporte, la procedencia y los límites de datos están definidos.

### Gate P1 — baseline

Se implementan baseline uniforme y baseline condicionado a cardinalidad antes de
probar memoria, interacciones o amplitudes.

### Gate P2 — evaluación

El runner prequential reproduce cada score desde un registro append-only.

### Gate P3 — estructura

Un modelo estructural supera al baseline en bloques futuros y sobrevive placebos.

### Gate P4 — transferencia

La misma familia matemática funciona en al menos dos generadores/adaptadores sin
ramificaciones específicas ocultas.

## Lo que queda deliberadamente fuera

- entrenamiento o inferencia en esta fase de preparación;
- importación de datos de un dominio comercial concreto;
- scraping, cámaras, video o bases privadas;
- claims sobre azar, causalidad o capacidad de intervención;
- deep learning antes de agotar los modelos explícitos;
- datasets voluminosos dentro del repositorio.
