# Agent 1 — incertidumbre conjunta y ajuste de la regla

La hipótesis de este bloque era que los intervalos independientes podían ser
demasiado conservadores porque el costo de identificar `I` y la ganancia bruta
`G` no son necesariamente independientes.

## Modelo conjunto

En vez de conservar solo dos intervalos, se conserva un conjunto finito de
escenarios factibles:

\[
 \Omega\ni\omega=(C_0(\omega),C^*(\omega),I(\omega)).
\]

La ganancia end-to-end de identificar en un escenario es

\[
 \Delta(\omega)=C_0(\omega)-C^*(\omega)-I(\omega).
\]

Por tanto, para una `Ω` finita:

\[
\begin{array}{rcl}
\min_{\omega\in\Omega}\Delta(\omega)>0
&\Rightarrow& \texttt{ROBUST\_IDENTIFY\_AND\_SOLVE},\\
\max_{\omega\in\Omega}\Delta(\omega)\le0
&\Rightarrow& \texttt{DIRECT\_CERTIFIED},\\
\text{en otro caso}
&\Rightarrow& \texttt{ABSTAIN\_JOINT\_UNCERTAIN}.
\end{array}
\]

Esta tricotomía es exacta para la evidencia conjunta suministrada: no supone
probabilidades ni inventa una media.

## La sospecha se confirma

Considérese:

\[
\omega_1=(C_0=10,C^*=6,I=0),
\qquad
\omega_2=(C_0=10,C^*=0,I=9).
\]

En ambos escenarios `Δ>0` (`4` y `1`), por lo que el conjunto conjunto
certifica identificar. Pero sus envolventes independientes son:

\[
 I\in[0,9],
 \qquad
 G\in[4,10].
\]

Como `I_max < G_min` es falso y `I_min >= G_max` también es falso, el modelo
independiente debe abstenerse. La correlación recupera una decisión que los
intervalos pierden.

Esto no prueba que la dependencia de costos pueda inferirse automáticamente.
Solo prueba que descartarla puede destruir certificados válidos.

## Ajuste y límite

El modelo conjunto es más informativo, pero exige justificar qué escenarios son
realmente compatibles. Si `Ω` omite un escenario posible, la garantía es falsa.
Por eso se conserva el origen de cada escenario y no se sustituye la evidencia
por una correlación estimada.

Estado epistemológico:

- `PROVED`: decisión robusta exacta sobre una `Ω` finita declarada.
- `PROVED`: los intervalos independientes son suficientes en algunos casos, pero
  no necesarios; pueden abstenerse aunque `Ω` certifique identificar.
- `DISPROVED`: la hipótesis de que la envolvente independiente conserva todos
  los certificados conjuntos.
- `UNKNOWN`: cómo construir `Ω` sin introducir escenarios manuales o perder
  escenarios posibles.

El siguiente ataque debe falsificar precisamente esa construcción de `Ω`; no
debe asumir que una correlación observada equivale a causalidad ni a validez
fuera del conjunto de evidencia.

