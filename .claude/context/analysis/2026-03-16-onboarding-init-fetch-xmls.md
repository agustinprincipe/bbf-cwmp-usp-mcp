---
task: Onboarding/Init -- Fetch only necessary XML documents and parse them
date: 2026-03-16
complexity: normal
files_affected: 4
replaces: Sub-task 1 (Repo Manager + Git Sync) from 2026-03-16-bbf-github-source-of-truth.md
---

## Analisis: Onboarding/Init -- Fetch selectivo de XMLs desde GitHub

### Alcance

Reemplazar la sub-tarea 1 del plan original (que proponia clonar 3 repos completos: ~209MB) con un enfoque de "onboarding/init" que:

1. Usa la GitHub API (trees + raw content) para descubrir y descargar **solo** los archivos necesarios
2. Parsea los XMLs de data models inmediatamente durante el init
3. Almacena los archivos descargados en `data/` para cache local

Esto fusiona lo que era sub-tarea 1 (repo manager) con la descarga selectiva, eliminando la necesidad de `git clone` de repos enteros.

### Que se descarga (inventario exacto verificado contra GitHub API)

#### Desde `BroadbandForum/cwmp-data-models`:
- `tr-181-2-20-1-cwmp-full.xml` (~4.9MB) -- Data model Device:2 completo para CWMP (ultima version)
- `tr-098-1-8-0-full.xml` -- Data model InternetGatewayDevice legacy (ultima version)
- `cwmp-1-4.xsd` -- CWMP protocol schema (ultima version)
- Opcionalmente: versiones anteriores del full.xml si se quiere soporte multi-version

#### Desde `BroadbandForum/usp-data-models`:
- `tr-181-2-20-1-usp-full.xml` -- Data model Device:2 completo para USP (ultima version)

#### Desde `BroadbandForum/usp` (specification/):
- 20 archivos markdown (specification/**/*.md) -- Especificacion USP completa
- `usp-msg-1-5.proto` -- USP Message protobuf (ultima version)
- `usp-record-1-5.proto` -- USP Record protobuf (ultima version)

**Total estimado: ~12-15MB de datos utiles vs ~209MB de clones completos**

### Estrategia de descubrimiento de archivos

En lugar de hardcodear nombres de archivo (que cambian con cada release), el init usara:

1. **GitHub Trees API** (`GET /repos/{owner}/{repo}/git/trees/master?recursive=1`) -- una sola request por repo, devuelve todos los paths
2. Filtrar por patron: buscar el archivo `-full.xml` con el mayor numero de version
3. Descargar via raw.githubusercontent.com (sin rate limiting de API)

Esto hace que el sistema se auto-actualice: si BBF publica `tr-181-2-21-0-cwmp-full.xml`, el init lo encontrara automaticamente.

### File Map

| Archivo | Accion | Motivo |
|---------|--------|--------|
| `bbf_fetcher.py` | Crear | Modulo para descubrir y descargar archivos desde GitHub BBF repos |
| `pyproject.toml` | Modificar | Agregar `httpx` como dependencia (async HTTP client) |
| `main.py` | Modificar | Agregar comando CLI `init`/`onboarding` que ejecuta el fetch |
| `data/` | Modificar | Destino de los archivos descargados, nueva estructura |

### Dependencias Identificadas

**Nuevas dependencias:**
- `httpx` -- HTTP client async, ligero, soporta streaming para archivos grandes. Alternativa: `aiohttp` o `urllib3`, pero httpx es mas moderno y tiene mejor API.

**No se necesitan:**
- `gitpython` -- ya no se clonan repos
- Ningun parser XML todavia -- esta sub-tarea solo descarga, la sub-tarea 2 parseara

**Se mantienen intactos:**
- `server.py` -- no se toca en esta sub-tarea
- `indexer.py` -- no se toca en esta sub-tarea
- `chromadb`, `sentence-transformers` -- se mantienen

### Diseno del modulo `bbf_fetcher.py`

```
class BBFDataFetcher:
    """Discovers and downloads BBF data model files from GitHub."""

    REPOS = {
        "cwmp-data-models": {
            "owner": "BroadbandForum",
            "patterns": {
                "data_models": [r"tr-181-2-\d+-\d+-cwmp-full\.xml", r"tr-098-\d+-\d+-\d+-full\.xml"],
                "protocols": [r"cwmp-\d+-\d+\.xsd"],
            },
            "latest_only": True,  # solo la ultima version de cada patron
        },
        "usp-data-models": {
            "owner": "BroadbandForum",
            "patterns": {
                "data_models": [r"tr-181-2-\d+-\d+-usp-full\.xml"],
            },
            "latest_only": True,
        },
        "usp": {
            "owner": "BroadbandForum",
            "patterns": {
                "spec_markdown": [r"specification/.*\.md"],
                "protocols": [r"specification/usp-msg-\d+-\d+\.proto", r"specification/usp-record-\d+-\d+\.proto"],
            },
            "latest_only": True,  # para protos; todos los md
        },
    }

    async def discover_files(self, repo_name: str) -> dict[str, list[str]]
    async def download_file(self, repo: str, path: str, dest: Path) -> Path
    async def run_init(self, data_dir: Path) -> InitResult
```

**Flujo del init:**
1. Para cada repo, llamar a Trees API (1 request por repo = 3 requests total)
2. Filtrar paths con los patrones regex configurados
3. Para patrones con `latest_only`, seleccionar la version mas alta
4. Descargar archivos via raw.githubusercontent.com (sin contar contra API rate limit)
5. Guardar en `data/{categoria}/` con estructura plana
6. Escribir `data/manifest.json` con metadata: version descargada, fecha, SHA del tree

**Nueva estructura de `data/`:**
```
data/
  manifest.json          -- metadata de lo descargado (version, fecha, tree SHA)
  cwmp/
    tr-181-2-20-1-cwmp-full.xml
    tr-098-1-8-0-full.xml
    cwmp-1-4.xsd
  usp/
    tr-181-2-20-1-usp-full.xml
  usp-spec/
    architecture/index.md
    messages/index.md
    mtp/index.md
    mtp/mqtt/index.md
    ...
    usp-msg-1-5.proto
    usp-record-1-5.proto
```

### Alternativas Evaluadas

| Enfoque | Pros | Contras |
|---------|------|---------|
| **A: GitHub Trees API + raw download (RECOMENDADO)** | Una sola API call por repo para descubrir archivos; raw downloads no tienen rate limit; auto-descubre nuevas versiones; ~12-15MB vs 209MB; no necesita git instalado | Necesita logica de parseo de version para seleccionar "latest"; no tiene historial de cambios |
| **B: Git sparse checkout** | Usa git nativo; mas familiar; puede hacer pull incremental | Requiere git instalado; sigue descargando metadata del repo completo (~50MB+ por repo); mas complejo de configurar sparse-checkout patterns; mas lento en init |
| **C: GitHub API contents endpoint** | API simple por archivo | Rate limited (60/hr sin token, 5000/hr con token); no puede listar recursivamente; necesita muchas requests para descubrir archivos |
| **D: Hardcodear URLs de archivos conocidos** | Cero descubrimiento, maxima simplicidad | Se rompe cuando BBF publica nueva version; requiere actualizacion manual del codigo |

**Recomendacion:** Enfoque A (Trees API + raw download) porque combina descubrimiento automatico de versiones con descarga eficiente y minimo uso de API.

### Riesgos

1. **GitHub API rate limiting (sin token):** 60 requests/hora. El init usa solo 3 requests (1 tree per repo) + downloads via raw.githubusercontent.com (sin limit). Mitigacion: suficiente con 3 requests. Opcionalmente aceptar un `GITHUB_TOKEN` para rate limit mas alto.

2. **Cambio de estructura en repos BBF:** Si BBF cambia la convencion de naming. Mitigacion: los regex patterns son configurables en `REPOS`; el manifest.json registra que se descargo para diagnostico.

3. **Archivos grandes en memoria:** El full XML es ~5MB. Mitigacion: httpx soporta streaming download, escribir directamente a disco.

4. **Falta de conectividad:** Si no hay internet al momento del init. Mitigacion: el manifest.json permite detectar si ya se hizo init previo; el servidor puede arrancar con datos cacheados.

- **Complejidad:** Baja-media

### Plan de Pasos

1. **Agregar `httpx` a `pyproject.toml`** como dependencia
2. **Crear `bbf_fetcher.py`** con:
   - Clase `BBFDataFetcher` con la config de repos/patterns
   - Metodo `discover_files()` que usa Trees API + regex filtering + version sorting
   - Metodo `download_file()` que descarga via raw.githubusercontent.com con streaming
   - Metodo `run_init()` que orquesta discovery + download + genera manifest.json
   - Dataclass `InitResult` con resumen de lo descargado
3. **Modificar `main.py`** para agregar subcomando `init` (o `onboarding`) que ejecuta `BBFDataFetcher.run_init()`
4. **Agregar `data/` a `.gitignore`** (los datos descargados no se commitean)
5. **Tests:** test unitario con mock de GitHub API response para verify pattern matching y version sorting

### Impacto en sub-tareas posteriores

Esta sub-tarea reemplaza la sub-tarea 1 original y simplifica la sub-tarea 2:
- **Sub-tarea 2 (XML Parser):** Ahora recibe XMLs ya descargados en `data/cwmp/` y `data/usp/`, solo necesita parsear
- **Sub-tarea 3 (Indexer):** Sin cambios, consume output del parser
- **Sub-tarea 4 (Server):** Puede agregar un tool `sync`/`update` que re-ejecuta el init para actualizar datos