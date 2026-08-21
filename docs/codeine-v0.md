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

La sesión de validación real y el gate se agregan después de ejecutar el flujo sobre
una tarea de este repositorio.
