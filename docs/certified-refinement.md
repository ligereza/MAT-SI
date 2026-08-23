# CERTIFIED REFINEMENT

Especificación formal estable y handoff de auditoría. MAT-SI define los
invariantes que una implementación MAK debe respetar sobre el corpus real de
Vibecodeine. No define otra fase de benchmarks, dataset sintético ni PiPi-48.

La investigación de benchmarks queda congelada. MAT-SI sólo se reabre si una
implementación real de MAK expone una contradicción o un invariante faltante.

## 1. Definición mínima

Sea `X` el universo de miembros y sea `S ⊆ X`, normalmente finito y no
vacío. La consulta humana `Q` no es todavía el objeto que el checker evalúa.
Debe existir un contrato explícito:

```text
C = (Q, P, A, K)
```

donde:

- `Q` es la pregunta humana;
- `P : X → {false, true}` es el predicado formal realmente evaluado;
- `A` es la autoridad, fuente y mecanismo de observación permitidos;
- `K` son las condiciones declaradas de soundness, completeness y coverage
  que hacen válidas las observaciones de `A`.

El certificado no afirma directamente `Q`: afirma `P` bajo `C`. Si la
traducción de `Q` a `P` depende de una definición o política, esa traducción
debe quedar explícita en `K` y no puede asumirse por el nombre de `Q`.

Un resumen es una función cuyo tipo incluye su contrato, autoridad y
provenance:

```text
summary = σ_{A,K,L,v}(S) ∈ Σ_{A,K,L,v}
```

Aquí `L ∈ {WORLD_CLAIM, CORPUS_CLAIM, POLICY_CLAIM}` es el nivel de la
afirmación y `v` identifica la versión/provenance aplicable.

Además del payload abstracto, todo summary debe transportar este registro
normativo:

```text
summary = {
    contract_identity: id(C),
    authority: A,
    provenance: provenance(A, K, v),
    n_members: |S|,
    n_covered: |Covered(A, K, S)|,
    invalidation_conditions: I,
    payload: σ(S)
}
```

`n_members` y `n_covered` cuentan miembros únicos del conjunto objetivo, no
filas, aliases ni observaciones duplicadas. Si cualquiera de los conteos no
puede conocerse exactamente, debe representarse como no disponible y no puede
sostener una certificación por ausencia. `I` enumera las mutaciones, cambios
de fuente, cambios de política, expiraciones u otros eventos que invalidan el
summary. Si no se puede evaluar si ocurrió una condición de `I`, el summary
no es certificable y el resultado es `UNKNOWN`.

acompañada, cuando sea necesario, por una concretización `γ(summary)`:
el conjunto de regiones o conjuntos que el resumen admite como posibles.
El contrato mínimo es que el conjunto real `S` esté cubierto por esa
concretización. Un resumen puede ser exacto o conservador; no puede omitir
miembros reales.

La interfaz de decisión es:

```text
certify(C, summary) ∈ {CERTIFIED_NO, CERTIFIED_YES, UNKNOWN}
```

con la semántica universal, siempre respecto de `P` y de `C`:

```text
CERTIFIED_NO  ⇒  ∀x ∈ S, P(x) = false bajo C
CERTIFIED_YES ⇒  ∀x ∈ S, P(x) = true  bajo C
UNKNOWN       ⇒  no se autoriza ninguna inferencia sobre P ni sobre Q
```

La ausencia tiene una precondición adicional. Si la única evidencia es que
`A` no observó `P`, entonces sólo es legal:

```text
n_members(summary) == n_covered(summary)
∧
Complete(A, P, S; K)
∧ Observed_A(P, x) = false para todo x ∈ S
⇒ CERTIFIED_NO
```

Sin igualdad de cobertura o sin `Complete(A, P, S; K)`, el resultado
obligatorio es `UNKNOWN`, salvo que exista otra prueba completa e independiente.
Para `CERTIFIED_YES`, `K` debe contener igualmente las condiciones que hacen
sound a la observación positiva o a la prueba usada; miembros no cubiertos no
pueden ignorarse.

El checker debe derivar el resultado desde el resumen y el contrato `C`,
no desde una estimación de exactitud. Si el resumen es una sobreaproximación,
un certificado sólo es válido cuando la conclusión vale para toda región
posible de `γ(summary)` y bajo las condiciones `A,K`. Un error de soundness
de `P` o una violación de `A,K` invalida el método completo.

Hay tres niveles de afirmación que deben permanecer tipados:

- **`WORLD_CLAIM`:** afirmación sobre el mundo o universo objetivo, más allá
  de lo que una colección observada permite concluir.
- **`CORPUS_CLAIM`:** afirmación sobre `S` y la autoridad/corpus `A` cubiertos.
  Por ejemplo, “no existe `.blend`” en el corpus observado.
- **`POLICY_CLAIM`:** afirmación bajo una política o definición explícita, por
  ejemplo una definición operacional de “3D”.

Un certificado de un nivel inferior no se promociona silenciosamente a otro
superior. “No existe `.blend`” es `CORPUS_CLAIM`; “no es 3D” es
`WORLD_CLAIM`, salvo que “3D” haya sido redefinido mediante una `POLICY`
explícita, en cuyo caso el resultado es `POLICY_CLAIM`.

La especificación trata `S` como no vacío. El caso vacío debe tener una
convención separada (`EMPTY`) para no confundir verdad vacua de `YES` y `NO`.

## 2. Invariantes

Un diseño candidato debe mantener, como mínimo, estos invariantes:

- **Cobertura relativa:** el resumen representa a todos los miembros de `S`
  cubiertos por `A` y por las condiciones `K`, incluso si lo hace con una
  sobreaproximación. Una autoridad incompleta no puede sostener una negación
  por ausencia.
- **Soundness contractual:** ningún `CERTIFIED_YES` ni `CERTIFIED_NO` puede
  ser falso como afirmación sobre `P` bajo `C`. No se permite cambiar de
  `CORPUS_CLAIM` a `WORLD_CLAIM` o `POLICY_CLAIM` sin una regla explícita.
- **Exactitud del UNKNOWN:** `UNKNOWN` significa sólo “este resumen no prueba
  una respuesta”; no significa falso, verdadero ni probablemente verdadero.
- **PROVENANCE tipada:** `A`, `K`, versión, parámetros y nivel de claim son
  parte del tipo de `summary`, no metadata decorativa. Dos payloads iguales
  con distinta autoridad no son intercambiables. Una mutación invalida o
  exige actualizar el resumen.
- **Registro obligatorio:** todo summary lleva `contract_identity`,
  `authority`, `provenance`, `n_members`, `n_covered` e
  `invalidation_conditions`; omitir uno de estos campos lo hace no
  certificable.
- **Cobertura contable:** `n_covered` cuenta miembros únicos cubiertos bajo
  `A,K`; para una certificación por ausencia debe cumplirse exactamente
  `n_members == n_covered`.
- **Invalidación efectiva:** cuando ocurre cualquier condición de `I`, el
  summary deja de ser reutilizable hasta ser reconstruido o validado de nuevo.
- **Compatibilidad contractual:** cada resumen declara la clase de contratos
  `C_σ` para la que sus reglas de certificación son válidas.
- **No-promoción heurística:** grouping aproximado, similarity, clustering o
  equivalencia aprendida no pueden cambiar `n_covered`, completar `K` ni crear
  un claim certificado. Sólo pueden proponer candidatos para refinamiento o
  permanecer como información no certificante.
- **Refinamiento seguro:** los hijos cubren el padre; abrir un hijo no puede
  descartar silenciosamente la parte restante.
- **Costo explícito:** se contabilizan construcción, consulta, memoria,
  refinamiento, residuo, verificación e invalidación por separado.

No se permite convertir probabilidad, tasa histórica de acierto o una señal
heurística en certificado. Se pueden medir probabilísticamente tiempos o
tasas de `UNKNOWN`, nunca la validez lógica del resultado.

## 3. Refinamiento

Para un `UNKNOWN` sobre `S`, un operador de refinamiento produce partes
`S₁, ..., S_k` tales que:

```text
S ⊆ ⋃ᵢ Sᵢ
summaryᵢ = σ(Sᵢ)
```

La cobertura puede ser una partición exacta o una cubierta con solapamiento,
pero el solapamiento debe estar especificado para no falsear conteos y costos.

Para la consulta universal definida arriba, el resultado agregado sólo puede
ser certificado así:

```text
todos los hijos CERTIFIED_NO  ⇒ CERTIFIED_NO en S
todos los hijos CERTIFIED_YES ⇒ CERTIFIED_YES en S
cualquier mezcla o UNKNOWN    ⇒ UNKNOWN en S
```

La mezcla no es un fallo del checker: demuestra que `P` no es uniforme en la
cubierta actual. Refinar puede resolver un `UNKNOWN` si separa regiones con
comportamiento uniforme; no existe obligación de que todo refinamiento
termine en una certificación.

`UNKNOWN` no es un estado terminal desde el que se pueda responder `Q`. Cuando
el summary actual no certifica, la siguiente operación autorizada es refinar
`S` (o aportar una prueba completa independiente que pase el mismo contrato);
hasta entonces la respuesta permanece `UNKNOWN`.

Definimos provisionalmente, para una estructura de refinamiento o índice `X`,

```text
R(q, X) = cantidad de nodos/partes cuyos resúmenes o residuos
          deben abrirse antes de certificar la respuesta de q
```

En la especificación estable, `q` es abreviatura de `P` bajo el contrato `C`.

El nodo raíz cuenta como uno si su resumen es consultado. Si no se certifica,
`R` es `∞` para una trayectoria exitosa, o se reporta como “no certificado”
con el presupuesto consumido. `R` mide resolución estructural, no trabajo
total ni una dimensión intrínseca del orden.

## 4. Composición, reutilización y economía

Para dos conjuntos `U` y `V` debe existir, cuando se reivindique composición,
una operación
`⊔` tal que:

```text
σ(U ∪ V) = σ(U) ⊔ σ(V)
```

o al menos un resumen construido por esa operación que siga siendo sound.
La operación también debe especificar cómo combina `A`, `K` y el nivel de
claim. Idealmente `⊔` tiene identidad para el conjunto vacío y es asociativa y
conmutativa, salvo equivalencia representacional. La composición puede perder
precisión y aumentar `UNKNOWN`; no puede crear un certificado inseguro ni
ocultar que una autoridad es incompleta.

Un resumen es **reusable** si se construye sin conocer una consulta concreta
y `certify` admite múltiples contratos compatibles de `C_σ` sin reconstruir
`σ`. La compatibilidad exige identidad contractual coincidente o una prueba
explícita de compatibilidad, autoridad/provenance suficiente y condiciones `K`
vigentes. La reutilización no implica que una consulta arbitraria sea
compatible ni que el resumen sea un quotient mínimo.

“Cheaper” no significa simplemente menor `R`. El criterio provisional es un
vector de recursos:

```text
construcción + memoria + consultas certificadas
+ refinamiento/residuo + verificación + invalidación
```

debe eliminar trabajo real frente a evaluar `q` sobre todos los miembros,
para una carga de consultas especificada. `R` es una dimensión del reporte,
no un sustituto de ese vector.

## 5. Residue

En el lenguaje MAT-SI, una representación puede separarse como:

```text
S = S_resumido ∪ S_residue
```

`S_residue` contiene miembros o condiciones que el resumen no puede decidir.
No es evidencia negativa ni una aproximación que pueda ignorarse: requiere
inspección exacta, refinamiento o una certificación independiente. Para una
consulta concreta, el residuo puede quedar vacío aunque exista en otras
consultas. Si el residuo proviene de una autoridad `A` incompleta, tampoco
puede convertirse en `CERTIFIED_NO` por ausencia.

Por tanto, `G` debe reinterpretarse como costo de construir/organizar
resúmenes y `residue` como trabajo conservado fuera del certificado. No hay
“Lift Gain” mientras no se demuestre un ahorro neto con unidades comparables.

## 6. Relación con líneas conocidas

Las siguientes correspondencias son analogías estructurales, no identidades:

- **Abstract interpretation:** comparte dominio abstracto, concretización,
  sobreaproximación y soundness. CERTIFIED es una conclusión universal sobre
  el abstracto; la especificación añade un árbol operativo de refinamiento y
  una contabilidad de costo.
- **Branch-and-bound:** un bound puede podar un nodo cuando prueba una
  condición. Aquí `CERTIFIED_NO`/`YES` cumplen una función análoga, pero no se
  restringe a optimización y la respuesta `YES` también exige universalidad.
- **BVH e índices espaciales:** una caja disjunta de la región objetivo puede
  certificar `NO`, y una caja contenida puede certificar `YES`; de lo contrario
  se desciende. Es un modelo geométrico útil, no la teoría general.
- **Interval arithmetic:** con intervalos hacia afuera, un rango completamente
  falso o completamente verdadero permite certificar; un rango que cruza la
  frontera produce `UNKNOWN`. El redondeo no puede romper soundness.
- **Constraint propagation:** estrecha dominios y puede alcanzar un estado que
  prueba una propiedad. Propagar no equivale por sí solo a tener un resumen
  reusable ni a haber resuelto la consulta.
- **Database indexes:** pueden eliminar candidatos o producir una lista para
  verificación exacta. Ausencia/presencia de candidatos no equivale a la
  semántica universal de `CERTIFIED_NO`/`YES`; un false positive del índice
  debe seguir siendo `UNKNOWN`, no certificado. La ausencia sólo es una
  negación cuando el índice es `Complete(A,P,S;K)` para ese predicado.
- **Future equivalence:** un quotient exacto bajo todas las consultas futuras
  compatibles puede funcionar como resumen reusable. Pero un resumen puede ser
  query-specific o no mínimo, y un quotient descubierto por oracle no prueba
  que sea descubrible sin pagar su costo.
- **Separator states / order width:** los separadores pueden controlar cuánta
  información o cuántos nodos deben atravesarse. `R(q,X)` captura una medida
  operacional relacionada, pero no se llama Dimensión del Orden ni demuestra
  una propiedad de ancho.
- **CODEINE `UNKNOWN/CONTINUE`:** `UNKNOWN` aquí comparte la disciplina de no
  concluir y continuar explorando. En CODEINE es una política/estado de
  ejecución; aquí es una salida semántica que debe preservar soundness.
- **MAT-SI `G + residue`:** aporta el marco de costo y fallback residual. La
  nueva línea exige además un contrato formal de certificado, una refinación
  con cobertura y consultas compatibles.

## 7. Relectura de resultados MAT-SI

PiPi-42 a PiPi-47B quedan como restricciones arquitectónicas congeladas, no
como una invitación a extender la cadena de benchmarks:

- **Future-equivalence discovery es caro:** el quotient calculado con
  `suffix_sums` es `GROUND_TRUTH/ORACLE`; pagar esa construcción no demuestra
  discovery barato. La arquitectura no lo usa como primitivo implícito.
- **Width solo es insuficiente:** order width, Cross Axis y separadores pueden
  orientar `R`, pero no certifican una consulta ni predicen por sí solos el
  costo real.
- **El contenido de la representación importa:** el resumen y `P` deben
  operar sobre la representación observada bajo `A`, no sobre una clase
  geométrica o un grupo que ignore contenido relevante.
- **El costo de discovery importa:** `G` es parte del costo normativo, junto
  con memoria, residencia, refinamiento, verificación e invalidación.
- **El lift autónomo no sobrevivió:** no se adopta una afirmación de lift ni
  un escalar que oculte unidades de trabajo incomparables.
- **Closure accessibility no sobrevivió como mecanismo suficiente:** puede
  sugerir rutas de refinamiento, pero no constituye un `certify` universal.
- **Blind reuse/grouping falló exactitud:** los merges aproximados no pueden
  aumentar cobertura, completar `K` ni producir claims certificados.
- **Drift detection sí sobrevivió:** detección de cambios, versiones y
  condiciones de invalidación pasa a ser un requisito obligatorio del summary.
- **Un `G` reusable suministrado sí puede amortizar:** una estructura externa
  ya construida puede ser reutilizada si su contract identity, autoridad,
  provenance, cobertura e invalidación son compatibles. Eso no prueba que MAK
  pueda descubrirla autónomamente.

La consecuencia es deliberada: **grouping no es el primitivo de la nueva
arquitectura**. El primitivo es un summary conservador, tipado por contrato y
autoridad, que sólo puede certificar `P` bajo `C`; el agrupamiento puede ser una
representación interna no certificante.

Los resultados congelados de PiPi-42, PiPi-43 y PiPi-47B no se reescriben ni se
convierten retrospectivamente en evidencia más fuerte de la que contienen.

## 8. Tres contraejemplos que pueden matar la idea

1. **Refinamiento total:** una estructura tiene hojas alternadas `q=true` y
   `q=false`, sin ningún nodo interno uniforme. Todo resumen sound devuelve
   `UNKNOWN` hasta abrir todas las hojas. Si el costo de construir el índice se
   suma, no existe ahorro frente al recorrido plano.

2. **Consultas que separan todos los miembros:** sea `Q` la familia
   `q_a(x) := (x = a)` sobre un universo arbitrario. Un resumen pequeño que no
   conserva la información necesaria no puede certificar respuestas para todos
   los `a`; uno que sí lo hace termina codificando esencialmente `S`. Esto
   rompe la combinación simultánea de composabilidad, reutilización y bajo
   costo, salvo que se restrinja explícitamente `Q_σ`.

3. **Autoridad incompleta o provenance equivocada:** si `A` no es completa para
   `P`, la ausencia de observaciones no certifica `NO`. Además, dos resúmenes
   con el mismo payload no son intercambiables si su autoridad difiere, por
   ejemplo:

   ```text
   [min_date, max_date, source=release_date]
   [min_date, max_date, source=mtime]
   ```

   Si se mezclan o se reutiliza el segundo como si fuera el primero, el
   certificado puede ser falso aunque los números coincidan. La deriva de `S`
   produce el mismo problema: sin invalidación se rompe soundness; con una
   verificación completa se puede perder todo el ahorro. Un Bloom filter o una
   tasa empírica de acierto no puede resolverlo.

## 9. Requisitos de evidencia si MAK exige una comprobación

No hay otro benchmark planificado. Si una implementación real de MAK expone
una contradicción o un invariante faltante y exige una comprobación empírica,
antes de gastar CPU deben estar fijados por escrito:

1. El universo de miembros, el contrato `C=(Q,P,A,K)`, el nivel de claim, la
   clase compatible `C_σ`, la estructura de refinamiento y la regla de
   cobertura. Debe quedar claro qué parte es `WORLD`, `CORPUS` o `POLICY`.
2. El dominio del resumen, su concretización o prueba equivalente, y un
   checker que pueda auditarse de forma independiente. `A` y `K` deben ser
   auditables y no se aceptan certificados probabilísticos.
3. Pruebas de composición, soundness exhaustiva o demostrada en el alcance
   elegido, refinamiento sin pérdida de cobertura y comportamiento explícito
   ante `UNKNOWN`, ausencia sin completeness, autoridad equivocada, mutación,
   claim promotion y solapamiento.
4. Parámetros y consultas congelados antes de cualquier held-out; incluir
   negativos y casos adversariales donde la consulta no sea uniforme.
5. Un baseline raw y un vector de costos que incluya `G`, memoria, consulta,
   `R`, residuo, refinamiento, verificación e invalidación. `GF2 row_xor_ops` y
   nodos DPLL no deben compararse como si fueran la misma unidad.
6. Resultados que distingan respuestas certificadas, `UNKNOWN`, costo de
   discovery y costo amortizado. `wall_ms` debe marcarse como medición no
   reproducible byte-a-byte; las reglas, entradas, certificados y conteos
   deterministas deben separarse de ella.

La comprobación sólo merece ejecutarse si existe una contradicción concreta o
un invariante faltante que resolver, y si puede medir ahorro neto después de
pagar construcción, residuo y mantenimiento. No autoriza crear otra PiPi ni
reanudar la cadena de benchmarks por conveniencia.

## 10. Efecto de esta enmienda

La enmienda cambia tres invariantes: la soundness pasa a ser soundness de `P`
bajo `C`, la cobertura pasa a ser relativa a `A,K`, y la proveniencia pasa a
ser parte nominal del tipo del resumen. Añade además una invariante de
**no-promoción de claims**. También restringe composición y reutilización:
los payloads no pueden combinarse sólo porque sus valores coincidan.

Los dos primeros contraejemplos permanecen sin cambios. El tercero se
fortalece: ya no es sólo deriva o sobreaproximación insegura, sino también
ausencia observada con autoridad incompleta y confusión de provenance. Este
contraejemplo puede matar soundness antes de medir cualquier ahorro.
