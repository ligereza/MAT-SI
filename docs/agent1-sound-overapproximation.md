# Agent 1 — decisiones universales con sobre-aproximación certificada

Este bloque ataca `UNIVERSALITY_REQUIRES_VERIFIABLE_CLOSURE`. La pregunta ya
no es si se conoce exactamente `Ω`, sino si existe un `U` certificadamente
sonoro con `Ω⊆U` y una cota de `Δ` que separe cero.

## Auditoría de teoría existente

La idea central no se reclama como nueva:

| Elemento | Clasificación | Fuente primaria / relación |
|---|---|---|
| `Ω⊆U`, concretización y semántica aproximada | `ESTABLISHED_THEORY` | [Cousot & Cousot 1977](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml) |
| frameworks, Galois connections, widening/narrowing | `ESTABLISHED_THEORY` | [Cousot & Cousot 1992](https://cs.nyu.edu/~pcousot/COUSOTpapers/JLC92.shtml) |
| fixpoints de funciones monótonas | `ESTABLISHED_THEORY` | [Tarski 1955](https://msp.org/pjm/1955/5-2/pjm-v5-n2-p11-p.pdf) |
| refinamiento por contraejemplo espurio | `ESTABLISHED_THEORY` | [Clarke et al., CEGAR](https://web.stanford.edu/class/cs357/cegar.pdf) |
| restricciones lineales como abstracción | `ESTABLISHED_THEORY` | [Cousot & Halbwachs 1978](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL78.shtml) |
| representación booleana compacta y peor caso exponencial | `ESTABLISHED_THEORY` | [Bryant 1986](https://people.eecs.berkeley.edu/~russell/classes/cs289/f04/readings/Bryant%3A1986.pdf) |
| peor caso sobre un conjunto de incertidumbre | `ESTABLISHED_THEORY` | [Ben-Tal & Nemirovski 1998](https://pubsonline.informs.org/doi/10.1287/moor.23.4.769) |

MAT-SI solo aporta en este bloque una instanciación explícita: el objeto
`Δ=directo-(downstream+identificación)`, la separación ejecutable `Ω/U/L`, la
salida de abstención y la contabilidad del costo de refinamiento. Eso es
`MAT-SI_INSTANTIATION`, no una nueva teoría de interpretación abstracta.

## Objeto formal

La teoría usa:

- `Ω`: universo verdadero de mundos compatibles;
- `U`: sobre-aproximación con certificado `Ω⊆U`;
- `L`: subcolección de testigos concretos con `L⊆Ω`;
- `Δ`: beneficio neto escalar, fijado aquí como un recurso explícito;
- `LB(U)≤inf_U Δ` y `UB(U)≥sup_U Δ`.

La regla segura es:

\[
LB(U)>0\Rightarrow\texttt{CERTIFIED\_IDENTIFY},
\qquad
UB(U)\le0\Rightarrow\texttt{CERTIFIED\_DIRECT}.
\]

En cualquier otro caso se abstiene. Un testigo `x∈L` con `Δ(x)≤0` refuta
`UNIVERSAL_IDENTIFY`; uno con `Δ(x)>0` refuta `UNIVERSAL_DIRECT`. `L` nunca
prueba por sí solo una afirmación universal.

## Fragmento simbólico no enumerativo

Los mundos son `x∈{0,1}^d`. `U` es una caja booleana: algunos bits están fijos
y el resto son libres. Para

\[
Δ(x)=c+\sum_i a_i x_i,
\]

los extremos se calculan bit a bit:

\[
\min_UΔ=c+\sum_{a_i<0}a_i,
\qquad
\max_UΔ=c+\sum_{a_i>0}a_i,
\]

ajustando los bits fijos. El algoritmo usa `O(d)` tiempo, `O(d)` espacio y
enumera `0` mundos. Con `d=32`, la caja inicial representa `2^32` mundos.

Este es el fragmento tractable:

- **Input:** dimensión `d`, bits fijos de `U`, coeficientes racionales de `Δ`;
- **assumption:** `Ω⊆U` está certificado;
- **algorithm:** extremos afines independientes por bit;
- **complexity:** `O(d)`;
- **guarantee:** decisión universal segura si el intervalo no cruza cero;
- **boundary:** restricciones generales que no son cajas ya no tienen este
  solver simbólico.

## Casos ejecutados

### A — sobre-aproximación estricta suficiente

`U` deja los 32 bits libres, mientras `Ω` fija `x[0]=1`. Con
`Δ=1+x[0]`, `LB(U)=1`, así que se certifica `IDENTIFY` aunque `U` contiene
mundos que no pertenecen a `Ω`.

El caso dual usa `Δ=-2-x[0]`, con `UB(U)=-2`, y certifica `DIRECT`.

### B — abstracción demasiado gruesa y refinamiento

Con `Δ=3+2x[0]-5x[1]`, la caja libre tiene intervalo `[-2,5]` y debe
abstenerse. La evidencia de que `x[1]=1` es espuria permite refinar a
`x[1]=0`; entonces `LB=3` y se certifica `IDENTIFY`.

### C — ambigüedad irreducible

Con `Δ=1-2x[0]` y `Ω=U` libre, existen testigos positivos y negativos. No hay
refinamiento honesto que elimine uno: la decisión permanece `ABSTAIN`.

### Contraejemplo real

En el caso B, si `x[1]=1` es realmente compatible, el refinamiento se rechaza.
El testigo `x[0]=0,x[1]=1` tiene `Δ=-2` y refuta la identificación universal.

### Regresión `+4/-1`

`Δ=4-5x[0]` reproduce exactamente el caso anterior: el testigo observado
`x[0]=0` da `+4`, pero la caja sonora conserva `LB=-1`, por lo que no se
certifica identificar.

## Teoremas y límites

1. **Soundness:** si `Ω⊆U` y `LB(U)≤inf_UΔ`, entonces `LB(U)>0` implica
   `∀ω∈Ω:Δ(ω)>0`; análogamente `UB(U)≤0` implica decisión directa segura.
2. **Exact closure no es necesaria:** los casos A muestran decisiones
   certificadas con `Ω⊂U` estricto.
3. **Completeness decision-relative:** en este fragmento, la abstracción es
   completa para una decisión si el intervalo calculado sobre `U` separa cero
   cuando la decisión verdadera sobre `Ω` tiene margen separado. No se exige
   reconstruir `Ω`.
4. **Abstracción no sonora:** si `Ω⊄U`, un extremo positivo o negativo de `U`
   no ofrece garantía; el control ejecutable devuelve `UNSOUND_ABSTRACTION`.

El refinamiento de un bit es una instancia pequeña de CEGAR. Un fixpoint
abstracto no se interpreta aquí como cierre concreto: el experimento principal
usa restricciones, no una transición recursiva. La función `set_bit_to_one`
solo muestra el compromiso mínimo `Post(γ(A))⊆γ(Post#(A))` en una transición
concreta elegida.

## Resultado epistemológico

- `PROVED`: un sobre-aproximador sonoro puede reemplazar el cierre exacto para
  decisiones de signo separadas.
- `PROVED`: el fragmento boolean-box/afín es simbólico y no enumerativo.
- `PROVED`: la subaproximación falsifica afirmaciones universales.
- `DISPROVED`: toda abstracción gruesa puede decidir o todo refinamiento puede
  borrar un testigo negativo.
- `KNOWN_RESULT`: la estructura es abstract interpretation/robust reasoning y
  CEGAR conocido.
- `UNKNOWN`: si una representación abierta de MAT-SI puede construir `U` sonoro
  y completo para una clase más amplia sin una hipótesis externa.

Gate: `SOUND_ENVELOPE_CAN_REPLACE_EXACT_CLOSURE_FOR_SIGN_SEPARATION`.

