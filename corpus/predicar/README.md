# PREDICAR corpus boundary

Este directorio contiene sólo manifiestos y contratos durante la preparación.
No contiene aún trayectorias, modelos ajustados ni resultados.

La primera campaña deberá registrar cuatro generadores sintéticos antes de abrir
cualquier adaptador externo:

1. `iid_exact_cardinality` — estados uniformes independientes;
2. `pairwise_gibbs` — interacciones conocidas;
3. `regime_switching` — cambio de régimen latente;
4. `noisy_observation` — estado válido observado mediante un canal ruidoso.

Todos deben conservar la especificación `N=25, K=14`, permitir semilla explícita
y separar generación, entrenamiento, predicción y puntuación.
