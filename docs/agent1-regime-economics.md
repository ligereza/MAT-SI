# Agent 1 — economía de identificar el régimen

El primer bloque identificó dos regímenes con garantías y dejó una pregunta
abierta: esa identificación también consume recursos. Este bloque no añade un
selector general; cobra ese costo explícitamente.

## Modelo

Para un horizonte conocido y un solver afín exacto:

\[
 C_0 = \text{costo de resolver directamente},
 \qquad
 C^* = \min_i(D_i+nA_i),
 \qquad
 I = \text{costo de observar y clasificar el régimen}.
\]

Las dos alternativas end-to-end son:

\[
 \text{DIRECTO}: C_0,
 \qquad
 \text{IDENTIFICAR+SOLVER}: I+C^*.
\]

No hay score ponderado. La decisión estrictamente mejor es

\[
 \boxed{\text{IDENTIFICAR} \iff I < C_0-C^*.}
\]

Si `C_0-C^*≤0`, ningún costo de identificación no negativo puede hacer que
identificar sea estrictamente mejor. Si hay igualdad, el resultado es
`SOLVE_DIRECT`, porque no se declara ventaja donde solo hay empate.

## Consecuencia para amortización

Con una ruta directa `nB` y una transformación `D+nA`, `g=B-A>0`, el costo de
identificación desplaza el umbral a

\[
 I+D+nA<nB
 \iff
 n>\frac{D+I}{g}.
\]

El menor horizonte entero válido es

\[
 n^*=\left\lfloor\frac{D+I}{g}\right\rfloor+1.
\]

Por ejemplo, con `D=3`, `B=10`, `A=2`, el umbral es `1` si `I=0` o `I=2`, y
pasa a `2` si `I=6`. La estructura puede ser real y la clasificación correcta,
pero la ventaja de un solo uso puede desaparecer al cobrar la observación.

## Falsificación mínima

Con horizonte `n=1`, directo cuesta `10`, la ruta transformada cuesta `3+2=5`.
La clasificación es correcta. Pero:

- con `I=1`, identificar cuesta `6` y gana `4` frente a directo;
- con `I=6`, identificar cuesta `11` y pierde frente a directo;
- con `I=5`, empata y no se declara mejora.

Esto refuta la regla informal `clasificación correcta ⇒ identificación útil`.
También muestra por qué el resultado anterior, que comparaba regímenes y
solvers pero no el costo de observarlos, no bastaba para afirmar ventaja
end-to-end.

## Límite del resultado

El teorema es exacto para el caso finito con horizonte conocido, costos
escalares y downstream affine explícito. Para horizonte desconocido, inspección
costosa o grafos implícitos, este bloque se abstiene porque todavía no posee un
solver downstream exacto con la misma semántica de costo.

Estado epistemológico:

- `PROVED`: condición `I < C_0-C^*` y umbral `(D+I)/g`.
- `DISPROVED`: la clasificación correcta no garantiza beneficio total.
- `KNOWN_RESULT`: la desigualdad es una instancia finita de metarrazonamiento
  con costo, no una afirmación de novedad por sí sola.
- `UNKNOWN`: si un clasificador parcial puede estimar o reducir `I` sin ocultar
  su propio costo.

No se creó corpus nuevo ni se modificó `main`.

