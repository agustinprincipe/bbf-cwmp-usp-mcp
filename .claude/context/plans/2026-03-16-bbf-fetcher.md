---
task: BBF Data Fetcher — Onboarding/Init selective fetch from GitHub
date: 2026-03-16
mode: directo
steps: 5
analysis_file: .claude/context/analysis/2026-03-16-onboarding-init-fetch-xmls.md
---

## Plan de Implementacion

### Cambios por archivo

**`pyproject.toml`** — `uv add httpx`

**`bbf_fetcher.py`** (NUEVO)
- Clase `BBFDataFetcher` con REPOS config, discover_files(), download_file(), run_init()
- Dataclass `InitResult`
- Helper `_parse_version()` para comparar versiones en filenames

**`main.py`** — argparse con subcomandos `serve` (default) e `init`

**`.gitignore`** — agregar paths de datos descargados

### Orden
1. pyproject.toml (uv add httpx)
2. bbf_fetcher.py con TDD
3. main.py CLI
4. .gitignore
5. Verificacion final