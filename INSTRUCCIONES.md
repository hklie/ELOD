# ELOD - Sistema de Rating ELO para Torneos de Scrabble Duplicada

**Versión 1.1 — Marzo 2026**

ELOD es un calculador de ratings diseñado para **torneos de Scrabble Duplicada** organizados bajo el marco de FILE (Federación Internacional de Léxico en Español). Procesa resultados de torneos desde archivos de texto, bases de datos Microsoft Access e imágenes, y calcula y hace seguimiento de los ratings ELO de los jugadores a lo largo del tiempo.

---

## Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Archivos de Entrada](#archivos-de-entrada)
3. [Cómo Agregar Resultados de Torneos](#cómo-agregar-resultados-de-torneos)
4. [Cómo Ejecutar el Programa](#cómo-ejecutar-el-programa)
5. [Resultados y Archivos de Salida](#resultados-y-archivos-de-salida)
6. [Estructura del Proyecto](#estructura-del-proyecto)
7. [Cálculo ELO](#cálculo-elo)
8. [Licencia](#licencia)
9. [Colaboradores](#colaboradores)
10. [Historial de Versiones](#historial-de-versiones)

---

## Descripción General

ELOD procesa resultados de torneos de múltiples eventos a lo largo de varios años, comparando cada par de jugadores por su posición en el ranking y calculando cambios en el rating ELO basados en factores K ajustados por experiencia. Produce archivos CSV de ranking por torneo y un libro Excel consolidado que muestra la progresión de cada jugador.

Los ratings ELOD correspondientes a jugadores de la **Copa FILE** se calculan automáticamente a partir de cada partida mundial de duplicada.

### Características Principales

- Cálculo de ratings ELO a partir de rankings de torneos
- Soporte para formatos `.txt`, `.mdb`, `.accdb`, `.html`/`.htm` e imágenes (`.jpeg`, `.png`)
- Factor K basado en experiencia: mayor ajuste para jugadores nuevos
- Sistema de alias de nombres para unificar variaciones de ortografía y acentos
- Exclusión de jugadores fallecidos del ranking final
- Seguimiento progresivo: libro Excel con deltas ELO por torneo
- Sistema de manifiestos para organizar torneos cronológicamente
- Auto-inicialización de nuevos jugadores con un rating por defecto configurable

---

## Archivos de Entrada

Todos los datos de entrada se encuentran en el directorio `data/`, organizados por año.

### 1. Archivos de Torneos

Contienen los resultados del torneo — nombres de jugadores ordenados por clasificación final (1er lugar primero).

| Formato | Extensión | Descripción |
|---------|-----------|-------------|
| Texto | `.txt` | Un nombre de jugador por línea, en orden de clasificación |
| Access DB | `.mdb`, `.accdb` | Base de datos Microsoft Access generada por **DupMaster** (el programa utilizado para gestionar torneos de Duplicada), con tablas `Jugadores` y `Relaciones`. |
| HTML | `.html`, `.htm` | Página HTML de clasificación exportada por **DupMaster** (ej., `Clasificacion.html`). No requiere dependencias externas. |
| Imagen | `.jpeg`, `.png` | Resultados escaneados (procesados vía OCR; un archivo `.txt` con el mismo nombre tiene prioridad) |

**Ejemplo de archivo de texto** (`Europeo_2025.txt`):
```
SergeEmig
AntonioAlvarez
CarlosGarcia
MarinaColson
ArantxaDelgado
```

**Tablas de base de datos Access:**

| Tabla | Columnas | Propósito |
|-------|----------|-----------|
| `Jugadores` | `Indice`, `Nombre`, `Acronim` | Información de jugadores |
| `Relaciones` | `Jugador`, `Ronda`, `PuntuacionAcumulada` | Puntuaciones por ronda |

**Ubicación:** `data/AAAA/` (ej., `data/2025/Europeo_2025.txt`)

### 2. Manifiesto de Torneos (`.manifiesto`)

El manifiesto es la lista maestra que indica a ELOD qué torneos procesar y en qué orden. Cada entrada de torneo tiene una línea de fecha seguida de uno o más archivos de torneo.

**Formato:**
```
DD-MM-AAAA  # Nombre del Evento
archivo_torneo1.txt
archivo_torneo2.mdb
```

**Ejemplo** (`data/torneos_all.manifiesto`):
```
1-08-2025 # Europeo Murcia 2025
2025/Europeo_2025.txt

01-11-2025  # Mundial Santiago de Chile 2025
2025/Duplicada Mundial 1 - 2025.accdb
2025/Duplicada Mundial 2 - 2025.accdb
2025/Duplicada Mundial 3 - 2025.accdb
```

Cada año también tiene su propio manifiesto en `data/AAAA/torneos_AAAA.manifiesto`. El script `regenerate_all.py` los combina en `data/torneos_all.manifiesto`.

### 3. Archivo de Alias de Jugadores (`.alias`)

Mapea variantes de ortografía, acentos y formatos de nombre a un único nombre canónico.

**Ubicación:** `data/jugadores_all.alias`

**Formato:**
```
# nombre_canónico = alias1, alias2, ...
AiranPérez = AiranPerez
XavierPiqué = XaviPiqué
JoséGonzález = GONZALEZ,José; GONZALEZ,J
```

### 4. Archivo de Jugadores Fallecidos

Los jugadores listados aquí son excluidos del ranking final (pero se incluyen en los cálculos ELO).

**Ubicación:** `data/jugadores_fallecidos.txt`

```
FreddyRamírez
EnriqueCortés
MarthaGalindo
```

### 5. Archivo de Nombres de Display

Nombres de visualización personalizados para jugadores con apellidos compuestos que el algoritmo automático no puede separar correctamente.

**Ubicación:** `data/nombres_display.txt`

```
DavidLozanoGaray = LOZANO GARAY, David
MaríaMartaGismondi = GISMONDI, María Marta
MaríadeArcos = DE ARCOS, María
```

### 6. Archivo de Ratings Iniciales (`.elod`) — Opcional

Si desea comenzar con ratings preexistentes en lugar de auto-inicializar a todos, proporcione un archivo `.elod` con columnas separadas por tabulaciones/espacios:

```
NombreJugador    ELO    Partidas    Torneos    UltimoTorneo
Alice            1800   0           0          -
Bob              1750   50          10         torneo5.txt
```

---

## Cómo Agregar Resultados de Torneos

Esta sección explica el flujo de trabajo paso a paso para incorporar resultados de un nuevo torneo.

### Paso 1: Preparar el Archivo del Torneo

- Si tiene un **ranking en texto**, cree un archivo `.txt` con un nombre de jugador por línea en orden de clasificación final (1er lugar en la primera línea). Use CamelCase sin espacios (ej., `CarlosGarcia`, `XavierPiqué`).
- Si tiene una **base de datos Microsoft Access** (`.mdb` o `.accdb`) generada por **DupMaster**, colóquela tal cual en la carpeta del año. DupMaster es el programa utilizado para gestionar torneos de Duplicada y exporta los resultados como bases de datos Access (así como páginas HTML de clasificación).
- Si solo tiene una **foto/escaneo** de los resultados (`.jpeg` o `.png`), coloque la imagen en la carpeta del año. Para mejores resultados, cree también un archivo `.txt` con el mismo nombre base como transcripción manual (ELOD preferirá el `.txt` sobre el OCR).

### Paso 2: Colocar el Archivo en la Carpeta del Año Correcto

Coloque el archivo bajo `data/AAAA/`, donde `AAAA` es el año del torneo. Por ejemplo:

```
data/2025/Europeo_2025.txt
```

### Paso 3: Actualizar el Manifiesto del Año

Abra el archivo de manifiesto del año en `data/AAAA/torneos_AAAA.manifiesto` y agregue una entrada para el nuevo torneo:

```
DD-MM-AAAA  # Nombre del Evento
nombre_archivo.txt
```

Para torneos de múltiples partes (ej., un Campeonato Mundial con 3 sesiones), liste todos los archivos bajo la misma línea de fecha:

```
01-11-2025  # Mundial Santiago de Chile 2025
Duplicada Mundial 1 - 2025.accdb
Duplicada Mundial 2 - 2025.accdb
Duplicada Mundial 3 - 2025.accdb
```

### Paso 4: Verificar Nuevos Nombres de Jugadores

Si algún nombre de jugador es una variante nueva de un jugador existente (diferentes acentos, diferente ortografía), agregue una entrada de alias en `data/jugadores_all.alias`:

```
NombreCanónico = NuevaVariante
```

También puede ejecutar el programa con la opción `--check-names` para auto-detectar posibles duplicados.

### Paso 5: Regenerar Todos los Resultados

Ejecute el script de regeneración (ver [Cómo Ejecutar el Programa](#cómo-ejecutar-el-programa) a continuación).

---

## Cómo Ejecutar el Programa

### Opción A: Ejecutable de Windows (Recomendado para usuarios de Windows)

No requiere instalación — solo descargue y ejecute.

1. Vaya a la página de [Releases](../../releases) y descargue el último archivo `elod-windows-vX.X.X.zip`
2. Descomprima el archivo en una carpeta de su computadora (ej., `C:\ELOD`)
3. Coloque sus archivos de torneo en las carpetas `data/AAAA/` (ej., `data/2025/`)
4. Actualice el manifiesto del año en `data/AAAA/torneos_AAAA.manifiesto`
5. Haga doble clic en **`run_elod.bat`** para procesar todos los torneos
6. Los resultados aparecerán en la carpeta `output/`

También puede ejecutar `elod.exe` directamente desde la línea de comandos:
```cmd
elod.exe --data-path data --output-path output
```

### Opción B: Ejecutar desde el Código Fuente en Python

#### Requisitos Previos

Necesita tener instalado lo siguiente en su computadora:

1. **Python 3.7 o superior** — Descárguelo desde [python.org](https://www.python.org/downloads/) e instálelo. Durante la instalación en Windows, marque la casilla que dice "Add Python to PATH".

2. **mdbtools** (solo necesario si procesa archivos `.mdb`):
   ```bash
   # En Ubuntu/Debian Linux:
   sudo apt-get install mdbtools

   # En macOS con Homebrew:
   brew install mdbtools
   ```

3. **Dependencias de Python:**
   ```bash
   pip install -r requirements.txt
   ```

#### Obtener el Código

Descargue o clone la carpeta del proyecto en su computadora. Abra una terminal (Símbolo del sistema en Windows, Terminal en macOS/Linux) y navegue a la carpeta del proyecto:

```bash
cd ruta/a/elod
```

### La Forma Fácil: Regenerar Todo

La forma más sencilla de ejecutar el programa es usar `regenerate_all.py`, que lee todos los manifiestos por año, los combina y produce todos los archivos de salida:

```bash
python regenerate_all.py
```

Esto hará lo siguiente:
1. Leerá los manifiestos de año de `data/2022/`, `data/2023/`, `data/2024/`, `data/2025/`, etc.
2. Generará el manifiesto combinado `data/torneos_all.manifiesto`
3. Procesará todos los torneos en orden cronológico
4. Producirá todos los archivos CSV de salida y el libro Excel consolidado en la carpeta `output/`

**Opciones:**
```bash
# Solo regenerar el manifiesto combinado (omitir procesamiento ELO):
python regenerate_all.py --manifest-only

# Especificar rutas personalizadas:
python regenerate_all.py --data-path data --output-path output
```

### Ejecutar Componentes Individuales

**Procesar torneos desde un manifiesto:**
```bash
python elod.py \
  --manifest data/torneos_all.manifiesto \
  --aliases data/jugadores_all.alias \
  --deceased data/jugadores_fallecidos.txt \
  --output ./output \
  --auto-init
```

**Generar solo el libro Excel:**
```bash
python generate_progressive.py \
  -m data/torneos_all.manifiesto \
  -a data/jugadores_all.alias \
  -b data \
  -d data/jugadores_fallecidos.txt \
  -n data/nombres_display.txt \
  -o output/elod_progresivos.xlsx
```

**Extraer rankings de una sola base de datos Access:**
```bash
python mdb_reader.py torneo.mdb --format clasificacion --output rankings.txt
```

**Verificar posibles nombres de jugadores duplicados:**
```bash
python elod.py \
  --manifest data/torneos_all.manifiesto \
  --aliases data/jugadores_all.alias \
  --auto-init --check-names --quiet
```

### Referencia de Argumentos de Línea de Comandos

| Argumento | Corto | Descripción |
|-----------|-------|-------------|
| `--base-path` | `-b` | Directorio base para archivos de datos |
| `--players-file` | `-p` | Archivo de ratings iniciales de jugadores (`.elod`) |
| `--tournaments` | `-t` | Archivos de torneo a procesar (`.txt`, `.mdb`, `.accdb`) |
| `--manifest` | `-m` | Archivo de manifiesto de torneos (alternativa a `--tournaments`) |
| `--output` | `-o` | Directorio de salida para resultados |
| `--auto-init` | `-a` | Auto-inicializar nuevos jugadores desde torneos |
| `--default-elo` | `-e` | ELO por defecto para nuevos jugadores (defecto: 2075) |
| `--aliases` | | Archivo de alias de nombres de jugadores |
| `--deceased` | | Archivo de jugadores fallecidos |
| `--check-names` | | Detectar posibles nombres duplicados |
| `--quiet` | `-q` | Suprimir mensajes de progreso |

### Ejecutar Pruebas

```bash
python test_elod.py
```

---

## Resultados y Archivos de Salida

Todos los archivos de salida se colocan en el directorio `output/`.

### Archivos CSV por Torneo

Para cada torneo procesado, se genera un archivo CSV con el nombre del torneo (ej., `Europeo_2025.csv`). Columnas:

| Columna | Descripción |
|---------|-------------|
| `Posición` | Posición final en el ranking |
| `Jugador` | Nombre del jugador (canónico, con alias aplicados) |
| `ELOD Inicial` | Rating ELO antes de este torneo |
| `Delta ELOD` | Cambio en el rating (+ o -) |
| `ELOD Final` | Rating después de este torneo |
| `N. Oponentes` | Número de oponentes enfrentados |
| `N. Partidas` | Total de partidas jugadas (acumulado) |
| `Último Torneo` | Nombre para mostrar del torneo |

### CSV de Rankings Finales

El archivo `elod_final.csv` (producido por el último torneo procesado) contiene la clasificación general después de todos los torneos. Mismo formato de columnas que arriba. Los jugadores fallecidos se excluyen de este archivo.

### Libro Excel Progresivo

El archivo `elod_progresivos.xlsx` es un libro Excel consolidado que rastrea la progresión ELO de cada jugador a través de todos los torneos:

- **Encabezado institucional** con nombre de FILE, logo y fecha de generación dinámica (en español)
- Orden de columnas: Deltas acumulados, Pos., JUGADOR, País, ELOD Actual (resaltado en amarillo), Último Torneo, N.Oponentes, N.Partidas, seguido de columnas de delta por torneo
- **Encabezados de torneo en vertical** para visualización compacta de muchas columnas
- Fila de conteo de participantes debajo de los encabezados
- Celdas de delta con código de colores (verde para positivo, rojo para negativo)
- Paneles congelados (primeras 3 columnas + primeras 5 filas) para navegación fácil

### Lista de Archivos de Salida (Ejemplo)

```
output/
├── Europeo_2025.csv
├── Duplicada Mundial 1 - 2025.accdb.csv
├── Duplicada Mundial 2 - 2025.accdb.csv
├── Duplicada Mundial 3 - 2025.accdb.csv
├── PartidaBaAs1.csv
├── ...                          (un CSV por torneo)
├── elod_final.csv               (rankings finales generales)
└── elod_progresivos.xlsx        (libro Excel consolidado)
```

---

## Estructura del Proyecto

```
elod/
├── elod.py                  # Clase orquestadora principal
├── elo_math.py              # Fórmulas de cálculo ELO
├── player.py                # Modelo de datos de jugador
├── tournament.py            # Parser de archivos .txt de torneo
├── mdb_reader.py            # Lector de bases de datos Microsoft Access
├── html_reader.py           # Lector de clasificaciones HTML de DupMaster
├── image_reader.py          # Procesamiento OCR de imágenes (opcional)
├── generate_progressive.py  # Genera el libro Excel
├── regenerate_all.py        # Combina manifiestos y regenera toda la salida
├── test_elod.py             # Suite de pruebas
├── __init__.py              # Exportaciones del paquete
├── requirements.txt         # Dependencias de Python
├── elod.spec                # Spec de PyInstaller para construir el .exe de Windows
│
├── .github/workflows/
│   └── build.yml            # CI/CD: construye elod.exe al hacer push de un tag git
│
├── scripts/
│   └── run_elod.bat         # Lanzador de doble clic para Windows
│
├── data/                    # Directorio de datos de torneos
│   ├── 2022/                # Carpetas por año con archivos de torneo
│   ├── 2023/                #   y manifiestos específicos por año
│   ├── 2024/
│   ├── 2025/
│   ├── torneos_all.manifiesto     # Manifiesto combinado (auto-generado)
│   ├── jugadores_all.alias        # Alias de nombres de jugadores
│   ├── jugadores_fallecidos.txt   # Lista de jugadores fallecidos
│   ├── nombres_display.txt        # Nombres de visualización personalizados
│   └── FILE1.jpg                  # Logo de FILE para el encabezado Excel
│
├── output/                  # Resultados generados
│   ├── *.csv                # Archivos de ranking por torneo
│   └── elod_progresivos.xlsx
│
└── resources/               # Recursos de prueba
    └── FILE/
        ├── game_test.txt
        └── inicio.elod
```

---

## Cálculo ELO

### Fórmula

1. **Probabilidad Esperada de Victoria:**
   ```
   E = (1 + erf(diferencia_rating / 400)) / 2
   ```

2. **Factor K (basado en experiencia):**
   - Jugadores nuevos (< 50 partidas): K = 25
   - Jugadores experimentados (>= 50 partidas): K = 10

3. **Cambio de Rating:**
   ```
   Delta ELO = K x (resultado_real - probabilidad_esperada)
   ```

### Procesamiento de Torneos

En un torneo con N jugadores, cada jugador se compara por pares contra todos los demás jugadores. Un jugador con mejor clasificación "gana" cada comparación por pares. Total de partidas por jugador = N - 1.

**Ejemplo:** En un torneo de 5 jugadores, el jugador en 1er lugar gana 4 comparaciones por pares (contra las posiciones 2-5), mientras que el jugador en 5to lugar pierde 4.

### Constantes de Configuración

| Constante | Valor | Descripción |
|-----------|-------|-------------|
| `K_NEW_PLAYER` | 25 | Factor K para jugadores con < 50 partidas |
| `K_EXPERIENCED` | 10 | Factor K para jugadores con >= 50 partidas |
| `GAMES_THRESHOLD` | 50 | Partidas necesarias para ser "experimentado" |
| `RATING_FACTOR` | 400 | Factor estándar de diferencia de rating ELO |
| `DEFAULT_ELO` | 2075 | Rating por defecto para nuevos jugadores |

---

## Licencia

Licencia MIT

Copyright (c) 2026 FILE (Federación Internacional de Léxico en Español)

Por la presente se concede permiso, libre de cargos, a cualquier persona que obtenga
una copia de este software y de los archivos de documentación asociados (el "Software"),
a utilizar el Software sin restricción, incluyendo sin limitación los derechos a usar,
copiar, modificar, fusionar, publicar, distribuir, sublicenciar y/o vender copias del
Software, y a permitir a las personas a las que se les proporcione el Software a hacer
lo mismo, sujeto a las siguientes condiciones:

El aviso de copyright anterior y este aviso de permiso se incluirán en todas las copias
o partes sustanciales del Software.

EL SOFTWARE SE PROPORCIONA "COMO ESTÁ", SIN GARANTÍA DE NINGÚN TIPO, EXPRESA O
IMPLÍCITA, INCLUYENDO PERO NO LIMITADO A GARANTÍAS DE COMERCIALIZACIÓN, IDONEIDAD
PARA UN PROPÓSITO PARTICULAR Y NO INFRACCIÓN. EN NINGÚN CASO LOS AUTORES O TITULARES
DEL COPYRIGHT SERÁN RESPONSABLES DE NINGUNA RECLAMACIÓN, DAÑO U OTRA RESPONSABILIDAD,
YA SEA EN UNA ACCIÓN DE CONTRATO, AGRAVIO O CUALQUIER OTRO MOTIVO, QUE SURJA DE O EN
CONEXIÓN CON EL SOFTWARE O EL USO U OTRO TIPO DE ACCIONES EN EL SOFTWARE.

---

## Colaboradores

- Héctor Klie
- Enric Hernández
- Horacio Moavro
- Javier Lattuf
- José Luis Rodríguez
- Norma Garza
- Carlos Espinosa
- Luis Carestía
- Erol

---

## Historial de Versiones

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| 1.0 | Febrero 2026 | Lanzamiento público inicial |
| 1.1 | Marzo 2026 | Encabezado Excel con título FILE, logo y fecha dinámica; columnas reordenadas; encabezados de torneo verticales; ELOD Actual resaltado en amarillo; nombres de torneos corregidos (Cuba Scrabble, Panamá, Castellón) |
