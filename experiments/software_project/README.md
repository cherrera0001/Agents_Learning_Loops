# Task Ledger

Small real Python WSGI/SQLite application. No external runtime dependencies.
Components: API, identity lookup, authorization middleware, environment config,
SQLite storage, task business rules, report service, background worker.

From this directory: `python -m app.api` serves on localhost:8000;
`python -m unittest discover -s tests -v` checks business behavior.
`Authorization: demo-token` is a deliberately local experimental identity.

El controlador que copia la aplicación es el harness de experimento ([glosario](../../docs/entorno/glosario.md));
la aplicación sana no es el agente. Esta aplicación tampoco asigna modelos de Claude: el modelo de
construcción de cada issue está en [`docs/estimation.md`](../../docs/estimation.md).

The checked-in application is healthy. The experiment controller copies it to a
fresh temporary workspace and injects exactly one defect. It copies only the
current task's acceptance test, never private metadata or future tasks. Each
attempt begins from the identical defective snapshot; successful patches from
training do not carry into evaluation. Only evidence-grounded memory can carry.
