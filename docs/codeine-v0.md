# CODEINE v0

CODEINE v0 es un instrumento local y manual para una sesión real de Git. No es un
daemon, dashboard, agente ni integración de IDE.

## Uso

Desde la raíz del repositorio:

```text
$env:PYTHONPATH="src"
python -m codeine start --task "descripción humana opcional" --test-command "python -m unittest discover -s tests -v"
python -m codeine checkpoint
python -m codeine assess
python -m codeine finish
```

La sesión se guarda por defecto en `artifacts/codeine-v0/session.json`, que queda
fuera de Git mediante el `.gitignore` existente. Se puede cambiar con `--session`.

Cada `checkpoint` captura un registro Phase 4C:

```text
before + intervention opaca + after + provenance
```

El snapshot observa `HEAD`, estado/diffs del working tree y, si se configura, el
resultado del comando de tests. Los recursos son dimensiones independientes: bytes
de diff y tiempo medido del comando. No se captura una etiqueta de acción, éxito,
progreso, fallo o atasco.

## Única hipótesis

`persistence_without_observable_change` busca dos o más fronteras consecutivas con
digests de estado iguales y `elapsed_ms` medido. La regla es explícita:

- ninguna tentativa: `UNKNOWN`;
- cambio observable: `CONTINUE`;
- una repetición sin cambio: `CONTINUE`, como señal débil;
- dos repeticiones sin cambio con recursos: `SWITCH`;
- tres o más: `STOP`;
- sin medición de recursos para la repetición: `UNKNOWN`.

Una repetición cuyo estado sí cambia aparece en `evidence_against` y no se clasifica
como atasco. CODEINE no usa un score oculto ni afirma que la recomendación haya
causado una mejora.

## Sesión real

La sesión se ejecutó sobre una tarea genuina de este repositorio: añadir `--summary`
al comando `assess`, con una prueba TDD nueva. Hubo 11 checkpoints, incluyendo
intentos con la prueba fallando y correcciones posteriores; el test suite terminó
con exit code 0.

Durante la sesión apareció un residuo real: los digests de stderr cambiaban por rutas
temporales y por la duración total de `unittest`. Se mantuvieron los digests crudos y
se añadió una comparación estable que normaliza únicamente ese residuo. Después de
la corrección, `attempt-0009` y `attempt-0011` tuvieron el mismo state digest con
`elapsed_ms` medido. CODEINE emitió `CONTINUE` con `weak_repetition`, porque una
repetición no alcanza el umbral de dos; no emitió `SWITCH` ni `STOP`. No se afirma
que la recomendación haya causado la corrección.

El resumen auditable está en
`results/codeine-v0-real-session.json`; la sesión detallada local queda en
`artifacts/codeine-v0/real-session.json`.

## Gate

**B — CODEINE WORKS BUT DID NOT JUSTIFY INTERVENTION.**

El instrumento observó una tarea real, distinguió cambios de una repetición sin
cambio, conservó evidencia y terminó con `CONTINUE`. La evidencia disponible no
justificó ordenar `SWITCH` o `STOP`.
