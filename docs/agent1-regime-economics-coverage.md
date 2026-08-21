# Agent 1 — ataque de completitud de escenarios

Una decisión robusta sobre `Ω` solo prueba una afirmación universal si `Ω`
contiene todos los escenarios factibles. La ejecución anterior no demostraba
esa cobertura.

## Falsificación por challenger

Para cada escenario `ω`, sea

\[
 \Delta(\omega)=C_0(\omega)-C^*(\omega)-I(\omega).
\]

Si el conjunto declarado certifica identificar (`Δ>0` para todos), un solo
escenario omitido con `Δ≤0` falsifica el certificado. Si declara directo
(`Δ≤0` para todos), un omitido con `Δ>0` lo falsifica.

El auditor ejecuta exactamente esta prueba. Un challenger del mismo signo no
falsifica la decisión, pero tampoco demuestra completitud.

## Resultado

La sospecha de incompletitud queda confirmada constructivamente:

\[
\Omega_d=\{(10,6,0),(10,0,9)\}
\]

certifica identificar, porque sus ganancias netas son `4` y `1`. Al añadir el
escenario omitido

\[
 (10,9,2),
 \qquad \Delta=-1,
\]

el resultado pasa a `ABSTAIN_JOINT_UNCERTAIN`; el certificado original era
falso como afirmación sobre el conjunto ampliado.

## Cuándo puede hablarse de cobertura

El programa permite definir una familia finita explícita mediante el producto
cartesiano de ejes de costos y enumerarla por completo. Solo en relación con
esa familia declarada puede aparecer:

`COVERAGE_COMPLETE_FOR_DECLARED_FINITE_DOMAIN`.

Esto no demuestra que la familia sea el universo real; demuestra únicamente
que no faltan combinaciones dentro del universo finito que se especificó.
Una enumeración parcial queda marcada como
`COVERAGE_INCOMPLETE_FOR_DECLARED_FINITE_DOMAIN`.

Estado epistemológico:

- `PROVED`: un escenario omitido de signo contrario falsifica el certificado.
- `KNOWN_RESULT`: cobertura completa es demostrable respecto de un universo
  finito explícitamente enumerado.
- `UNKNOWN`: un generador abierto puede probar que no omite escenarios posibles.

El siguiente paso no debe añadir más escenarios manuales. Debe atacar si existe
una regla de cierre verificable para el generador de escenarios; si no existe,
la salida correcta es conservar `UNKNOWN`/`ABSTAIN`.

