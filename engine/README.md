# ECMWF IFS 0.25° Indonesia tile engine

Pre-renders colored XYZ WebP tiles for the Metamorph map. Colormaps live here, not in the app.

Licence: [CC-BY-4.0](https://www.ecmwf.int/en/forecasts/datasets/open-data) — attribution required.

## Env (conda-forge, recommended on Windows)

eccodes/cfgrib is painful as a pip-only install on Win11.

```
conda env create -f engine/environment.yml
conda activate ecmwf
```

If conda eccodes fails, use WSL2 with the same file. Docker is last resort.

## MapLibre hook without GRIB (no eccodes)

Needs numpy + pillow only:

```
python -m engine.smoke
```

Writes a synthetic 2-step tree so the map button can be tested before conda/eccodes is ready.

## Run once (live IFS)

From repo root, with `ecmwf` env active:

```
python -m engine.run --once --max-steps 2
```

Writes:

- `engine/output/latest.json` (`run_time` + per-step `valid_time`)
- `engine/output/runs/{run_id}/{var}/{step}/{z}/{x}/{y}.webp`

Same cycle a second time is a no-op.

Full latest cycle (all published steps):

```
python -m engine.run --once
```

Force rebuild:

```
python -m engine.run --once --force --run 20261017T00
```

## Poller (realtime)

```
python -m engine.poll
```

Every 10 minutes: discover latest IFS `oper` cycle, bake new steps, keep 2 runs.

## Serve

`npm run dev` mounts `engine/output` at `/ecmwf/`. MapLibre fetches `/ecmwf/latest.json` and `/ecmwf/runs/.../{z}/{x}/{y}.webp`.

## Variables

| id | GRIB | units |
|---|---|---|
| t2m | 2t | °C |
| d2m | 2d | °C |
| rh | derived from 2t+2d | % |
| tp | tp (accum from T+0) | mm |
| msl | msl | hPa |
| cape | mucape | J/kg |
| tcc | tcc | 0–1 |

Open Data has no surface `r`, no `cape`, no `lcc/mcc/hcc`.
