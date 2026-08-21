# Phase 4 — transferencia cross-domain

Phase 4 prueba si una relación descubierta en dos dominios puede tener valor
predictivo en un tercero sin etiquetas semánticas de dominio.

## Corpus y envelope

Se congelaron tres familias pequeñas e independientes de registros, sin ingerir
proyectos completos. El envelope común mínimo es:

`context, observation, action, outcome, cost, provenance`.

El envelope solo transporta estructura. Los valores permanecen opacos y el adaptador
registra por separado:

- `PRESERVED`: campos, cronología, adyacencia, transiciones observables y costos;
- `NORMALIZED`: identidad de fuente, trayectoria y procedencia a tokens opacos;
- `LOST`: nombres de dominio, productores, etiquetas de trayectoria, nombres de
  archivos e interpretación humana;
- `RESIDUE`: hashes y campos retirados.

El dominio C no se cargó ni adaptó hasta después de congelar G.

## Descubrimiento A+B

El adaptador enumeró relaciones genéricas de igualdad y orden sobre los campos
observables, sin usar etiquetas de dominio. La relación máxima común encontrada fue:

- en los dos primeros pares de eventos: igualdad de `action`, `observation` y
  `outcome`, con aumento de `cost`;
- en el siguiente par: la misma combinación como predicción de continuación.

G se congeló con digest
`cf5ec8c3856a8c279d368ec41e48a1994d01afc172c19d5266c78f64ed09da80` y no se cambió
al revelar C.

## C held-out

C contiene cuatro ventanas. G coincide estructuralmente con tres:

- dos continuaciones satisfacen la predicción;
- una continuación es productiva pese a la misma forma del prefijo y falsifica la
  predicción;
- una cuarta ventana no coincide.

La transferencia predictiva sobre ventanas coincidentes es `2/3 = 0.6667`. El
baseline sin G, usando la clase modal de la propiedad de continuación sobre las
cuatro ventanas, es `2/4 = 0.5`. Gain: `0.1667`.

La ventana productiva demuestra que el sistema no colapsa `repetición == mala`:
hay transferencia estructural, pero el resultado conductual decide si la predicción
sobrevive.

## Transferencias separadas

- `STRUCTURAL_TRANSFER`: observada; G identifica 3/4 ventanas de C.
- `BEHAVIORAL_TRANSFER`: observada con falsificación; 2 sobreviven y 1 falla.
- `PREDICTIVE_TRANSFER`: observada; supera el baseline sin G.

No se implementaron CODEINE, X-ANA-X, VIZZ ni KETAMINE.

## Gate

**A — CROSS-DOMAIN TRANSFER DEMONSTRATED.**

Una relación generada desde A+B conserva valor predictivo medible en C sin etiquetas
de dominio. La evidencia no autoriza todavía una ontología común ni una regla
universal sobre repetición.

Resultado reproducible: `results/phase4-cross-domain-results.json`.
