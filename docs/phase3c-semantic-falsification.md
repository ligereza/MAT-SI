# Phase 3C — falsificación semántica

Phase 3C pregunta si una regularidad descubierta por el mecanismo estructural de
Phase 3B puede validarse o rechazarse mediante consecuencias observables, sin
introducir una ontología universal.

## Congelación

La rama parte de `e9d018e`, el commit final de Phase 3B. `main` fue avanzado por
fast-forward hasta ese commit antes de crear `phase3-semantic-falsification`.

El `G` se recalcula únicamente a partir de A/B del manifiesto de Phase 3B y se
compara con el digest ya publicado. C/N1/N2 no participan en su construcción.
El control independiente quedó congelado en `5a5e972` antes de producir los
resultados:

- dos implementaciones públicas de `clamp`;
- un control negativo comparable;
- un vector de tres intervenciones: límite inferior, valor interior y límite superior;
- hashes y procedencia de cada fuente.

## Evidencia positiva

El candidato estructural de las dos implementaciones positivas se construye antes
de consultar el oráculo. Después, un adaptador de ejecución restringida observa las
funciones extraídas. No es el evaluador MAT-SI ni una IR universal: solamente acepta
el subconjunto de control necesario para este experimento y únicamente permite
`min` y `max` como llamadas.

| fuente | observación | resultado |
|---|---|---|
| `positive_a` | `[-2, 0, 1]`, `[0.5, 0, 1]`, `[2, 0, 1]` | `[0, 0.5, 1]` |
| `positive_b` | mismas entradas | `[0, 0.5, 1]` |
| `negative_local` | misma interfaz y superficie comparable | `[1, 1, 2]` |

El negativo también coincide estructuralmente con el `G` positivo, pero es rechazado
por la consecuencia observable. Esto demuestra que la evidencia conductual puede
falsificar al menos una similitud estructural engañosa.

Fuentes positivas: [TedAlden clamp](https://gist.github.com/TedAlden/1a30101620d2152ab84e9e26b80e8384)
y [chriscamacho raymath](https://gist.github.com/chriscamacho/63a9427deca505634f162e882e369172).

## Resultado sobre el falso positivo real

C, N1 y N2 conservan el resultado de Phase 3B: tienen coincidencias estructurales
y ventaja descriptiva. Las intervenciones sobre el primer nodo compartido cambian
la coincidencia estructural de `True` a `False`, pero no producen una consecuencia
de comportamiento: el `G` congelado no contiene una semántica ejecutable suficiente.

Por tanto, para esas fuentes la evidencia es `UNKNOWN`, no `PASS` ni `FAIL`.
El resultado confirma que el `G` de 3B es descriptivo y no predictivo en esas
secciones; no se modificaron el adaptador AST, la anti-unificación, la compresión ni
el corpus real congelado.

## Clasificación de semántica

- `HOST`: parseo Python, adquisición/verificación de fuentes, ejecución restringida
  del control y comparación con el oráculo.
- `REPRESENTED`: U AST neutral, `G`, coincidencias, intervenciones, relaciones de
  evidencia y procedencia como datos ordinarios.
- `DERIVED`: reconstrucción, match estructural, igualdad con el oráculo y `UNKNOWN`
  cuando no existe un oráculo seguro.

No se añadió una IR universal, un AST semántico, embeddings, un clasificador, una
regla de dominio ni una plataforma de ejecución completa.

## Gate

**A — BEHAVIORAL FALSIFICATION WORKS.**

La evidencia observable distingue una abstracción reutilizable de una similitud
engañosa en el control positivo/negativo. El falso positivo de los repositorios
reales sigue abierto como `UNKNOWN` y queda explícitamente registrado. Phase 4 no
comienza.

Resultados reproducibles: `results/phase3c-semantic-falsification-results.json`.
