# Agent 1 — experimento único de cierre de escenarios

Este bloque ejecuta una afirmación deliberadamente acotada:

> una regla declarativa sobre un dominio finito puede generar todos sus
> escenarios, coincidir con un oráculo exhaustivo independiente y mantener una
> ventaja end-to-end positiva.

## Regla congelada

El dominio tiene dos modos `m∈{0,1}` y produce:

\[
 C_0(m)=10,
 \qquad
 C^*(m)=6-6m,
 \qquad
 I(m)=9m.
\]

Los escenarios son:

\[
 m=0: (10,6,0), \quad \Delta=4,
\]

\[
 m=1: (10,0,9), \quad \Delta=1.
\]

El costo de identificación `I` ya está incluido en la ganancia neta; no se
presenta una ventaja que ignore el costo de generar la estructura.

## Resultado positivo

El generador produce exactamente los dos escenarios del oráculo independiente:

- `generated_count = 2`;
- `oracle_count = 2`;
- no hay escenarios faltantes ni extras;
- `min net gain = 1`;
- la decisión robusta es `ROBUST_IDENTIFY_AND_SOLVE`.

Por tanto, la tesis sobre esta clase finita es exitosa: hay cierre y ventaja
end-to-end dentro del dominio declarado.

## Falsificación negativa

Se ejecutó el mismo generador eliminando deliberadamente `m=1`. El generador
parcial aún podría emitir una decisión favorable sobre lo que ve, pero el
oráculo detecta el escenario faltante. El resultado es
`CLOSURE_FALSIFIED`.

Esto confirma que el cierre no se obtiene por observar que la decisión actual
parece buena. Debe compararse contra el dominio completo.

## Alcance exacto

El experimento no demuestra una clausura universal. Demuestra una afirmación
condicional y reproducible:

\[
\text{regla correcta} + \text{dominio finito completo}
\Rightarrow
\text{cierre verificable} + \text{decisión robusta}.
\]

Estado epistemológico:

- `PROVED`: coincidencia del generador y oráculo en la clase finita congelada.
- `PROVED`: ventaja neta positiva en todos sus escenarios.
- `DISPROVED`: omitir un modo puede invalidar el cierre aunque la decisión
  parcial parezca favorable.
- `UNKNOWN`: si un generador abierto puede probar completitud fuera de un
  dominio finito declarado.

Gate: `SUCCESS_WITHIN_FINITE_DECLARED_CLASS_ONLY`. No se creó corpus nuevo, no
se tocó `main` y no se mezcló Agent 2.

