# Agent 1 — costo incierto de identificación

El costo exacto `I` del bloque anterior se reemplaza por evidencia intervalar:

\[
 I\in[I_{\min},I_{\max}],
\]

sin interpretar el intervalo como una distribución de probabilidad. El
downstream permanece deliberadamente exacto: `C*` es el mínimo afín certificado
y `C₀` es el costo directo observado.

Definimos la ganancia bruta:

\[
 G=C_0-C^*.
\]

La política robusta tiene tres salidas:

\[
\begin{array}{rcll}
I_{\max}<G &\Rightarrow& \texttt{ROBUST\_IDENTIFY\_AND\_SOLVE},\\
I_{\min}\ge G &\Rightarrow& \texttt{DIRECT\_CERTIFIED},\\
I_{\min}<G\le I_{\max} &\Rightarrow& \texttt{ABSTAIN\_COST\_UNCERTAIN}.
\end{array}
\]

Si `I_max` no existe y `I_min<G`, tampoco se certifica identificar. El fallback
operacional seguro es directo, pero el resultado conserva `ABSTAIN` para no
confundir seguridad con una prueba de optimalidad.

## Resultado formal

Para downstream exacto, la tricotomía anterior es necesaria y suficiente para
las tres afirmaciones robustas disponibles desde el intervalo:

- identificar es estrictamente mejor para todo `I` admisible;
- directo es al menos tan bueno para todo `I` admisible;
- o la evidencia permite ambos casos y no certifica una elección estricta.

No se usa promedio, confianza inventada ni score ponderado. La incertidumbre se
conserva como conjunto de costos posibles.

## Contraejemplo mínimo

Con `C₀=10` y `C*=5`, `G=5`:

- `[0,4]` permite identificar robustamente;
- `[5,8]` permite elegir directo robustamente;
- `[4,6]` cruza el límite y obliga a abstenerse;
- `[0,∞)` tampoco permite certificar identificación.

La clasificación del régimen puede ser perfecta en los cuatro casos. Lo que
falla en los dos últimos no es la semántica del régimen, sino la información
suficiente sobre el costo de obtenerla.

Estado epistemológico:

- `PROVED`: tricotomía robusta para downstream exacto.
- `DISPROVED`: un intervalo que cruza el umbral no justifica una elección
  estricta sin evidencia adicional.
- `UNKNOWN`: qué observaciones mínimas permiten estrechar `I` sin que el costo
  de estrecharlo consuma la ganancia.

El bloque no crea corpus nuevo y no toca `main`.

