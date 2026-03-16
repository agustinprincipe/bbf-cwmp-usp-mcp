---
task: Refactor MCP server to use Broadband Forum GitHub repos as source of truth
date: 2026-03-16
complexity: grande
files_affected: 3-6 (rewrite of indexer.py, server.py; new modules for fetching/parsing)
---

## Analisis: MCP Server con Broadband Forum GitHub repos como fuente de verdad

### Proposito y Contexto

El servidor MCP actual funciona con documentos locales (PDFs y XSD/proto) que se indexan manualmente en ChromaDB con embeddings. La propuesta es reemplazar esa fuente de datos por los repositorios oficiales de Broadband Forum en GitHub, que contienen la informacion canonica y siempre actualizada sobre CWMP, USP y los data models.

### Estado Actual del Proyecto

**Arquitectura actual:**
- `indexer.py`: Pipeline de indexacion que convierte PDFs a markdown (via Docling), chunking, embeddings (sentence-transformers/all-MiniLM-L6-v2), y almacenamiento en ChromaDB
- `server.py`: Servidor MCP con 6 tools de busqueda semantica sobre colecciones ChromaDB
- `main.py`: Entry point
- Dependencias pesadas: `docling` (conversion PDF), `chromadb`, `sentence-transformers`

**Problemas del enfoque actual:**
1. Requiere obtener y colocar manualmente PDFs en directorios locales
2. `docling` es una dependencia pesada para conversion PDF y el resultado no es perfecto
3. Los data models XML (que son la fuente mas rica) no se procesan en absoluto
4. El contenido se desactualiza -- no hay mecanismo de sincronizacion
5. Semantic search sobre text chunks pierde estructura (jerarquia de objetos/parametros)

### Repositorios de Broadband Forum Analizados

#### 1. `BroadbandForum/cwmp-data-models` (111MB)
- **Contenido principal**: Data models CWMP en XML estructurado
- **Archivos clave**:
  - `tr-181-2-*-cwmp-full.xml` (~4MB cada uno): Data model Device:2 completo para CWMP (81 archivos full)
  - `tr-181-2-*-{wifi,ip,ethernet,...}.xml` (10KB-260KB): Componentes modulares por subsistema
  - `tr-098-*-full.xml`: Data model InternetGatewayDevice (legacy)
  - `tr-069-*-biblio.xml`: Bibliografias del protocolo TR-069
  - `cwmp-*.xsd`: Schemas XSD del protocolo CWMP
  - `cwmp-datamodel-*.xsd`: Schemas para definicion de data models
- **Formato XML**: Muy bien estructurado con `<parameter>`, `<object>`, `<component>`, `<description>`, tipos, rangos, enumeraciones, access rights
- **Versiones**: Desde v1.0 hasta v2.20 (ultima), con versionado por componente

#### 2. `BroadbandForum/usp-data-models` (57MB)
- **Contenido principal**: Data models USP en XML estructurado
- **Archivos clave**:
  - `tr-181-2-*-usp-full.xml`: Data model Device:2 completo para USP
  - `tr-181-2-*-{wifi,ip,...}.xml`: Componentes modulares USP-specific (ej: `wifi-usp.xml` vs `wifi-cwmp.xml`)
  - `tr-104-*-usp.xml`, `tr-135-*-usp.xml`, `tr-140-*-usp.xml`: Otros data models USP
- **Diferencia con CWMP**: Incluye archivos `-usp.xml` con parametros y objetos especificos de USP (ej: `softwaremodules-usp.xml`, `moca-usp.xml`)

#### 3. `BroadbandForum/usp` (41MB)
- **Contenido principal**: Especificacion completa USP TR-369
- **Archivos clave**:
  - `specification/*/index.md`: Especificacion en Markdown, organizada por seccion:
    - `architecture/index.md`, `messages/index.md`, `encoding/index.md`
    - `mtp/{stomp,mqtt,coap,websocket,unix-domain-socket}/index.md`
    - `security/index.md`, `discovery/index.md`, `e2e-message-exchange/index.md`
    - `extensions/{proxying,iot,software-module-management,...}/index.md`
  - `specification/usp-msg-1-{0..5}.proto`: Protobuf schemas USP Message (todas las versiones)
  - `specification/usp-record-1-{0..5}.proto`: Protobuf schemas USP Record
  - `api/swagger-usp-controller-v1.yaml`: API Swagger para USP Controller
  - `faq/`: FAQs del protocolo

#### Otros repos relevantes:
- `BroadbandForum/bbfreport`: Herramienta oficial para procesar data models BBF (podria usarse como referencia de parsing)
- `BroadbandForum/device-data-model`: Fuente upstream del data model Device:2 (contiene `specification/`)
- `BroadbandForum/cwmp-xml-tools`: [DEPRECATED] Herramientas legacy para XML

### Alternativas Evaluadas

| Enfoque | Pros | Contras |
|---------|------|---------|
| **A: Git clone + XML parsing directo + semantic search** | Datos siempre actualizados via git pull; Preserva estructura XML; Puede combinar busqueda estructurada (por path) con semantica (por descripcion); Elimina dependencia de PDFs y Docling | Requiere parser XML robusto para el schema BBF; Full XMLs son grandes (~4MB); Necesita estrategia de caching; Mas codigo a escribir |
| **B: GitHub API on-demand (sin clone local)** | Sin almacenamiento local; Siempre la version mas reciente; Setup minimal | Lento (API calls por cada query); Rate limiting de GitHub API; Sin busqueda offline; No apto para semantic search sobre contenido completo |
| **C: Hybrid -- Git clone + indexing inteligente de XML en ChromaDB** | Lo mejor de ambos mundos: estructura XML parseada + embeddings para busqueda semantica; Mantiene la capacidad actual de semantic search; XML parsing genera chunks de mayor calidad que PDF-to-markdown; Puede ofrecer busqueda por path exacto Y por semantica | Mas complejidad en el pipeline; Requiere re-indexar cuando hay updates; Sigue dependiendo de sentence-transformers y ChromaDB |
| **D: MCP Resources (no tools) -- exponer repos como resources navegables** | Aprovecha MCP resources para navegacion; El LLM decide que leer; No necesita embeddings ni indexing | No tiene busqueda; Solo funciona si el LLM sabe que path pedir; No escala para data models grandes; Limitado por context window del LLM |
| **E: XML parsing estructurado + busqueda por path (sin embeddings)** | Eliminaria chromadb y sentence-transformers; Busqueda determinista por path (Device.WiFi.SSID); Rapido, ligero, sin GPU/model loading; El XML ya tiene toda la info estructurada | Pierde busqueda semantica ("show me wifi parameters"); Solo funciona si el usuario sabe paths exactos; No sirve para specs narrativas (USP specification markdown) |

**Recomendacion:** **Enfoque C (Hybrid)** con la siguiente variante:

1. **Para Data Models (XML)**: Parsear los XMLs estructurados a una representacion intermedia, generar chunks por objeto/parametro con su path completo, descripcion, tipo, etc. Indexar en ChromaDB para busqueda semantica, PERO tambien ofrecer un tool de busqueda por path exacto (determinista, sin embeddings).

2. **Para Especificaciones USP (Markdown)**: Usar directamente los `.md` del repo `usp`. Son ya markdown limpio, no necesitan conversion PDF. Chunk e indexar en ChromaDB.

3. **Para Protobuf/XSD (Schemas)**: Chunk e indexar el texto raw como se hace ahora, pero desde los repos en vez de archivos locales.

4. **Sincronizacion**: `git clone --depth 1` inicial + `git pull` periodico. Un comando `sync` en el servidor.

### Modelo de Dominio (Enfoque C)

```
Fuentes (GitHub repos)
  |
  v
Git Clone/Pull local
  |
  +---> XML Parser (data models)
  |       |
  |       +---> Structured index (path -> {description, type, access, version, ...})
  |       +---> Semantic chunks (object/parameter descriptions) -> ChromaDB
  |
  +---> Markdown files (USP spec) -> Chunks -> ChromaDB
  |
  +---> Proto/XSD files -> Chunks -> ChromaDB
  |
  v
MCP Server
  +---> Tool: search_datamodel (semantic + path-based)
  +---> Tool: get_parameter (exact path lookup, e.g., "Device.WiFi.SSID.1.SSID")
  +---> Tool: search_cwmp_spec (semantic over CWMP spec/protocol)
  +---> Tool: search_usp_spec (semantic over USP spec markdown)
  +---> Tool: search_usp_protocol (semantic over protobuf definitions)
  +---> Tool: list_objects (list children of a data model path)
  +---> Tool: sync_repos (update local clones)
```

### File Map

| Archivo | Accion | Motivo |
|---------|--------|--------|
| `indexer.py` | Reescribir | Nuevo pipeline: git clone + XML parsing + markdown chunking |
| `server.py` | Reescribir | Nuevos tools (search_datamodel, get_parameter, list_objects, etc.) |
| `main.py` | Modificar menor | Ajustar si cambia el entry point |
| `pyproject.toml` | Modificar | Cambiar dependencias: quitar docling, agregar lxml/gitpython |
| `xml_parser.py` | Crear | Modulo para parsing de data models XML BBF |
| `repo_manager.py` | Crear | Modulo para clone/pull de repos GitHub |
| `data/` | Reestructurar | Reemplazar directorios manuales por clones de repos |

### Dependencias Nuevas vs Eliminadas

**Eliminar:**
- `docling` (pesada, solo para PDF->markdown, ya no se necesita)

**Agregar:**
- `lxml` o usar `xml.etree.ElementTree` (stdlib) para parsing XML
- `gitpython` o simplemente shell `git` commands para clone/pull

**Mantener:**
- `chromadb` (vector storage)
- `sentence-transformers` (embeddings para busqueda semantica)
- `mcp` (SDK del servidor)

### Riesgos

1. **Tamano de los repos**: `cwmp-data-models` es 111MB. El clone inicial tardara. Mitigacion: `--depth 1` y clone solo los archivos necesarios (sparse checkout de `-full.xml` y `-*.xml` del ultimo version).

2. **Complejidad del XML parsing**: El schema XML de BBF es rico y tiene imports cruzados entre archivos. Mitigacion: Usar los archivos `-full.xml` que ya resuelven imports y contienen todo el data model expandido. Para los modulares, parsear solo los de la ultima version.

3. **Tamano del full XML**: 4MB por archivo full es mucho para parsear en memoria. Mitigacion: `lxml` con iterparse (streaming) o parsear solo la ultima version.

4. **Diferencias CWMP vs USP data models**: Hay archivos `-cwmp.xml` y `-usp.xml` separados. Mitigacion: Indexar ambos con metadata que indique el protocolo. El tool `search_datamodel` acepta un filtro de protocolo.

5. **Versionado**: Hay 20+ versiones de TR-181. Mitigacion: Por defecto indexar solo la ultima version. Opcionalmente permitir seleccionar version.

- **Complejidad general:** Alta (rewrite completo del pipeline y server)

### Plan de Pasos (descomposicion sugerida)

Dado que es un proyecto **Grande**, se recomienda descomponerlo en sub-tareas:

#### Sub-tarea 1: Repo Manager + Git Sync
- Crear `repo_manager.py` con clone/pull de los 3 repos BBF
- Comando CLI para sync
- Tests

#### Sub-tarea 2: XML Data Model Parser
- Crear `xml_parser.py` que parsee los XMLs de BBF
- Extraer objetos, parametros, descripciones, tipos, paths
- Generar chunks para indexacion
- Tests con XML de ejemplo

#### Sub-tarea 3: Nuevo Indexer
- Reescribir `indexer.py` usando repo_manager y xml_parser
- Indexar data models (CWMP + USP), USP spec markdown, proto/XSD
- Separar colecciones ChromaDB por tipo

#### Sub-tarea 4: Nuevo Server con Tools Mejorados
- Reescribir `server.py` con nuevos tools:
  - `search_datamodel` (semantic)
  - `get_parameter` (exact path)
  - `list_objects` (tree navigation)
  - `search_usp_spec` (USP specification)
  - `search_cwmp_protocol` (CWMP XSD/schemas)
  - `search_usp_protocol` (protobuf)
  - `sync_repos` (trigger re-sync)
- Actualizar `pyproject.toml`

#### Sub-tarea 5: Cleanup y Documentacion
- Quitar dependencia `docling`
- Actualizar README
- Reestructurar `data/`

### Orden Sugerido
1 -> 2 -> 3 -> 4 -> 5 (cada paso depende del anterior)

Cada sub-tarea puede ejecutarse con su propio ciclo `/analyze` -> `/implement`.
