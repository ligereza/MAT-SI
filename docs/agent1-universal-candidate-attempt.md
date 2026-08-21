# Agent 1 — intento directo de teorema universal

Se atacó directamente la posibilidad de evitar varios experimentos positivos.
El resultado separa dos afirmaciones que no deben confundirse.

## Teorema candidato

Sea `Ω` un conjunto no vacío de escenarios factibles y

\[
 \Delta(\omega)=C_0(\omega)-C^*(\omega)-I(\omega).
\]

La regla candidata es:

\[
\begin{array}{rcl}
\inf_{\omega\in\Omega}\Delta(\omega)>0
&\Rightarrow& \texttt{ROBUST\_IDENTIFY\_AND\_SOLVE},\\
\sup_{\omega\in\Omega}\Delta(\omega)\le0
&\Rightarrow& \texttt{DIRECT\_CERTIFIED},\\
\text{en otro caso}
&\Rightarrow& \texttt{ABSTAIN}.
\end{array}
\]

Esta regla es sound y completa **dado el conjunto exacto `Ω`**. Para universos
finitos, `inf` y `sup` son mínimo y máximo, y el programa lo ejecuta
exactamente.

## Contraejemplo de observación parcial

La observación:

\[
 S=\{(C_0=10,C^*=6,I=0)\}
\]

tiene ganancia `4`, por lo que sobre el mundo `Ω₁=S` la decisión es identificar.
Pero el mismo `S` es compatible con:

\[
 Ω_2=S\cup\{(10,9,2)\},
\]

donde el escenario omitido tiene ganancia `-1` y la decisión correcta es
abstenerse.

Cualquier regla que vea únicamente `S` debe devolver lo mismo en ambos mundos;
por tanto se equivoca en al menos uno. Esto no es un fallo de implementación:
es una imposibilidad de inferir una afirmación universal desde un subconjunto
sin una hipótesis de cobertura.

## Resultado del intento directo

- `PROVED`: tricotomía robusta para `Ω` exacto.
- `PROVED`: clausura exacta convierte el caso finito en una instancia del
  teorema parametrizado.
- `DISPROVED`: una observación parcial puede sostener la decisión universal
  para todos sus superconjuntos compatibles.
- `UNKNOWN`: si un generador abierto puede certificar `Ω` exacto sin un axioma
  externo de completitud.

Gate: `UNIVERSALITY_REQUIRES_VERIFIABLE_CLOSURE`.

La conclusión es que sí se ahorran experimentos positivos, pero el problema
central no desaparece: la universalidad queda reducida a demostrar clausura.
Sin esa prueba, el teorema universal sería solo condicional o circular.

