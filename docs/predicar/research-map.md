# PREDICAR — mapa de investigación

La estrategia es importar matemáticas de campos que ya resolvieron problemas
parciales de predicción, inferencia, ruido, cardinalidad o memoria. Cada área es
un adaptador; ninguna define por sí sola la interpretación de PREDICAR.

## 1. Random finite sets / multi-object tracking

Problema externo: inferir y predecir conjuntos de objetivos a partir de
detecciones incompletas, falsas alarmas y asociaciones ambiguas.

Importar:

- filtros Bayesianos de conjunto;
- cardinality distributions;
- multi-Bernoulli, GLMB y PMBM;
- data association;
- métricas de distancia entre conjuntos.

Uso PREDICAR: primer adaptador aplicado y puente con sensores visuales baratos.

## 2. Neural population coding

Problema externo: modelar patrones binarios colectivos y su probabilidad conjunta.

Importar:

- máxima entropía;
- modelos pairwise/Ising;
- actividad poblacional `K`;
- likelihood de patrones;
- condiciones sobre estímulo o contexto.

Uso PREDICAR: laboratorio de estados binarios con cardinalidad controlada.

## 3. Física estadística

Problema externo: describir configuraciones discretas mediante energía, temperatura
y función de partición.

Importar:

- modelos Gibbs;
- Ising con magnetización fija;
- campo medio;
- MCMC;
- transiciones y concentración.

Uso PREDICAR: generadores sintéticos con mecanismo conocido y pruebas de recuperación.

## 4. Teoría de códigos

Problema externo: recuperar un estado válido después de un canal ruidoso.

Importar:

- modelos de canal;
- belief propagation;
- mensajes locales;
- decodificación y confidence;
- trade-off entre exactitud y coste.

Uso PREDICAR: separar incertidumbre del proceso e incertidumbre de observación.

## 5. Procesos puntuales

Problema externo: predecir eventos futuros con intensidad dependiente de la historia.

Importar:

- kernels de memoria;
- autoexcitación;
- decaimiento y retorno de información;
- estados latentes de intensidad.

Uso PREDICAR: dotar de dinámica temporal a modelos que conservan cardinalidad.

## 6. Constraint programming / weighted inference

Problema externo: buscar, contar o muestrear estados que satisfacen restricciones.

Importar:

- restricciones de cardinalidad;
- CP-SAT y Max-SAT;
- weighted model counting;
- factibilidad y explicación de restricciones.

Uso PREDICAR: asegurar soporte válido y comparar inferencia probabilística contra
solvers combinatorios.

## Criterio de selección

Una idea entra al núcleo sólo si aporta al menos una de estas propiedades:

- mejora la representación del soporte exacto;
- mejora la inferencia bajo observación parcial;
- incorpora memoria explícita;
- ofrece una métrica probabilística reproducible;
- tiene un baseline o placebo claro;
- puede separarse del dominio original.

Una analogía física, una arquitectura popular o una mejora in-sample no bastan.
