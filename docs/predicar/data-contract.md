# PREDICAR — contrato de datos

## Registro de observación

```json
{
  "ordinal": 0,
  "state": [0, 1, 0],
  "timestamp": null,
  "context": {},
  "source_ref": "source-or-synthetic-id"
}
```

El ejemplo es ilustrativo. La configuración inicial real tiene ancho 25 y suma
14; no se incluye una trayectoria en esta fase.

## Registro de forecast

```json
{
  "record_id": "fold-0001-model-0001-step-0001",
  "before": {"history_ref": "...", "cutoff": "..."},
  "intervention": {"model_id": "...", "config_digest": "..."},
  "after": {"state_ref": "..."},
  "scores": {},
  "provenance": {
    "protocol_id": "predicar-v0",
    "code_version": "...",
    "data_identity": "..."
  },
  "residue": {}
}
```

`before`, `intervention`, `after` y `provenance` siguen la frontera de
observabilidad mínima de MAT-SI. `scores` son derivados y no se escriben como
etiquetas semánticas del sistema.

## Estados

El estado canónico es una máscara binaria de ancho `N`. La serialización debe
ser estable y no depender de nombres humanos, orden accidental o formato de
fuente.

## Fuentes

Cada fuente debe indicar:

- `source_id`;
- URL o ruta;
- licencia/condición de uso;
- fecha de adquisición;
- hash cuando se congele;
- campos preservados, normalizados y perdidos;
- residuo no observable.

No se descargan fuentes privadas ni se incluyen secretos, credenciales o rutas
locales en resultados compartibles.
