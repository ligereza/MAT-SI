# WACHUMA — modelo de desarrollo, cultivo y animación

Estado: especificación matemática de MAT-SI para una implementación
procedural en WACHUMA. No es una reconstrucción biológica validada de un
ejemplar, ni un predictor hortícola. Distingue resultados anatómicos de reglas
generativas que deberán calibrarse contra observaciones longitudinales.

## 1. Decisión de modelo

La unidad animable no es una malla ni un tallo aislado: es un organismo con
memoria de desarrollo. La escena mantiene un grafo de tallos y meristemos:

```text
X(t) = (G(t), M(t), A(t), W(t), E(t), H(t))
```

- `G(t)`: grafo de tallos; la raíz visual, cada columna y cada brazo son
  nodos, con relaciones padre-hijo.
- `M(t)`: meristemos apicales activos, uno por punta que puede generar tejido.
- `A(t)`: areolas, con identidad permanente, edad, posición y estado.
- `W(t)`: estado hídrico/turgencia reversible.
- `E(t)`: entradas de cultivo y ambiente (luz, temperatura, riego, estrés,
  estación, poda o daño).
- `H(t)`: historia inmutable de nacimientos, transiciones y parámetros usados.

La malla es una observación derivada de `X(t)`. No se anima escalando un tubo,
pegando una tapa, interpolando un brazo completo ni aleatorizando una flor en
cada frame.

## 2. Restricciones biológicas que sí informan la arquitectura

En cactus columnares, las areolas representan yemas axilares persistentes. Las
costillas y sus surcos transportan sus areolas hacia afuera y abajo conforme
crece el tejido subapical; una areola puede producir espinas, una rama o una
flor. Por tanto, rama y flor deben salir de una areola identificable y no de
una posición arbitraria sobre la superficie.

La posición de las areolas conserva un registro del desarrollo: las más nuevas
se encuentran en la corona periférica del ápice y las más antiguas han sido
advectadas hacia abajo. El punto matemático central no es una areola; existe
una zona meristemática finita alrededor de él.

Las costillas tienen un componente hídrico reversible. El diseño rib-and-furrow
permite variar volumen de agua sin que cada cambio sea crecimiento irreversible.
Una animación debe separar expansión/contracción de la producción permanente de
tejido.

Para `Echinopsis pachanoi`, las referencias morfológicas describen costillas
anchas y redondeadas, areolas sobre sus crestas y flores grandes, usualmente en
areolas superiores, de apertura nocturna. La frecuencia exacta de ramificación,
el umbral de floración y la filotaxis de un clon concreto no quedan demostrados
por esta especificación.

Fuentes de partida:

- J. Mauseth, [Structure--Function Relationships in Highly Modified Shoots of
  Cactaceae](https://pmc.ncbi.nlm.nih.gov/articles/PMC2803597/).
- Mauseth et al., [Constant distance between leaf initiation sites permits
  non-destructive analysis of apical meristem activity during cactus shoot
  growth](https://pmc.ncbi.nlm.nih.gov/articles/PMC12401885/).
- [Shape and size adjustments of a cactus with rib and furrow
  morphology](https://www.sciencedirect.com/science/article/abs/pii/S014019631630204X).
- [Ficha morfológica de *E. pachanoi*](https://www.cactus-art.biz/schede/TRICHOCEREUS/Trichocereus_pachanoi/Trichocereus_pachanoi/Trichocereus_pachanoi.htm).

## 3. Costillas como historia de nacimientos

### Primario apical frente a secundario axilar

La extensión del tallo principal tiene una sola fuente primaria: el meristemo
apical del brote (`SAM`). En una idealización temporal:

```text
H(t) = H0 + integral_0^t v_SAM(tau) d tau
tau_k <= t  iff  el primordio k ha sido iniciado
```

La base permanece como referencia material y el nuevo tejido se incorpora en la
corona. Para un primordio ya iniciado, una ley mínima de advección es:

```text
age_k(t) = clamp((t - tau_k) / (T - tau_k))
z_k(t) = H(t) [s_apex - Delta(age_k)]
```

`H(t)` puede cambiar por cultivo; `Delta` representa expansión subapical y no
una animación de un cactus adulto escalado globalmente. Las costillas y areolas
son la memoria material de esa producción apical.

Una rama es otro meristemo, pero no es crecimiento primario del tronco. Sólo
puede crearse si existe una areola `a_k` cuyo estado sea `vegetative` y si una
condición de liberación secundaria está presente:

```text
create_child(a_k) iff
  a_k in A and state(a_k) == vegetative and release(a_k, E, H) == true
```

La dominancia apical y la liberación de yemas tienen respaldo general en
Cactaceae y en biología de brotes; `release`, sus umbrales y sus pesos son
parámetros de política hasta que existan series temporales del mismo clon.

Cada nuevo primordio/areola recibe una identidad al nacer:

```text
a_k = (id_k, t_k, theta_k, rib_k, state_k)
theta_k = theta_0 + k alpha mod 2pi
```

`alpha` no se fija al ángulo áureo. Es un parámetro de un perfil de especie,
clon o ejemplar que se debe estimar si existe evidencia. Las costillas son
ortóstiquias: trayectorias longitudinales de nacimientos relacionados, no
rayas superpuestas sobre un cilindro.

Una posición longitudinal se obtiene por advección desde la corona:

```text
s_k(t) = s_apex - D(t - t_k)
D(0) = 0;  D'(age) >= 0
```

`D` debe tener una zona juvenil suave y una zona madura aproximadamente lineal.
Así se representa la compactación visual cerca del ápice sin comprimir
artificialmente toda la columna.

La geometría de un tallo puede escribirse:

```text
Sigma(s, theta, t) =
  ( r(s, theta, t) cos(theta),
    r(s, theta, t) sin(theta),
    z(s, theta, t) )

r = R(s,t) + A(s,t) f_n(theta - Phi(s,t)) + delta_nodes(s,theta,t)
```

`f_n` es un perfil ancho, suave y periódico de `n` costillas. `delta_nodes`
no sustituye las costillas: agrega la ondulación sutil de cada módulo/areola.
Una formulación conservadora es una suma de kernels C2 localizados:

```text
delta_nodes = sum_k taper(s_k)
  [ a_g K((s-s_k)/ell_s, d(theta,theta_k)/ell_theta)
  - a_n K((s-(s_k+delta_s))/ell_s, d(theta,theta_k)/ell_theta) ]
```

donde `K` es compacto, no negativo y C2, y `d` es distancia angular circular.
El primer término da la elevación tenue de la areola; el segundo, desplazado
ligeramente hacia el ápice, representa la depresión transversal visible encima
de ella. Ambos desaparecen de manera suave en el polo apical para evitar una
singularidad de estrella.

### Controles de sección, pulpa y espinas

Los controles visuales deben corresponder a parámetros explícitos, no a una
deformación arbitraria del mesh horneado. Para un módulo `u in [-1,1]`, sea
`c(u)=cos(pi u)` la diferencia crest-valle y `rho in [0,1]` el redondeo interno:

```text
p_rho(u) = 1 + alpha c(u) + 0.18 rho alpha [1 - c(u)]
```

El término de control es cero en la cresta y eleva progresivamente el fondo del
valle. Así `rho=0` conserva la sección base y `rho=1` suaviza el perfil sin
eliminar las costillas, cambiar `n` ni romper la identificación de los valles
compartidos. `rho` es una decisión geométrica calibrable; no es una medición
histológica.

La referencia SVG tampoco se proyecta como una pegatina sobre el tallo. Se
extrae su estructura cromática radial y se aplica a la banda interior:

```text
q(r) = clamp(r / r_core, 0, 1)
P(r) = (1 - gamma) B + gamma lerp(P_light, P_mid, P_dark; q(r))
```

`P_light` representa la pulpa verde clara central, `P_mid` la transición y
`P_dark` la pulpa exterior más oscura; `gamma` controla el contraste. `r_core`
y `gamma` son controles de representación, mientras que el SVG es sólo la
provenance visual de esa paleta y no una autoridad anatómica 3D.

Para las espinas, el abanico de cada areola conserva sus slots y sólo escala
la longitud generada:

```text
d_jk = normalize(cos(alpha_k) N_j + sin(alpha_k) T_j + v_jk e_z)
L_jk = spine_scale L0 activity_j age_factor_j lambda_k
```

El parámetro `spine_scale` modifica el alcance común y no crea/elimina
espinas. Los valores `alpha_k`, `lambda_k` y el número de slots siguen siendo
hipótesis del perfil hasta ser comparados con fotografías longitudinales del
mismo ejemplar o clon.

## 4. Tres escalas temporales

| Escala | Estado dominante | Resultado visual | Reversibilidad |
| --- | --- | --- | --- |
| horas--días | `W(t)` | respiración radial leve de costillas | sí |
| semanas--meses | meristemo | altura, nuevas areolas y advección | no |
| estaciones--años | yemas | brazos, botones, flores y arquitectura de mata | parcialmente |

Un estado hídrico mínimo:

```text
dW/dt = (W_target(E,t) - W) / tau_W
R(s,t) = R_dry(s) [1 + eta(s) W(t)]
```

La expansión debe alterar sobre todo la apertura de surcos y el volumen,
manteniendo identidad de las costillas. No debe crear nuevas areolas ni alterar
la edad de las existentes.

El crecimiento de altura de un meristemo `v` se modela mediante una compuerta:

```text
dH_v/dt = q_v g(E,t)
g(E,t) = sigmoid(w_T T + w_L L + w_W W - w_S Stress)
```

La sigmoide y sus pesos son una interfaz de simulación, no una ley fisiológica
demostrada para pachanoi. Cada fuente y cada perfil de cultivo debe declarar
sus parámetros, unidad y alcance.

## 5. Areolas: decisión, no decoración

Cada areola usa una máquina de estados:

```text
nascent -> spinous -> dormant
dormant -> vegetative -> shoot_meristem
dormant -> floral -> floral_bud -> anthesis -> senescent
dormant -> aborted
```

Una transición sólo se permite desde una areola existente, madura y cubierta
por la política de cultivo elegida. Un puntaje de activación útil para animación
es:

```text
S_veg(k,t) =
  w_m maturity_k + w_r reserve_v - w_d dominance(k,t)
  + w_x disturbance_v - w_c competition_v

S_floral(k,t) =
  u_m maturity_k + u_e exposure_k + u_q seasonal_cue(E,t)
  - u_d dominance(k,t) - u_s stress_v
```

La activación determinista ocurre sólo si el score supera un umbral configurado
y las precondiciones son válidas. Si se usa aleatoriedad para variedad visual,
debe estar sembrada y quedar registrada en `H(t)`; no puede simular conocimiento
botánico ausente.

La dominancia apical puede representarse como un campo que decrece desde la
punta del tallo padre:

```text
dominance(k,t) = D0(t) exp(-distance_on_shoot(k, apex)/lambda_D)
```

Poda o daño reducen `D0` localmente y permiten un escenario explícito de
liberación de yemas. Esto representa la idea general de dominancia apical, no
un umbral experimentalmente probado para *E. pachanoi*. Véase la
[revisión de dominancia apical](https://pmc.ncbi.nlm.nih.gov/articles/PMC10400159/).

## 6. Ramas y arquitectura de mata

Una rama es un nuevo nodo del grafo, nacido desde una areola vegetativa:

```text
child.origin = Sigma_parent(s_k, theta_k, t_birth)
child.parent_areole = id_k
child.meristem = active
```

La dirección inicial mezcla la normal de la superficie con el vector vertical:

```text
T_child(0) = normalize(cos(beta) N_parent + sin(beta) e_z)
dT_child/dt = kappa [ e_z - (T_child . e_z) T_child ]
```

Esto produce salida lateral inicial y reorientación ascendente, sin insertar un
tubo rígido. El hijo genera su propia corona, costillas, areolas y memoria de
desarrollo.

El sistema debe soportar dos modos arquitectónicos diferentes:

1. **Pup/corona basal:** varias yemas en el dominio inferior producen columnas
   casi verticales. Es el modo prioritario para una mata adulta como las fotos
   de referencia.
2. **Brote axilar lateral:** una areola de un tallo maduro activa un hijo que
   sale lateralmente y se endereza por tropismo gravitacional.

No se debe inferir que toda areola madura ramificará. La selección de areolas
es una hipótesis de perfil, condicionada por edad, reserva, dominancia,
perturbación y espacio disponible.

## 7. Floración como ruta de la misma yema

Una flor no nace en el polo geométrico ni se añade como accesorio. Una areola
superior y madura puede transitar a `floral_bud`. Para el simulador:

```text
Q_f(t) = integral_0^t floral_gate(E(tau)) d tau
allow_flower(k) iff mature(k) and upper_zone(k)
                    and Q_f > Theta_f and S_floral > theta_f
```

La trayectoria visual debe incluir botón, elongación, antesis nocturna y
senescencia. `floral_gate` es intencionalmente configurable: la evidencia
disponible apoya localización superior y apertura nocturna, pero no justifica
afirmar un disparador cuantitativo universal para todos los clones o cultivos.

## 8. Contrato de datos de cultivo

Los controles de usuario no son verdades biológicas; son entradas declaradas:

```text
CultivationEvent = {
  time, kind, value, unit, source,
  specimen_or_culture_id, confidence, notes
}
```

`kind` puede incluir `irrigation`, `light_exposure`, `temperature`, `pruning`,
`damage`, `repotting` y `observation`. Un `GrowingGuideClaim` debe mantener
fuente, especie/clon, condiciones, evidencia y revisión. Nunca convertir un
riego observado en una regla universal ni prometer una fecha real de floración.

Parámetros que deben vivir en un perfil versionado por material/cultivo:

```text
rib_count, alpha, plastochron, D(age), hydration_response,
dominance_length, branch_threshold, floral_threshold,
geometry_seed, model_version
```

## 9. Invariantes implementables

- Una areola conserva `id`, padre y tiempo de nacimiento; no se reordena entre
  frames.
- Una rama o flor debe referenciar una areola existente y una transición válida.
- El crecimiento añade historia; no modifica retroactivamente nacimientos.
- Agua altera `W` y geometría reversible, no la topología de areolas.
- Cada meristemo hijo genera sus propios módulos; no recibe una malla adulta.
- Los parámetros, fuentes, semilla y versión se serializan con el asset.
- Si faltan condiciones para una transición, el estado se conserva como
  `dormant` o `UNKNOWN`; no se inventa una decisión.
- Toda afirmación de cultivo conserva autoridad/provenance y alcance de especie,
  clon y condiciones.

## 10. Primer slice de animación recomendado

No empezar por una flor al azar. Implementar una secuencia acelerada y
reproducible:

```text
seco -> riego -> expansión reversible de costillas
-> nacimientos en corona apical -> advección/elongación
-> activación explícita de una yema basal
-> brote hijo con su propio ápice y costillas
```

Después, usar la misma máquina de estados para demostrar la ruta floral con un
perfil de escenario marcado como `procedural-hypothesis`. El criterio visual es
que cada cambio sea legible como consecuencia de una historia, no como morph o
accesorio añadido.

## 11. Límite científico y programa de calibración

El modelo es generativo y modulable, no una imitación estática. Sin embargo,
la plausibilidad no prueba poder predictivo. Para calibrarlo se requieren
series temporales del mismo ejemplar, con escala, identidad del clon, fechas,
riego, temperatura, luz, poda/daño y observaciones de cada areola activada.

Hasta entonces, los scores, umbrales, `alpha`, ritmos y reglas de floración son
**POLICY/PROCEDURAL CLAIMS**, no `WORLD CLAIMS`. La interfaz debe exponerlo y
permitir cambiar perfiles sin reescribir la geometría.
