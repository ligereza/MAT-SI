# Agent 1 — identificación de régimen algorítmico

Esta es una contracción deliberada de la búsqueda de representaciones. La
pregunta no es si MAT-SI puede resolver cualquier meta-problema, sino si unas
invariantes observables bastan para identificar un régimen matemático conocido
antes de seleccionar un solver. La función de identificación es parcial y puede
devolver `ABSTAIN`.

## Objeto formal

Una observación neutral es

\[
 o=(h,\{(D_i,A_i)\}_{i=1}^m,B,V,I,G,d),
\]

donde:

- `h` indica si el horizonte es conocido, desconocido o no observado;
- `D_i` es el costo de preparación de una ruta reutilizable;
- `A_i` es su costo por uso;
- `B` es un costo directo por uso, cuando está observado;
- `V` indica si los valores de las opciones están disponibles;
- `I` contiene costos de inspección;
- `G` indica si el grafo de rutas y sus transiciones están completo;
- `d` es la cantidad de dimensiones de objetivo.

La identificación es una función parcial

\[
K(o)\in\{\texttt{KNOWN\_HORIZON\_AFFINE},
\texttt{UNKNOWN\_HORIZON\_TWO\_SLOPE},
\texttt{COSTLY\_OPTION\_INSPECTION},
\texttt{EXPLICIT\_ROUTE\_GRAPH},\bot\}.
\]

`⊥` se materializa como `ABSTAIN`. Un certificado solo afirma que las premisas
estructurales son visibles; no afirma que la transformación sea rentable.

## Dos solvers con garantías explícitas

### Horizonte conocido

Para una cartera finita explícita,

\[
 C_i(n)=D_i+nA_i,
 \qquad
 C^*(n)=\min_i C_i(n).
\]

`solve_known_horizon_affine` evalúa exactamente ese mínimo en `O(m)` tiempo y
`O(m)` espacio. Esto es un resultado elemental y conocido; se implementa aquí
como certificado de que el clasificador no necesita inventar un score.

### Horizonte desconocido: dos pendientes

Hay una ruta directa con costo por uso `B` y una ruta transformada con costo
`D+nA`, con `0 ≤ A < B`. Sea `g=B-A`. La política es:

\[
 k=\left\lfloor\frac{D}{g}\right\rfloor,
 \quad\text{usar directo durante }k\text{ usos},
 \quad\text{comprar antes del uso }k+1.
\]

Para un horizonte real `n ≤ k`, la política paga `nB` y como `ng ≤ D` el
óptimo offline tampoco mejora comprando. Para `n > k`, la política paga

\[
 P(n)=kB+D+(n-k)A=D+nA+kg.
\]

 Como `n>k=floor(D/g)`, se cumple `ng>D` y el óptimo offline compra, de modo
 que `OPT(n)=D+nA`. Además `kg≤D`; por tanto

\[
 \frac{P(n)}{OPT(n)}
 \le 1+\frac{kg}{D+nA}
 \le 2.
\]

Así, en este modelo concreto la política es `2`-competitiva. El resultado es
un caso de ski-rental conocido, no una afirmación de novedad de MAT-SI.

## Falsificaciones mínimas

1. **Régimen no implica beneficio:** con horizonte `n=1`, directo `10` y
   transformación `4+1·9=13`, el clasificador identifica correctamente el
   régimen afín, pero el solver elige `SOLVE_DIRECT`.
2. **No todo horizonte desconocido es dos pendientes:** dos opciones
   transformadas hacen que la clasificación se abstenga; no se aplica la
   garantía de dos pendientes por semejanza superficial.
3. **La abstención no es un solver:** la inspección costosa se reconoce como
   familia `COSTLY_OPTION_INSPECTION`, pero queda `CLASSIFIED_BUT_SOLVER_DEFERRED`.
4. **Objetivos incomparables:** con dos dimensiones se abstiene; no se crea una
   suma ponderada.

## Estado epistemológico

- `PROVED`: el mínimo afín es exacto; la política de dos pendientes satisface
  el límite `2` bajo sus premisas.
- `KNOWN_RESULT`: los dos regímenes y sus solvers de referencia existen en
  teoría previa; esta rama no los presenta como descubrimiento.
- `DISPROVED`: clasificar un régimen no implica que transformar sea rentable.
- `UNKNOWN`: todavía no está demostrado que identificar el régimen, cobrando
  el costo de observarlo, reduzca el costo total de extremo a extremo.

No se creó corpus nuevo. El programa usa únicamente instancias finitas mínimas
para falsificar la frontera elegida. El siguiente experimento, si se justifica,
debe medir el costo de identificación contra la ventaja máxima disponible y
debe poder terminar en `ABSTAIN`.
