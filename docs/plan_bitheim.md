# Plan Maestro de Implementación de Bitheim hasta `v1.0.0`

## Plataforma distribuida para experimentación, minería y análisis sobre Bitcoin

**Estado:** Source of Truth
**Versión del documento:** 1.1
**Nombre del proyecto:** Bitheim
**Horizonte:** Desde la inicialización del repositorio hasta `v1.0.0`
**Naturaleza:** Proyecto open source
**Usuarios iniciales confirmados:** 2
**Escala de diseño:** De 2 a decenas de nodos sin rediseño estructural
**Lenguaje principal:** Python
**Gestión de proyecto Python:** `uv`
**Red privada:** Previamente establecida, por ejemplo mediante Headscale/Tailscale
**Red blockchain inicial:** Bitcoin Core `regtest`
**Red blockchain objetivo:** `labnet-v1`
**Plataformas objetivo para `v1.0.0`:**

* Linux `amd64`
* Linux `arm64`
* macOS Apple Silicon mediante Docker Desktop
* Windows mediante WSL2 y Docker Desktop

---

# 1. Propósito del documento

Este documento define la arquitectura, alcance, convenciones, estándares de ingeniería, controles de seguridad, módulos, fases de desarrollo, proceso de releases y criterios de aceptación que regirán Bitheim hasta alcanzar la versión `1.0.0`.

Su contenido constituye la referencia normativa principal del proyecto.

Toda implementación deberá respetar este documento salvo que:

1. se identifique un error técnico;
2. aparezca una restricción no contemplada;
3. exista evidencia suficiente para justificar una alternativa;
4. el cambio sea documentado mediante un Architecture Decision Record, ADR;
5. ambos mantenedores aprueben la modificación.

No deberán introducirse cambios arquitectónicos significativos únicamente por conveniencia inmediata, preferencia personal o incorporación impulsiva de una nueva tecnología.

---

# 2. Identidad del proyecto

## 2.1 Nombre

El nombre oficial del proyecto será:

> **Bitheim**

El nombre se utilizará de forma consistente en:

* repositorio;
* paquete Python;
* comando CLI;
* imágenes Docker;
* documentación;
* configuración;
* logs;
* releases;
* artefactos;
* nombres de servicio.

## 2.2 Convenciones de nombres

| Elemento                           | Nombre                       |
| ---------------------------------- | ---------------------------- |
| Proyecto                           | `Bitheim`                    |
| Repositorio principal              | `bitheim`                    |
| Paquete Python                     | `bitheim`                    |
| Comando CLI                        | `bitheim`                    |
| Imagen principal                   | `ghcr.io/<org>/bitheim`      |
| Fork de Bitcoin Core               | `bitheim-bitcoin-core`       |
| Imagen del nodo Labnet             | `ghcr.io/<org>/bitheim-core` |
| Red experimental                   | `labnet-v1`                  |
| Archivo principal de configuración | `bitheim.toml`               |
| Directorio local predeterminado    | `.bitheim/`                  |

## 2.3 Ejemplos de uso

```bash
uv run bitheim doctor
uv run bitheim start
uv run bitheim status
uv run bitheim tui
```

En una distribución Docker:

```bash
docker compose up -d
docker compose run --rm bitheim tui
```

---

# 3. Visión del producto

Bitheim será una plataforma ligera, reproducible y extensible para desplegar, utilizar, observar y analizar redes privadas basadas en Bitcoin Core.

El sistema permitirá:

* ejecutar un nodo blockchain privado;
* crear y administrar wallets;
* realizar transacciones Bitcoin válidas;
* observar bloques, mempool, UTXOs y peers;
* participar en minería competitiva;
* observar prueba de trabajo real;
* utilizar una dificultad distribuida;
* generar actividad sintética opcional;
* ejecutar experimentos reproducibles;
* capturar eventos y métricas;
* consultar y exportar datos;
* usar una TUI sin depender obligatoriamente de comandos;
* acceder a una CLI y una consola RPC para uso avanzado;
* desplegar la misma implementación en arquitecturas distintas.

Las monedas utilizadas no tendrán valor económico, pero las transacciones deberán ser auténticas desde el punto de vista del protocolo.

Las transacciones:

* consumirán UTXOs reales;
* estarán firmadas criptográficamente;
* serán validadas por Bitcoin Core;
* entrarán al mempool;
* se propagarán entre peers;
* serán incluidas en bloques;
* recibirán confirmaciones;
* modificarán balances;
* podrán regresar al mempool después de una reorganización;
* podrán quedar invalidadas por una cadena competidora.

Bitheim no será una simulación visual desconectada de Bitcoin.

Será una capa de operación, experimentación y análisis construida alrededor de nodos reales.

---

# 4. Antecedentes

Bitheim surge del proyecto **Bitcoin Local Lab**, en el cual se desarrolló progresivamente:

1. un nodo autónomo en `regtest`;
2. una red P2P local de dos nodos;
3. automatización mediante JSON-RPC;
4. propagación de transacciones;
5. simulación de forks;
6. reorganizaciones de cadena;
7. una malla distribuida entre equipos heterogéneos;
8. instrumentación;
9. documentación de reproducibilidad;
10. resolución de problemas reales de red, memoria y contenedores.

El laboratorio demostró la viabilidad técnica del concepto.

Bitheim transformará ese laboratorio en un producto mantenible, desplegable y utilizable por personas que no necesariamente desean operar Bitcoin Core exclusivamente desde una terminal.

---

# 5. Objetivos

## 5.1 Objetivos funcionales

Bitheim deberá permitir:

* instalar y desplegar un nodo con configuración mínima;
* unirse a una red privada existente;
* crear y administrar wallets;
* enviar y recibir monedas de laboratorio;
* consultar balances y UTXOs;
* observar la red P2P;
* inspeccionar bloques y transacciones;
* participar en minería;
* generar actividad sintética;
* ejecutar experimentos;
* almacenar observaciones;
* analizar resultados;
* exportar datasets.

## 5.2 Objetivos educativos

El producto deberá permitir observar:

* ciclo de vida de una transacción;
* propagación P2P;
* mempool;
* confirmaciones;
* coinbase;
* maduración;
* UTXOs;
* minería;
* nonce;
* hash SHA-256d;
* target;
* dificultad;
* chainwork;
* forks;
* reorganizaciones;
* ajuste de dificultad;
* impacto de latencia;
* comportamiento de una red pequeña.

## 5.3 Objetivos de ingeniería

El proyecto deberá:

* ser reproducible;
* funcionar en `amd64` y `arm64`;
* ser mantenible por dos personas;
* seguir buenas prácticas actuales de Python;
* utilizar `uv`;
* contar con typing estricto;
* poseer límites arquitectónicos claros;
* aplicar seguridad por defecto;
* contar con pruebas automatizadas;
* producir releases verificables;
* soportar actualización y rollback;
* ser seguro para publicación open source.

---

# 6. Principios rectores

## 6.1 Bitcoin Core conserva la autoridad de validación

Bitheim nunca deberá sustituir la validación de:

* bloques;
* transacciones;
* scripts;
* UTXOs;
* prueba de trabajo;
* dificultad;
* trabajo acumulado;
* reorganizaciones.

Bitheim puede:

* crear;
* solicitar;
* automatizar;
* observar;
* presentar;
* registrar;
* analizar.

Bitcoin Core será la autoridad final sobre la validez de los datos.

---

## 6.2 La complejidad será opcional

Un usuario deberá poder:

1. instalar Bitheim;
2. importar una configuración;
3. iniciar el nodo;
4. crear una wallet;
5. realizar una transacción;
6. observar el resultado;

sin escribir comandos obligatoriamente.

El mismo usuario podrá posteriormente acceder a:

* CLI;
* consola RPC;
* configuración;
* logs;
* SQL;
* datos sin procesar;
* detalles de protocolo.

---

## 6.3 Automatización transparente

Toda acción importante iniciada desde la TUI deberá permitir consultar:

* caso de uso ejecutado;
* RPC equivalente;
* parámetros;
* respuesta;
* eventos;
* modificaciones persistidas.

La TUI no deberá convertirse en una caja negra.

---

## 6.4 Seguridad por defecto

Las configuraciones predeterminadas deberán adoptar:

* mínimo privilegio;
* denegación por defecto;
* RPC local;
* separación de secretos;
* imágenes inmutables;
* versiones fijadas;
* permisos restrictivos;
* ausencia de telemetría remota;
* exposición mínima de puertos;
* sanitización de logs.

---

## 6.5 Diseño para dos usuarios, sin impedir crecimiento

Los únicos usuarios iniciales confirmados son los dos mantenedores.

Por tanto:

* no se optimizará prematuramente para cientos de participantes;
* no se implementará infraestructura innecesaria;
* no se introducirán microservicios sin justificación;
* no se asumirá una organización grande.

Sin embargo, el diseño evitará decisiones que impidan utilizar varios nodos o incorporar más participantes.

---

## 6.6 Modularidad sin microservicios prematuros

Bitheim será inicialmente un:

> **Monolito modular con arquitectura hexagonal.**

No se dividirá en microservicios mientras:

* existan dos mantenedores;
* se distribuya como una unidad;
* los componentes compartan el mismo ciclo de release;
* no exista una necesidad real de escalarlos de forma independiente.

---

## 6.7 Reproducibilidad

Con la misma:

* versión;
* configuración;
* manifiesto;
* escenario;
* semilla;
* estado inicial;
* versión de Bitcoin Core;

los experimentos deberán producir resultados funcionalmente equivalentes.

---

## 6.8 Open source seguro

Ningún artefacto público deberá contener:

* direcciones reales de la malla;
* dominios privados;
* nombres internos;
* claves de Headscale;
* claves privadas;
* seeds;
* cookies RPC;
* tokens;
* configuraciones reales de OCI;
* dumps locales;
* rutas personales;
* nombres de participantes;
* direcciones de wallets utilizadas en entornos privados.

---

# 7. Alcance hasta `v1.0.0`

## 7.1 Incluido

Bitheim incluirá antes de `v1.0.0`:

* proyecto Python administrado con `uv`;
* distribución reproducible mediante Docker Compose;
* imágenes multi-arquitectura;
* gestión del ciclo de vida de Bitcoin Core;
* configuración de nodos;
* wallets;
* transacciones humanas;
* TUI;
* CLI;
* consola RPC;
* visualización de peers;
* visualización de bloques;
* visualización de mempool;
* minería manual;
* minería competitiva;
* `labnet-v1`;
* dificultad distribuida;
* agentes sintéticos opcionales;
* escenarios reproducibles;
* recolección de eventos;
* almacenamiento analítico;
* exportación CSV;
* exportación Parquet;
* experimentos;
* diagnóstico;
* actualización;
* rollback;
* documentación de usuario;
* documentación de desarrollo;
* pipeline seguro de releases.

## 7.2 Fuera de alcance

No se implementará antes de `v1.0.0`:

* instalación automática de Headscale;
* administración de usuarios de Headscale;
* creación automática de redes privadas;
* mainnet;
* fondos reales;
* Lightning Network;
* panel web;
* aplicación móvil nativa;
* Kubernetes;
* Databricks;
* conector nativo para Power BI;
* autenticación multiusuario;
* alta disponibilidad;
* telemetría centralizada;
* marketplace de plugins;
* ejecución remota de RPC;
* exposición pública de nodos.

---

# 8. Arquitectura principal

## 8.1 Estilo arquitectónico

Bitheim utilizará:

> **Monolito modular con arquitectura hexagonal y separación por dominios.**

El diseño combinará:

* Ports and Adapters;
* Domain-Driven Design ligero;
* Application Services;
* separación pragmática entre commands y queries;
* inversión de dependencias;
* eventos internos tipados;
* límites explícitos entre módulos.

No se implementará DDD táctico completo cuando no aporte valor directo.

## 8.2 Razones

Un monolito modular es apropiado porque:

* solo existen dos mantenedores;
* la aplicación se distribuye como una unidad;
* las operaciones son principalmente locales;
* simplifica debugging;
* simplifica releases;
* reduce problemas distribuidos internos;
* permite refactorizar sin coordinar servicios;
* mantiene la posibilidad de extraer módulos en el futuro.

## 8.3 Arquitectura hexagonal

El dominio no deberá depender directamente de:

* Bitcoin Core;
* Docker;
* Textual;
* DuckDB;
* ZMQ;
* `urllib`;
* sistema operativo;
* framework de configuración;
* gestor de procesos.

Las dependencias externas se implementarán como adapters.

---

# 9. Arquitectura de ejecución

```text
┌────────────────────────── Host ────────────────────────────┐
│                                                           │
│ Headscale / Tailscale                                     │
│ └── Fuera del alcance de Bitheim                          │
│                                                           │
│ Docker Compose                                            │
│ ├── bitheim-core                                          │
│ ├── bitheim-daemon                                        │
│ ├── bitheim-tui                                           │
│ ├── bitheim-miner             opcional                    │
│ ├── bitheim-simulator         opcional                    │
│ └── bitheim-analytics         opcional                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

Todos los procesos de Bitheim utilizarán el mismo paquete Python y distintos entrypoints.

```bash
bitheim daemon
bitheim tui
bitheim miner
bitheim simulate
bitheim analytics
bitheim doctor
```

Esto evitará mantener aplicaciones separadas y divergentes.

---

# 10. Repositorios

## 10.1 Repositorio principal: `bitheim`

Contendrá:

* aplicación Python;
* TUI;
* CLI;
* daemon;
* minero;
* simulador;
* analítica;
* configuraciones;
* Docker Compose;
* documentación;
* pruebas;
* pipelines;
* escenarios.

## 10.2 Fork: `bitheim-bitcoin-core`

Contendrá un fork mínimo de Bitcoin Core.

Solo deberá modificar lo necesario para:

* registrar `labnet`;
* definir génesis;
* definir magic bytes;
* definir puertos;
* configurar `powLimit`;
* habilitar reajuste;
* definir tiempos;
* identificar la red;
* validar dificultad.

No deberá modificar innecesariamente:

* wallets;
* mempool;
* scripts;
* RPC;
* serialización;
* P2P;
* chain selection;
* almacenamiento.

---

# 11. Estructura del repositorio

```text
bitheim/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── workflows/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── development/
│   ├── operations/
│   ├── releases/
│   └── user-guide/
├── src/
│   └── bitheim/
│       ├── bootstrap/
│       ├── shared/
│       ├── node/
│       ├── wallet/
│       ├── network/
│       ├── mining/
│       ├── activity/
│       ├── experiments/
│       ├── analytics/
│       ├── runtime/
│       ├── interfaces/
│       │   ├── cli/
│       │   └── tui/
│       └── infrastructure/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   ├── security/
│   ├── performance/
│   └── fixtures/
├── scenarios/
├── schemas/
├── docker/
├── scripts/
├── examples/
│   ├── configs/
│   └── network-manifests/
├── compose.yaml
├── compose.dev.yaml
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── GOVERNANCE.md
├── CHANGELOG.md
├── LICENSE
└── .gitignore
```

Se utilizará `src-layout`.

---

# 12. Gestión del proyecto Python con `uv`

## 12.1 Herramienta oficial

`uv` será la herramienta oficial para:

* crear el proyecto;
* administrar el entorno virtual;
* instalar Python cuando sea necesario;
* resolver dependencias;
* bloquear versiones;
* ejecutar comandos;
* instalar grupos de desarrollo;
* construir paquetes;
* reproducir entornos.

No se utilizará `pip install` directamente durante el flujo normal de desarrollo.

No se instalarán dependencias del proyecto en el entorno global.

## 12.2 Inicialización

El proyecto se inicializará mediante:

```bash
uv init --package bitheim
```

Se utilizará estructura de paquete en `src/`.

## 12.3 Entorno virtual

El entorno local será administrado por `uv`.

```bash
uv sync
```

Esto creará o actualizará `.venv/`.

`.venv/` estará ignorado por Git.

## 12.4 Ejecución

Todos los comandos Python del proyecto se ejecutarán mediante:

```bash
uv run <command>
```

Ejemplos:

```bash
uv run bitheim doctor
uv run bitheim start
uv run bitheim tui
uv run pytest
uv run ruff check .
uv run mypy src
```

## 12.5 Dependencias

Agregar dependencia de producción:

```bash
uv add textual
```

Agregar dependencia de desarrollo:

```bash
uv add --dev pytest
```

Eliminar dependencia:

```bash
uv remove <package>
```

No se editarán manualmente las dependencias del lockfile.

## 12.6 Lockfile

`uv.lock` deberá:

* versionarse;
* actualizarse mediante `uv`;
* revisarse en pull requests;
* utilizarse en CI;
* utilizarse en Docker;
* ser la referencia de resolución reproducible.

## 12.7 Sincronización bloqueada

En CI y builds se utilizará:

```bash
uv sync --locked
```

Esto impedirá que un entorno cambie silenciosamente el lockfile.

## 12.8 Instalación congelada

En contextos donde se requiera reproducibilidad estricta:

```bash
uv sync --frozen
```

## 12.9 Grupos de dependencias

Como mínimo existirán:

* dependencias de producción;
* grupo `dev`;
* grupo `test`;
* grupo `docs`;
* grupo `security`.

La división exacta se definirá en `pyproject.toml`.

## 12.10 Versión de Python

`.python-version` declarará la versión utilizada por el proyecto.

Ejemplo:

```text
3.13
```

El flujo inicial podrá ser:

```bash
uv python install
uv sync
```

## 12.11 Bootstrap del desarrollador

Un nuevo contribuidor deberá poder ejecutar:

```bash
git clone <repository>
cd bitheim
uv python install
uv sync --all-groups
uv run bitheim doctor
```

## 12.12 Comandos de desarrollo

Podrán existir wrappers mediante `Makefile` o scripts, pero internamente utilizarán `uv`.

Ejemplo:

```makefile
check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src
	uv run pytest
```

`uv` seguirá siendo la fuente de verdad del entorno.

## 12.13 Docker

Los Dockerfiles utilizarán `uv` para instalar las dependencias.

Principios:

* copiar primero `pyproject.toml` y `uv.lock`;
* usar `uv sync --locked`;
* aprovechar cache de capas;
* separar build y runtime;
* no incluir dependencias de desarrollo en producción;
* usar una imagen final mínima;
* ejecutar como usuario no root.

Ejemplo conceptual:

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY src/ ./src/
```

## 12.14 CI

Los workflows utilizarán la misma secuencia que los desarrolladores:

```bash
uv sync --locked --all-groups
uv run ruff check .
uv run mypy src
uv run pytest
```

No se mantendrá un `requirements.txt` manual paralelo.

Solo se generará uno cuando alguna herramienta externa lo requiera expresamente.

---

# 13. Reglas de dependencia entre capas

La dirección será:

```text
Interfaces
    ↓
Application
    ↓
Domain
```

Los adapters de infraestructura implementarán ports definidos por la aplicación.

```text
Infrastructure
    ↓
Application Ports
    ↓
Domain
```

El dominio nunca importará:

* Textual;
* DuckDB;
* ZMQ;
* Docker SDK;
* bibliotecas HTTP concretas;
* controladores de procesos;
* configuración del sistema operativo.

---

# 14. Estructura interna de los módulos

Cada módulo podrá contener:

```text
module/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── events.py
│   ├── policies.py
│   └── errors.py
├── application/
│   ├── commands.py
│   ├── queries.py
│   ├── handlers.py
│   ├── ports.py
│   └── dto.py
└── infrastructure/
    ├── adapters/
    ├── repositories/
    └── mappers/
```

No deberán crearse directorios o archivos vacíos únicamente por simetría.

---

# 15. Módulos funcionales

## 15.1 `bootstrap`

Responsabilidades:

* inicialización;
* contenedor de dependencias;
* selección de adapters;
* migraciones;
* registro de handlers;
* startup;
* shutdown.

No contendrá lógica de negocio.

---

## 15.2 `node`

Responsabilidades:

* ciclo de vida del nodo;
* configuración;
* health checks;
* datadir;
* estado de blockchain;
* sincronización;
* logs;
* compatibilidad de versiones.

Entidades:

* `Node`
* `NodeStatus`
* `NodeConfiguration`
* `NodeHealth`
* `ChainIdentity`

Ports:

* `NodeProcessPort`
* `BlockchainRpcPort`
* `NodeConfigurationRepository`
* `NodeLogPort`

---

## 15.3 `wallet`

Responsabilidades:

* creación;
* carga;
* direcciones;
* balances;
* UTXOs;
* transacciones;
* historial;
* coinbase maturity.

Reglas:

* ninguna clave privada saldrá del nodo;
* Bitheim no persistirá seeds;
* Bitheim no registrará secretos;
* las wallets serán administradas mediante RPC local.

---

## 15.4 `network`

Responsabilidades:

* peers;
* conexiones;
* topología;
* latencia;
* transporte;
* bytes;
* manifiestos;
* bootstrap peers;
* identidad de red.

El módulo no configurará Headscale.

---

## 15.5 `mining`

Responsabilidades:

* minería manual;
* minería competitiva;
* plantillas;
* coinbase;
* Merkle root;
* encabezados;
* nonces;
* SHA-256d;
* hashrate;
* envío de bloques;
* dificultad.

Backends:

* `RpcBlockProducer`
* `ProofOfWorkMiner`

---

## 15.6 `activity`

Responsabilidades:

* agentes sintéticos;
* perfiles;
* generación de transacciones;
* procesos estocásticos;
* montos;
* scheduling;
* semillas;
* etiquetado de origen.

Orígenes:

```text
human
synthetic
experiment
external
faucet
```

---

## 15.7 `experiments`

Responsabilidades:

* planes;
* precondiciones;
* ejecución;
* checkpoints;
* compensación;
* resultados;
* metadata;
* reproducibilidad.

Experimentos incluidos:

1. transferencia y confirmación;
2. propagación;
3. crecimiento de mempool;
4. desconexión y resincronización;
5. competencia minera;
6. reorganización;
7. dificultad;
8. consolidación de UTXOs.

---

## 15.8 `analytics`

Responsabilidades:

* eventos;
* snapshots;
* esquema analítico;
* consultas;
* datasets;
* métricas;
* exportaciones.

Tecnologías:

* DuckDB;
* Parquet;
* SQLite, solo si el estado operativo lo requiere.

---

## 15.9 `runtime`

Responsabilidades:

* procesos;
* scheduler;
* tareas;
* señales;
* graceful shutdown;
* locks;
* supervisión;
* recuperación;
* comunicación local.

---

## 15.10 `interfaces`

Contendrá:

* CLI;
* TUI;
* presentación;
* mapping de errores;
* DTOs.

No ejecutará RPC directamente.

---

## 15.11 `shared`

Solo incluirá elementos realmente compartidos:

* `Clock`;
* `EventBus`;
* identificadores;
* satoshis;
* errores base;
* serialización;
* utilidades verificadas.

No será un depósito genérico de funciones.

---

# 16. Procesos

## 16.1 Daemon

`bitheim daemon` será el proceso principal.

Responsabilidades:

* estado operativo;
* casos de uso;
* supervisión;
* eventos;
* tareas;
* API local.

## 16.2 API local

La TUI y CLI se comunicarán mediante:

* Unix Domain Socket en Linux/macOS;
* mecanismo local equivalente en Windows/WSL2;
* HTTP loopback como fallback.

Nunca se expondrá a la malla por defecto.

## 16.3 TUI

La TUI será un cliente descartable.

Cerrar la TUI no detendrá:

* nodo;
* minero;
* simulador;
* recolección;
* analítica.

---

# 17. Red blockchain

## 17.1 Etapa inicial: `regtest`

Se utilizará para desarrollar:

* nodo;
* wallets;
* TUI;
* transacciones;
* RPC;
* analítica;
* simulador;
* motor minero;
* actualizaciones.

## 17.2 Etapa objetivo: `labnet-v1`

Tendrá:

* génesis propio;
* identificador propio;
* magic bytes propios;
* puerto propio;
* monedas sin valor;
* PoW obligatorio;
* dificultad inicial;
* reajuste;
* validación distribuida;
* cadena independiente.

---

# 18. Dificultad distribuida

## 18.1 Regla

Cada nodo calculará independientemente el target esperado.

Ninguna autoridad central podrá cambiar la dificultad durante la operación.

Un bloque será aceptado únicamente cuando:

[
SHA256d(header) \leq target
]

y `nBits` represente el target esperado.

## 18.2 Parámetros iniciales

```yaml
target_spacing_seconds: 30
adjustment_interval_blocks: 20
target_timespan_seconds: 600
maximum_adjustment_factor: 4
allow_min_difficulty_blocks: false
no_retargeting: false
```

## 18.3 Ajuste

[
target_{new}
============

target_{old}
\times
\frac{actual\ timespan}
{expected\ timespan}
]

Con límites:

[
\frac{expected}{4}
\leq actual
\leq 4 \times expected
]

El target nunca superará `powLimit`.

## 18.4 Cambios futuros

Cualquier cambio incompatible requerirá:

* `labnet-v2`;
* red nueva; o
* mecanismo de activación explícito.

Hasta `v1.0.0`, se creará una red nueva.

---

# 19. Manifiesto de red

Ejemplo:

```yaml
format_version: 1

network:
  name: example-labnet
  protocol: labnet-v1
  network_id: "<generated>"
  genesis_hash: "<generated>"

bootstrap:
  peers:
    - node-a.example.internal:19444
    - node-b.example.internal:19444

features:
  simulation_enabled: false
  analytics_enabled: true
```

Los manifiestos reales permanecerán fuera del repositorio.

---

# 20. Actividad humana y sintética

Ambas coexistirán.

```text
Human wallet ───────┐
                    ├── Bitcoin Core ── mempool ── bloques
Synthetic agent ────┘
```

Bitcoin Core tratará ambas como transacciones reales.

Bitheim conservará metadata analítica sobre el origen.

## 20.1 Modelos incluidos

* Poisson homogéneo;
* Poisson por franjas;
* cantidades lognormales;
* pagos recurrentes;
* retail;
* comerciante;
* nómina;
* exchange simulado;
* whale;
* agente de estrés.

## 20.2 Reproducibilidad

```yaml
random_seed: 12345
duration_seconds: 3600
```

La fuente aleatoria será inyectable.

---

# 21. Almacenamiento analítico

## 21.1 Tablas mínimas

```text
nodes
node_snapshots
peers
peer_observations
blocks
block_observations
transactions
transaction_observations
mempool_events
wallet_events
utxo_snapshots
mining_sessions
mining_samples
difficulty_adjustments
experiments
experiment_events
system_metrics
```

## 21.2 Timestamps

* UTC;
* timezone-aware;
* ISO 8601 al exportar;
* precisión documentada.

## 21.3 Datos sensibles

No almacenar:

* claves;
* seeds;
* cookies;
* passwords;
* tokens;
* rutas personales;
* IP públicas sin consentimiento.

---

# 22. Estándares Python

## 22.1 Versión

La línea inicial utilizará Python 3.13.

La versión mínima soportada será declarada en `pyproject.toml`.

## 22.2 Packaging

Se utilizará:

* `pyproject.toml`;
* `src-layout`;
* wheel;
* source distribution;
* `uv.lock`;
* `.python-version`.

## 22.3 PEPs

El código seguirá:

* PEP 8;
* PEP 257;
* PEP 484;
* PEP 440;
* PEP 621.

## 22.4 Código Pythonico

Se preferirá:

* composición;
* dataclasses;
* enums;
* context managers;
* iteradores;
* `pathlib`;
* excepciones específicas;
* protocolos;
* value objects inmutables;
* satoshis enteros;
* `Decimal` cuando sea necesario.

Nunca se usarán `float` para cantidades monetarias.

## 22.5 Typing

Todo el código de producción estará tipado.

Reglas:

* evitar `Any`;
* justificar `# type: ignore`;
* validar JSON;
* DTOs tipados;
* interfaces explícitas;
* strict typing en CI.

## 22.6 Funciones

Las funciones deberán:

* tener responsabilidad clara;
* evitar efectos secundarios ocultos;
* recibir dependencias explícitas;
* evitar booleanos ambiguos;
* devolver tipos predecibles.

## 22.7 Docstrings

Explicarán:

* contrato;
* invariantes;
* errores;
* efectos secundarios.

No repetirán el código.

---

# 23. Manejo de errores

```text
BitheimError
├── ConfigurationError
├── NodeError
├── WalletError
├── NetworkError
├── MiningError
├── ExperimentError
├── AnalyticsError
└── SecurityError
```

Los adapters traducirán errores externos.

Los stack traces solo se mostrarán con modo debug.

---

# 24. Logging

Los logs contendrán:

* timestamp UTC;
* nivel;
* módulo;
* evento;
* correlation ID;
* node ID;
* experiment ID.

Nunca contendrán:

* cookies;
* claves;
* seeds;
* passwords;
* `Authorization`;
* secretos;
* configuración no sanitizada.

---

# 25. Seguridad

## 25.1 Modelo de amenazas

Se documentarán:

* participante curioso;
* nodo mal configurado;
* imagen comprometida;
* dependencia vulnerable;
* filtración en Git;
* RPC expuesto;
* manifiesto manipulado;
* escenario malicioso;
* acceso local;
* supply-chain attacks.

## 25.2 RPC

RPC:

* solo localhost;
* cookie authentication;
* nunca enviada por red;
* nunca registrada;
* leída bajo demanda;
* mantenida en memoria el mínimo tiempo.

## 25.3 P2P

Solo se publicará el puerto P2P.

El bind será explícito.

No se usará `0.0.0.0` como valor público predeterminado.

## 25.4 Contenedores

* usuario no root;
* root filesystem de solo lectura cuando sea posible;
* capabilities eliminadas;
* `no-new-privileges`;
* health checks;
* límites;
* sin modo privilegiado;
* sin Docker socket.

## 25.5 Secretos

No deberán almacenarse en:

* Dockerfile;
* build args;
* repositorio;
* imágenes;
* `.env` versionado.

## 25.6 Gitignore

```text
.venv/
.env
.env.*
!.env.example
.local/
data/
wallets/
*.cookie
*.sqlite
*.duckdb
*.parquet
*.log
*.pem
*.key
*.crt
network.local.yaml
compose.override.yaml
secrets/
backups/
```

---

# 26. Dependencias

Toda dependencia deberá:

* tener propósito;
* estar mantenida;
* tener licencia compatible;
* estar declarada mediante `uv`;
* quedar fijada en `uv.lock`;
* pasar revisión.

Una PR que agregue una dependencia deberá explicar:

* problema;
* alternativas;
* impacto;
* licencia;
* riesgo;
* estrategia de eliminación.

---

# 27. Herramientas de calidad

La configuración vivirá en `pyproject.toml`.

Categorías obligatorias:

* formatting;
* linting;
* static typing;
* tests;
* coverage;
* dependency audit;
* secret detection;
* static security;
* Dockerfile validation;
* YAML/JSON validation.

Comandos:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Wrappers:

```bash
make check
make test
make security
make build
```

---

# 28. Testing

## 28.1 Unit tests

Cubrirán:

* dominio;
* value objects;
* políticas;
* dificultad;
* minería;
* serialización;
* random generators;
* handlers.

## 28.2 Integration tests

Cubrirán:

* RPC;
* DuckDB;
* ZMQ;
* filesystem;
* daemon;
* migraciones.

## 28.3 Contract tests

Cubrirán:

* Bitheim ↔ Bitcoin Core;
* TUI ↔ daemon;
* manifests ↔ schemas;
* scenarios ↔ runner;
* exportadores.

## 28.4 End-to-end tests

Levantarán redes efímeras de:

* un nodo;
* dos nodos;
* tres nodos.

Validarán:

* wallets;
* transacciones;
* minería;
* propagación;
* reorg;
* retarget;
* actualizaciones.

## 28.5 Security tests

Validarán:

* RPC cerrado;
* permisos;
* secretos;
* path traversal;
* contenedores no root;
* puertos.

## 28.6 Property-based testing

Para dificultad:

* mismo historial → mismo target;
* target ≤ `powLimit`;
* ajuste limitado;
* bloques rápidos → más dificultad;
* bloques lentos → menos dificultad;
* hash alto → rechazo;
* chainwork monotónico.

## 28.7 Cobertura

Objetivos:

* dominio: 95%;
* dificultad: ramas relevantes completas;
* total inicial: 85%.

---

# 29. Desarrollo local

## 29.1 Bootstrap

```bash
git clone <repository>
cd bitheim
uv python install
uv sync --all-groups
uv run bitheim doctor
```

## 29.2 Ejecución

```bash
uv run bitheim start
uv run bitheim tui
```

## 29.3 Tests

```bash
uv run pytest
```

## 29.4 Datos locales

```text
.local/
├── data/
├── logs/
├── secrets/
├── exports/
└── networks/
```

---

# 30. Docker

## 30.1 Arquitecturas

* `linux/amd64`;
* `linux/arm64`.

## 30.2 Perfiles

```text
default
mining
simulation
analytics
development
```

## 30.3 Ejemplos

```bash
docker compose up -d

docker compose --profile mining up -d

docker compose \
  --profile mining \
  --profile simulation \
  --profile analytics \
  up -d
```

## 30.4 Versiones

No se usará `latest`.

```yaml
image: ghcr.io/example/bitheim:0.4.0
image: ghcr.io/example/bitheim-core:31.1-labnet.1
```

## 30.5 Persistencia

```text
bitcoin-data
wallet-data
bitheim-state
analytics-data
exports
```

---

# 31. TUI

Vistas:

```text
Overview
Wallet
Transactions
Blocks
Mempool
Peers
Mining
Difficulty
Activity
Experiments
Analytics
Logs
Settings
RPC Console
```

La TUI deberá:

* funcionar sin color;
* soportar terminales pequeñas;
* documentar atajos;
* confirmar acciones destructivas;
* mostrar errores accionables.

---

# 32. CLI

```text
bitheim install
bitheim start
bitheim stop
bitheim status
bitheim tui
bitheim wallet create
bitheim wallet send
bitheim peers list
bitheim miner start
bitheim miner stop
bitheim simulate start
bitheim experiment run
bitheim export
bitheim doctor
bitheim update check
bitheim update apply
```

Desde desarrollo:

```bash
uv run bitheim status
```

Salidas:

* `human`;
* `json`.

---

# 33. Configuración

Prioridad:

```text
defaults
→ bitheim.toml
→ variables permitidas
→ CLI flags
```

No se admitirán secretos mediante flags.

La aplicación fallará ante:

* campos inválidos;
* paths inseguros;
* puertos inválidos;
* IP pública inesperada;
* protocolo incompatible;
* RPC expuesto.

---

# 34. Versionado

Se utilizará Semantic Versioning.

Se versionarán separadamente:

```text
Bitheim version
Node distribution version
Labnet protocol version
Manifest format version
Analytics schema version
```

Ejemplo:

```yaml
bitheim_version: 0.6.0
bitcoin_base_version: 31.1
node_distribution: 31.1-labnet.3
labnet_protocol: 1
manifest_format: 1
analytics_schema: 4
```

---

# 35. Git

## 35.1 Flujo

Trunk-based development ligero:

* `main` siempre integrable;
* ramas cortas;
* pull requests;
* feature flags.

## 35.2 Pull requests

Toda PR incluirá:

* problema;
* solución;
* riesgos;
* pruebas;
* impacto arquitectónico;
* impacto de seguridad;
* documentación.

No podrá fusionarse con:

* CI fallando;
* secretos;
* review pendiente;
* vulnerabilidad crítica;
* cambio arquitectónico sin ADR.

## 35.3 Revisión

Cambios de:

* consenso;
* seguridad;
* wallets;
* releases;
* Docker;
* manifests;
* migraciones;

requerirán revisión de ambos mantenedores.

---

# 36. Architecture Decision Records

```text
ADR-0001: Modular Monolith
ADR-0002: Hexagonal Architecture
ADR-0003: uv Project Management
ADR-0004: DuckDB and Parquet
ADR-0005: Docker Compose
ADR-0006: Labnet Parameters
ADR-0007: Local Daemon API
ADR-0008: Multi-Architecture Images
ADR-0009: Project Naming — Bitheim
```

Cada ADR contendrá:

* contexto;
* decisión;
* alternativas;
* consecuencias;
* estado.

---

# 37. CI/CD

## 37.1 Pull request

1. `uv sync --locked`;
2. format check;
3. lint;
4. typing;
5. unit tests;
6. integration tests;
7. dependency review;
8. secret scanning;
9. security analysis;
10. package build;
11. image build;
12. smoke test;
13. documentation validation.

## 37.2 Main

Además:

* E2E multi-nodo;
* `amd64`;
* `arm64`;
* reorg;
* retarget;
* upgrade;
* rollback.

## 37.3 Release

1. validar tag;
2. generar changelog;
3. ejecutar suite;
4. construir imágenes;
5. construir wheel;
6. generar SBOM;
7. escanear;
8. firmar;
9. generar provenance;
10. publicar RC;
11. smoke test;
12. promoción manual.

---

# 38. Supply-chain security

Antes de `v1.0.0`:

* dependencias fijadas;
* `uv.lock`;
* dependency review;
* SBOM;
* imágenes firmadas;
* provenance;
* GitHub Actions fijadas;
* permisos mínimos;
* branch protection;
* escaneo de contenedores;
* OpenSSF Scorecard.

---

# 39. Releases y actualizaciones

## 39.1 Canales

```text
dev
alpha
beta
rc
stable
```

## 39.2 Proceso

```text
1. Comprobar compatibilidad.
2. Mostrar notas.
3. Verificar firma.
4. Crear backup.
5. Descargar artefactos.
6. Validar espacio.
7. Detener procesos.
8. Migrar.
9. Iniciar.
10. Ejecutar health checks.
11. Confirmar.
12. Rollback si falla.
```

Ninguna actualización ordinaria cambiará silenciosamente `labnet-v1`.

---

# 40. Roadmap hasta `v1.0.0`

## `v0.1.0` — Foundation

### Entregables

* repositorio `bitheim`;
* proyecto administrado por `uv`;
* `pyproject.toml`;
* `uv.lock`;
* `.python-version`;
* `src-layout`;
* monolito modular;
* arquitectura hexagonal;
* CLI mínima;
* configuración;
* logging;
* CI;
* Docker;
* documentación;
* políticas open source;
* ADRs.

### Aceptación

* `uv sync` reproduce el entorno;
* `uv run bitheim --help` funciona;
* imágenes `amd64` y `arm64`;
* CI obligatorio;
* cero secretos.

---

## `v0.2.0` — Managed Regtest Node

### Entregables

* gestión de Bitcoin Core;
* datadir;
* health;
* RPC cookie;
* wallet;
* transacciones humanas;
* bloques;
* mempool;
* peers;
* CLI JSON;
* TUI básica.

### Aceptación

Dos usuarios pueden levantar nodos, conectarlos, crear wallets y realizar una transacción.

---

## `v0.3.0` — Analytics Foundation

### Entregables

* recolector;
* eventos;
* DuckDB;
* snapshots;
* CSV;
* Parquet;
* consultas;
* paneles TUI.

### Aceptación

Una transacción puede seguirse desde su creación hasta su confirmación.

---

## `v0.4.0` — Synthetic Activity

### Entregables

* agentes;
* scheduler;
* Poisson;
* montos;
* seeds;
* perfiles;
* escenarios;
* origen.

### Aceptación

Un escenario genera transacciones Bitcoin válidas y reproducibles.

---

## `v0.5.0` — External PoW Miner

### Entregables

* `getblocktemplate`;
* coinbase;
* Merkle root;
* header;
* SHA-256d;
* workers;
* hashrate;
* `submitblock`;
* límites.

### Aceptación

Dos mineros compiten por producir un bloque.

---

## `v0.6.0` — Labnet Prototype

### Entregables

* fork mínimo;
* génesis;
* magic bytes;
* puertos;
* PoW obligatorio;
* retarget;
* manifest;
* pruebas.

### Aceptación

Un bloque con PoW insuficiente es rechazado por todos los nodos.

---

## `v0.7.0` — Distributed Mining

### Entregables

* perfiles;
* dificultad visible;
* retarget;
* stale blocks;
* reorgs;
* métricas;
* cambio de hashrate.

### Aceptación

Dos equipos diferentes mantienen una cadena con dificultad distribuida.

---

## `v0.8.0` — Experiment Workbench

### Entregables

* runner;
* transfer;
* propagation;
* congestion;
* partition;
* reorg;
* UTXO consolidation;
* difficulty experiment;
* checkpoints;
* reportes.

### Aceptación

Los experimentos pueden ejecutarse, repetirse y exportarse.

---

## `v0.9.0` — Operational Hardening

### Entregables

* update;
* rollback;
* backups;
* doctor;
* security tests;
* SBOM;
* firmas;
* provenance;
* documentación;
* performance;
* Mac/Linux/WSL2.

### Aceptación

El sistema puede actualizarse y recuperarse ante un fallo inducido.

---

## `v1.0.0` — Stable Release

### Requisitos

* API estable;
* CLI estable;
* manifest estable;
* configuración estable;
* `labnet-v1` congelado;
* migraciones;
* rollback;
* imágenes firmadas;
* SBOM;
* documentación completa;
* seguridad documentada;
* `amd64`;
* `arm64`;
* pruebas en los dos usuarios;
* cero vulnerabilidades críticas conocidas;
* release candidate validado en uso real.

---

# 41. Criterios no funcionales

## Seguridad

* RPC no accesible desde la malla.
* Sin secretos en repositorio.
* Contenedores no root.
* Releases verificables.
* Configuración segura.

## Rendimiento

En estado base:

* Bitheim menor a 150 MiB de RAM;
* TUI responsiva;
* startup razonable;
* minería configurable;
* sesiones prolongadas soportadas.

## Fiabilidad

* graceful shutdown;
* reinicio sin corrupción;
* recuperación;
* migraciones idempotentes;
* backups verificables.

## Mantenibilidad

* sin dependencias circulares;
* typing estricto;
* documentación;
* tests;
* ADRs;
* deuda registrada.

## Escalabilidad

Dos nodos serán el caso principal.

El diseño deberá tolerar más participantes sin cambiar la arquitectura central.

---

# 42. Definición de terminado

Una tarea estará terminada cuando:

* código implementado;
* tests;
* typing;
* lint;
* documentación;
* revisión de seguridad;
* logs sanitizados;
* errores manejados;
* criterios cumplidos;
* CI verde;
* lockfile actualizado cuando corresponda.

---

# 43. Gobernanza

Los dos mantenedores serán responsables de:

* roadmap;
* arquitectura;
* seguridad;
* releases;
* revisión;
* soporte.

Ante desacuerdo:

1. documentar alternativas;
2. crear experimento;
3. medir;
4. elegir la opción más segura y reversible.

---

# 44. Licencia y contribuciones

Antes del primer release público se elegirán:

* licencia;
* política de contribución;
* código de conducta;
* política de seguridad;
* gobernanza.

Archivos obligatorios:

```text
LICENSE
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
GOVERNANCE.md
```

No se aceptarán contribuciones que:

* introduzcan telemetría no consentida;
* relajen seguridad;
* expongan RPC;
* incorporen datos reales;
* eludan consenso;
* agreguen dependencias sin revisión.

---

# 45. Documentación obligatoria

```text
README
Quick Start
Installation
uv Development Workflow
Architecture Overview
Module Boundaries
Security Model
Threat Model
Configuration Reference
Network Manifest Reference
CLI Reference
TUI Guide
Mining Guide
Analytics Guide
Experiment Guide
Update and Rollback
Backup and Recovery
Troubleshooting
Development Guide
Release Process
Contribution Guide
```

---

# 46. Riesgos

## Fork de Bitcoin Core

Mitigación:

* delta mínimo;
* commits aislados;
* tests;
* seguimiento de upstream;
* documentación.

## Exposición de red

Mitigación:

* bind explícito;
* doctor;
* tests;
* ejemplos ficticios;
* RPC local.

## Complejidad

Mitigación:

* monolito modular;
* roadmap incremental;
* scope estricto;
* sin panel web antes de `1.0.0`.

## Pocos usuarios

Mitigación:

* diseñar para dos;
* automatizar pruebas multi-nodo;
* simulador opcional;
* no sobredimensionar.

## Plataformas

Mitigación:

* Docker;
* multi-arquitectura;
* CI;
* pruebas reales;
* doctor.

## Divergencia de entornos Python

Mitigación:

* `uv`;
* `.python-version`;
* `uv.lock`;
* `uv sync --locked`;
* mismos comandos en local, CI y Docker.

## Pérdida de datos

Mitigación:

* volúmenes;
* backups;
* migraciones;
* rollback;
* snapshots.

---

# 47. Resultado esperado

Al alcanzar `v1.0.0`, Bitheim permitirá que dos usuarios:

1. clonen o instalen la misma distribución;
2. reproduzcan el entorno Python con `uv`;
3. ejecuten el sistema en arquitecturas distintas;
4. se unan a una red privada existente;
5. creen una red `labnet-v1`;
6. ejecuten nodos reales;
7. creen wallets;
8. realicen transacciones válidas;
9. participen en minería competitiva;
10. observen dificultad distribuida;
11. generen actividad sintética opcional;
12. ejecuten experimentos;
13. analicen datos;
14. exporten resultados;
15. actualicen Bitheim;
16. reviertan una actualización fallida;
17. comprendan qué ocurre detrás de cada abstracción.

Bitheim deberá permanecer suficientemente pequeño para ser operado y mantenido por dos personas, pero contar con fundamentos técnicos, arquitectónicos y de seguridad que permitan extenderlo después de `v1.0.0` sin una reescritura completa.
