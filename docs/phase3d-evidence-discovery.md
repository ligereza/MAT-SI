# Phase 3D — descubrimiento de evidencia

Phase 3D prueba el paso `observaciones -> relación falsificable`. El oráculo de
Phase 3C permanece sellado hasta después de generar y congelar las hipótesis,
probarlas en held-out y ejecutar el control negativo.

## Congelación

`main` fue avanzado por fast-forward hasta `d5b50f8` y la rama de trabajo es
`phase3-evidence-discovery`. El manifiesto de entradas quedó congelado en
`0d1b2b4`.

El manifiesto de descubrimiento conserva únicamente:

- hashes exactos de A, B y N;
- ordinal de la unidad ejecutable;
- cuatro entradas de descubrimiento y cuatro entradas held-out;
- la afirmación de que no hay salidas esperadas, etiquetas semánticas ni relación
  manual.

El origen público se adquiere por hash. Los nombres y la descripción semántica del
comportamiento no participan en la generación de hipótesis.

## Descubrimiento

La misma unidad restringida de ejecución de Phase 3C produjo observaciones ordinarias:

`(input, output_A, output_B, provenance)`.

El lenguaje mínimo usado fue una comparación binaria genérica sobre las dos salidas:
`==`, `<=` y `>=`. No contiene propiedades del dominio. Las tres hipótesis que
encajaron en las cuatro observaciones de descubrimiento fueron conservadas con:

- `evidence_for` y `evidence_against`;
- `description_cost`;
- cobertura;
- procedencia de cada observación.

No se seleccionó la primera hipótesis. El digest de la lista completa se congeló
antes de observar held-out.

## Held-out y control negativo

Las tres hipótesis sobrevivieron las cuatro entradas held-out. Al reutilizar el mismo
G estructural frente al control negativo:

| hipótesis | held-out positivo | control negativo |
|---|---|---|
| `A.output == B.output` | SURVIVED | FALSIFIED |
| `A.output <= B.output` | SURVIVED | SURVIVED |
| `A.output >= B.output` | SURVIVED | FALSIFIED |

El control negativo coincide estructuralmente con el candidato (`structural_match_to_G
= true`). Por tanto, la distinción proviene de las consecuencias observadas, no de
una diferencia de forma.

La evidencia permite afirmar que se descubrió, entre otras hipótesis, la relación
`A.output == B.output`. No permite afirmar una descripción semántica más fuerte que
esa igualdad observada.

## Oráculo sellado

Solo después de la generación, congelación, held-out y control negativo se abrió el
vector de Phase 3C. Ambas fuentes producen las salidas selladas y satisfacen la
igualdad descubierta. Esto valida la hipótesis; no participó en su generación y no se
promovió la igualdad a una descripción semántica completa.

## G real de Phase 3B

El digest de G sigue coincidiendo con el resultado congelado. C/N1/N2 mantienen sus
coincidencias estructurales, pero G no expone una frontera de entrada ejecutable, un
contrato de salida comparable ni fixtures seguros para dependencias, estado y
efectos. Resultado:

`STRUCTURE_FOUND_BUT_NO_OBSERVABLE_CORRESPONDENCE_CAN_BE_DERIVED`.

No se generaron hipótesis conductuales para esas fuentes y no se intentó resolver la
carencia.

## Límite epistemológico para LLM

Un LLM futuro podría proponer H, pero su confianza no es evidencia. La propuesta
debe pasar exactamente por:

`proposal -> evidence_for/evidence_against -> held-out -> SURVIVED/FALSIFIED/UNKNOWN`.

No se construyó integración LLM.

## Gate

**A — EVIDENCE DISCOVERY DEMONSTRATED.**

MAT-SI derivó relaciones desde observaciones, las congeló, las probó fuera de muestra
y rechazó una similitud estructural engañosa. Phase 4 no comienza.

Resultado reproducible: `results/phase3d-evidence-discovery-results.json`.
