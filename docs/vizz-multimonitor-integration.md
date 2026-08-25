# VIZZ — integración geométrica multi-monitor

Estado: integración experimental de MAT-SI para FARMAKSIA/VIZZ.

Esta integración convierte la hipótesis de eye tracking de una relación
dependiente de una cámara perpendicular y una pantalla en una representación
geométrica explícita: rayos de mirada, pose de cabeza, planos físicos de
monitores y demanda focal. No implementa una cámara, un modelo neuronal ni una
corrección clínica de refracción.

## Decisión arquitectónica

La tubería recomendada es:

```text
imagen de cámara
  → landmarks / pose de cabeza
  → vector de mirada en coordenadas del ojo
  → vector de mirada en coordenadas del mundo
  → intersección con planos de monitores
  → monitor + coordenadas locales + distancia
  → demanda focal / representación VIZZ
```

No se debe entrenar como primitiva principal:

```text
imagen → píxel global de escritorio
```

Ese mapeo puede funcionar en una geometría fija, pero mezcla cámara, cabeza,
monitor, distancia y usuario. Al mover una pantalla o añadir otra, no hay una
transformación explícita que pueda recalibrarse o auditarse.

El kernel ejecutable está en `src/matsi/vizz_geometry.py`. Es deliberadamente
agnóstico de cámara y de ML: recibe un `GazeRay` ya calibrado y una colección de
`ScreenPlane` físicos.

## Modelo geométrico

Cada pantalla `m` lleva:

```text
O_m       origen físico, por convención esquina superior izquierda
u_m       eje horizontal
v_m       eje vertical
n_m       normal, u_m × v_m
W_m       ancho en metros
H_m       alto en metros
```

Una mirada es un rayo:

```text
r(λ) = o + λ d
```

La intersección con el plano es:

```text
λ = ((O_m - o) · n_m) / (d · n_m)
X_m = o + λ d
```

Las coordenadas locales normalizadas son:

```text
x_m = ((X_m - O_m) · u_m) / W_m
y_m = ((X_m - O_m) · v_m) / H_m
```

Una pantalla es candidata solo si `λ > 0` y `x_m,y_m ∈ [0,1]`. Si no hay
intersección, el kernel devuelve ausencia geométrica; la capa de autoridad debe
decidir si eso significa `UNKNOWN`, fuera de dominio o no-hit físico.

La distancia sobre el rayo y la demanda óptica son:

```text
z_m = λ
D_m = 1 / z_m
```

`D_m` está en dioptrías cuando `z_m` está en metros. El ángulo entre dos
monitores se calcula con el producto punto de sus normales.

## Calibración separada

La calibración debe tener capas independientes:

1. **Intrínsecas de cámara:** matriz `K` y distorsión.
2. **Extrínsecas de escena:** transformación cámara-mundo.
3. **Pose de cada monitor:** esquinas físicas, ArUco, AprilTag, ChArUco o
   seguimiento de características naturales.
4. **Pose de cabeza y ojos:** landmarks y modelo de cabeza.
5. **Visual axis offset:** diferencia individual entre eje óptico y eje visual.
6. **Validación:** objetivos no usados durante el ajuste y movimiento de cabeza.

La perpendicularidad de cámara puede simplificar la primera versión, pero no
debe aparecer como una precondición matemática del contrato. La pose de cada
monitor debe poder cambiar sin reescribir el modelo de mirada.

GazeProjector es una referencia conceptual directa para displays de tamaño y
orientación arbitrarios:

<https://www.perceptualui.org/publications/lander15_techrep/>

El proyecto `screen-eye-tracking` es un baseline útil para falsificar la
hipótesis actual porque declara la suposición de cámara arriba y centrada:

<https://github.com/PINTO0309/screen-eye-tracking>

## Capa learned recomendada

El modelo learned debe predecir dirección y confianza, no coordenadas de un
escritorio específico:

```text
I_t → (gaze_direction_t, head_pose_t, covariance_t)
```

La geometría posterior transforma esa salida a cada monitor. Un objetivo
multitarea puede incluir:

```text
L = L_angular
  + λ1 L_monitor
  + λ2 L_plane_intersection
  + λ3 L_temporal
  + λ4 L_uncertainty
```

La calibración personal puede ser una regresión ridge o polinómica de bajo
orden, un proceso gaussiano o una pequeña red residual. No se debe reemplazar
la geometría por un clasificador global mientras se pretenda generalizar a
monitores no vistos.

Separaciones obligatorias de evaluación:

- usuario visto frente a usuario no visto;
- monitor visto frente a monitor no visto;
- cámara fija frente a cámara desplazada;
- pantallas coplanares frente a pantallas anguladas;
- cabeza fija frente a movimiento natural;
- gafas, iluminación y oclusiones;
- calibración usada frente a objetivos held-out.

Métricas mínimas:

- error angular de mirada;
- error sobre el plano en píxeles y milímetros;
- identificación de monitor;
- error de distancia;
- error de dioptrías `|1/z_est - 1/z_true|`;
- latencia y drift;
- cobertura y tasa de `UNKNOWN`;
- calibración de incertidumbre.

## Componentes externos evaluados

| Componente | Uso permitido en esta integración | Límite |
|---|---|---|
| WebGazer | baseline 2D y calibración rápida | no es modelo 3D de foco ni refracción |
| MediaPipe Iris / Face Landmarker | landmarks faciales e iris | no equivale a medición clínica de mirada |
| pye3d | modelo geométrico 3D del ojo y corrección de refracción del tracker | requiere revisar hardware, cámara y licencia |
| ETH-XGaze | preentrenamiento/benchmark de dirección bajo poses extremas | revisar licencia CC BY-NC-SA y adaptación de dominio |
| L2CS-Net | baseline learned de yaw/pitch | no conoce la geometría de los monitores |
| GazeProjector | referencia de displays arbitrarios y tracking de superficie | es una referencia de investigación, no una garantía de integración |

Fuentes:

- <https://github.com/brownhci/WebGazer>
- <https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/iris.md>
- <https://github.com/pupil-labs/pye3d-detector>
- <https://docs.pupil-labs.com/core/developer/pye3d/>
- <https://github.com/xucong-zhang/ETH-XGaze>
- <https://github.com/Ahmednull/L2CS-Net>

## Relación con foco y refracción

El cálculo multi-monitor entrega una distancia física y, por tanto, una
demanda focal. No corrige automáticamente el ojo.

Una receta ocular debe mantenerse por ojo como esfera, cilindro, eje y, cuando
corresponda, distancia vértice. Un único ajuste esférico del display puede
compensar un error esférico dentro de los límites de la óptica, pero no puede
resolver astigmatismo: el astigmatismo tiene dos potencias principales y una
orientación. Para resolverlo se necesita una óptica cilíndrica/toric,
wavefront o una precompensación computacional limitada al contenido y al campo
de mirada.

La webcam no debe diagnosticar ni refinar una receta. Una receta declarada es
autoridad externa; una estimación learned de mirada no es autoridad clínica.

## Contrato MAT-SI para el adaptador

Esta integración no modifica `CERTIFIED REFINEMENT`; lo instancia en un dominio
concreto.

Ejemplo de contrato:

```text
Q = ¿qué monitor y qué punto físico intersecta la mirada?
P = el rayo calibrado intersecta el plano m dentro de ε
A = intrínsecas, extrínsecas, poses de monitor, tracker y reloj
K = todos los monitores activos y sus poses están cubiertos y vigentes
```

Si falta la pose de un monitor, hay más de un candidato válido, el tracker está
fuera de cobertura o la latencia supera el contrato, no se debe elegir una
pantalla por proximidad estadística. La salida debe quedar no certificada.

La representación tiene esta cadena:

```text
R0 cámara
R1 landmarks / cabeza
R2 mirada en ojo
R3 rayo en mundo
R4 hit de monitor
R5 distancia y dioptrías
R6 representación VIZZ
```

El residuo incluye oclusión, lágrima, aberraciones no modeladas, acomodación
dinámica, latencia, error de pose y drift. La representación 2D tiene un
`γ(R)` mucho más amplio que un rayo 3D con planos físicos conocidos.

La calibración de monitores es `Representation Investment`; la recalibración
por movimiento o drift es `Debt`; la reutilización del mismo mundo geométrico
para monitor, punto, distancia, foveación y demanda focal es `Credit`.

## Límites de esta integración

No demuestra:

- precisión humana;
- diagnóstico de miopía, hipermetropía o astigmatismo;
- corrección clínica;
- comodidad visual;
- eliminación del conflicto vergencia–acomodación;
- generalización de una red neuronal a usuarios no vistos.

Sí deja implementado y testeado el núcleo determinista de intersección
multi-monitor sobre geometría calibrada. El siguiente componente externo debe
proporcionar rayos 3D y su incertidumbre; no debe ocultar esa incertidumbre
dentro de coordenadas de pantalla.
