# 🛠️ Guía de instalación y ejecución

> 🌍 **Español** · [English](SETUP.en.md)

Guía paso a paso para poner en marcha este proyecto en **cualquier ordenador**,
desde cero. No hace falta saber de entornos virtuales: se explica todo.

Tiempo estimado: **5–10 minutos** (la mayoría es esperar a que instale).

---

## Índice

1. [Qué necesitas](#1-qué-necesitas)
2. [Instalar Python](#2-instalar-python)
3. [Descargar el proyecto](#3-descargar-el-proyecto)
4. [Crear el entorno virtual](#4-crear-el-entorno-virtual)
5. [Instalar las librerías](#5-instalar-las-librerías)
6. [Ejecutar el análisis](#6-ejecutar-el-análisis)
7. [Abrir la memoria (Jupyter)](#7-abrir-la-memoria-jupyter)
8. [Lanzar el demo interactivo (Streamlit)](#8-lanzar-el-demo-interactivo-streamlit)
9. [Problemas frecuentes](#9-problemas-frecuentes)
10. [Chuleta de comandos](#10-chuleta-de-comandos)

---

## 1. Qué necesitas

| | Mínimo | Comentario |
|---|---|---|
| **Python** | 3.10 o superior | Probado en 3.14 |
| **Espacio en disco** | ~500 MB | Casi todo son las librerías |
| **Conexión a internet** | Solo la primera vez | Para instalar y descargar los datos |

> **¿Sin internet?** El proyecto incluye los datos cacheados en
> `src/data/raw/`, así que funciona en modo offline. Ve al paso 6.

---

## 2. Instalar Python

### ¿Ya lo tienes?

Abre una terminal y escribe:

```bash
python --version
```

Si responde `Python 3.10.x` o superior, **salta al paso 3**.

<details>
<summary>¿Cómo abro una terminal?</summary>

* **Windows:** tecla `Windows` → escribe `powershell` → Enter
* **macOS:** `Cmd + Espacio` → escribe `terminal` → Enter
* **Linux:** `Ctrl + Alt + T`
</details>

### Si no lo tienes

**Windows**
1. Descarga desde [python.org/downloads](https://www.python.org/downloads/)
2. ⚠️ **MUY IMPORTANTE:** en la primera pantalla del instalador marca la
   casilla **"Add Python to PATH"**. Si no la marcas, la terminal no
   encontrará Python y nada de lo que sigue funcionará.
3. Pulsa *Install Now*

**macOS**
```bash
brew install python
```
(Si no tienes Homebrew: descarga desde [python.org](https://www.python.org/downloads/))

**Linux (Ubuntu/Debian)**
```bash
sudo apt update && sudo apt install python3 python3-venv python3-pip
```

---

## 3. Descargar el proyecto

**Opción A — con Git:**
```bash
git clone <URL-DEL-REPOSITORIO>
cd 0926_ds_thebridge_ft/2-Analytics/EDA/my-eda-project
```

**Opción B — sin Git:** descarga el ZIP desde GitHub, descomprímelo, y abre
una terminal **dentro de la carpeta `my-eda-project`**.

> ### ⚠️ El error más común de todos
> Todos los comandos de esta guía se ejecutan desde la carpeta
> **`my-eda-project`** (la que contiene `requirements.txt`). Compruébalo así:
>
> ```bash
> # Windows
> dir requirements.txt
> # macOS / Linux
> ls requirements.txt
> ```
>
> Si dice "no se encuentra el archivo", estás en la carpeta equivocada. Usa
> `cd` para moverte hasta donde está `requirements.txt`.

---

## 4. Crear el entorno virtual

Un **entorno virtual** es una carpeta donde se instalan las librerías de
*este* proyecto, sin tocar el Python de tu sistema ni el de otros proyectos.
Así nunca hay conflictos de versiones.

```bash
python -m venv .venv
```

Esto crea una carpeta oculta `.venv/`. Ahora hay que **activarla**:

**Windows (PowerShell)**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD)**
```cmd
.venv\Scripts\activate.bat
```

**Windows (Git Bash / MINGW64)**
```bash
source .venv/Scripts/activate
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

> ### ⚠️ Si usas Git Bash en Windows, lee esto
> Git Bash es un caso híbrido: shell de Unix, pero el entorno virtual lo ha
> creado Python para Windows. Por eso **no** funcionan ninguna de estas dos:
>
> ```bash
> .\.venv\Scripts\Activate.ps1   # ❌ en bash, \ escapa caracteres:
>                                #    se convierte en "..venvScriptsActivate.ps1"
> source .venv/bin/activate      # ❌ bin/ es la carpeta de macOS/Linux;
>                                #    en Windows es Scripts/
> ```
>
> La correcta combina las dos cosas: barras normales **y** `Scripts/`, con el
> fichero `activate` **sin extensión**:
>
> ```bash
> source .venv/Scripts/activate  # ✅
> ```

### ¿Cómo sé que funcionó?

El prompt de la terminal pasa a empezar por `(.venv)`:

```
(.venv) C:\...\my-eda-project>
```

Ese `(.venv)` es la señal de que todo va bien. **Tiene que estar ahí cada vez
que ejecutes algo.** Si cierras la terminal, hay que volver a activarlo.

<details>
<summary>⚠️ Windows: error "la ejecución de scripts está deshabilitada"</summary>

PowerShell bloquea scripts por defecto. Ejecuta esto **una sola vez** y vuelve
a intentar la activación:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Solo afecta a tu usuario y es la configuración recomendada por Microsoft para
desarrollo.
</details>

---

## 5. Instalar las librerías

Con el entorno activado (`(.venv)` visible):

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Tarda **2–5 minutos**. Verás mucho texto: es normal.

### Comprobar que todo está bien

```bash
python -c "import pandas, numpy, scipy, matplotlib, seaborn, yfinance, streamlit; print('Todo OK')"
```

Si imprime `Todo OK`, ya está listo. ✅

---

## 6. Ejecutar el análisis

Este es el comando principal: hace **todo** el pipeline (descarga, limpieza,
features, tests de hipótesis y los 4 gráficos).

```bash
python src/main.py
```

<details>
<summary>¿Qué verás por pantalla?</summary>

```
==============================================================================
STEP A | INGESTION, DATA HYGIENE AUDIT AND CALENDAR ALIGNMENT
==============================================================================
  [AUDIT] A1. raw Adj Close (union calendar)   shape=(991, 3)  d_rows= -
  ...
  >>> A blanket .dropna() would have destroyed 35 rows (3.5% of the sample).
  ...
VERDICTS | WHAT THE DATA SAYS ABOUT EACH PRE-STATED HYPOTHESIS
  H1 ... NOT SUPPORTED (data points the other way)
  H2 ... SUPPORTED (direction + statistically significant)
  H3 ... SUPPORTED (direction + statistically significant)
```
</details>

### Variantes útiles

| Comando | Para qué sirve |
|---|---|
| `python src/main.py` | Descarga datos frescos de Yahoo Finance |
| `python src/main.py --offline` | **Sin internet.** Usa la caché de `src/data/raw/` |
| `python src/main.py --no-charts` | Solo tablas, sin generar imágenes (más rápido) |

### Qué genera

```
reports/figures/     4 gráficos PNG a 300 DPI (los del PowerPoint)
reports/tables/      16 tablas en markdown + el ledger de auditoría
src/data/processed/  4 CSV listos para análisis
src/data/raw/        la descarga original cacheada
```

> 💡 **Para la presentación:** ejecuta `python src/main.py` el día anterior.
> Después usa siempre `--offline`, y así no dependes del wifi de la sala.

---

## 7. Abrir la memoria (Jupyter)

La memoria (`src/memoria.ipynb`) **ya viene ejecutada**, con todos sus
resultados guardados dentro. Puedes leerla directamente en GitHub sin instalar
nada.

Para abrirla y poder reejecutarla:

```bash
jupyter lab src/memoria.ipynb
```

### Si usas VS Code

1. Abre `src/memoria.ipynb`
2. Arriba a la derecha, pulsa el **selector de kernel**
3. Elige *Python Environments* → el que ponga **`.venv`**

> ⚠️ Si eliges el Python del sistema en lugar del `.venv`, **todas las celdas
> fallarán** con `ModuleNotFoundError: No module named 'pandas'`. Es el fallo
> número uno con los notebooks: las librerías están en el entorno virtual, no
> en el Python global.

---

## 8. Lanzar el demo interactivo (Streamlit)

```bash
streamlit run src/app.py
```

Se abre solo en el navegador, en `http://localhost:8501`.

### Qué tiene

| Pestaña | Contenido |
|---|---|
| 📊 **Resumen** | KPIs y el veredicto de las 3 hipótesis |
| 📈 **H1 · Rendimiento** | Gráfico de crecimiento + tests de alpha |
| ⚠️ **H2 · Riesgo** | Distribuciones + umbral de desplome **ajustable en vivo** |
| 🔊 **H3 · Liquidez** | Estacionalidad del volumen, Zara vs Temu |
| 🔗 **Síntesis** | Matrices de correlación por régimen |
| 🧹 **Higiene de datos** | El ledger de auditoría y las decisiones de limpieza |

### Dos trucos para la defensa

* **El control de robustez:** marca *«Solo sesiones reales»* en la barra
  lateral. Excluye los días rellenados por forward-fill y la conclusión de H2
  no cambia — es la respuesta a *«¿y si tu limpieza de datos está creando el
  resultado?»*.
* **El umbral de desplome:** llévalo a −10%. Zara se queda en **0 sesiones**
  y Temu en **12**. Es la diapositiva que se explica sola.

> **Para parar la app:** `Ctrl + C` en la terminal.

> ⚠️ La app **solo lee** los resultados del pipeline, no los calcula. Si da el
> error *«No hay datos procesados todavía»*, ejecuta antes el paso 6.

---

## 9. Problemas frecuentes

<details>
<summary><b>"python no se reconoce como un comando"</b> (Windows)</summary>

No marcaste *"Add Python to PATH"* al instalar. Dos soluciones:
* Reinstala Python marcando esa casilla, **o**
* Usa `py` en lugar de `python` en todos los comandos.
</details>

<details>
<summary><b>"ModuleNotFoundError: No module named 'pandas'"</b></summary>

El entorno virtual no está activado. Mira si el prompt empieza por `(.venv)`.
Si no, vuelve al **paso 4** y actívalo.

En un notebook de VS Code, significa que has elegido el kernel equivocado:
paso 7.
</details>

<details>
<summary><b>"No module named 'tabulate'" o similar</b></summary>

Faltan librerías. Con el entorno activado:
```bash
python -m pip install -r requirements.txt
```
</details>

<details>
<summary><b>La descarga de Yahoo Finance falla o va vacía</b></summary>

Pasa: es una API pública y gratuita, a veces limita las peticiones. Usa la
caché incluida:
```bash
python src/main.py --offline
```
Si el error menciona `database is locked`, es el caché SQLite de `yfinance`.
El proyecto ya descarga en serie (`threads=False`) para evitarlo; basta con
reintentar.
</details>

<details>
<summary><b>"Port 8501 is already in use"</b> (Streamlit)</summary>

Ya hay una app corriendo. Ciérrala con `Ctrl + C`, o usa otro puerto:
```bash
streamlit run src/app.py --server.port 8502
```
</details>

<details>
<summary><b>Los gráficos salen con cuadrados en vez de texto</b></summary>

Falta la fuente *Segoe UI*. El código ya cae en *DejaVu Sans* como
alternativa, pero si ves cuadraditos, borra la caché de matplotlib:
```bash
python -c "import matplotlib; import shutil; shutil.rmtree(matplotlib.get_cachedir())"
```
</details>

<details>
<summary><b>Quiero empezar de cero</b></summary>

Borra la carpeta `.venv/` y repite desde el paso 4. No se pierde nada: el
código y los datos están fuera del entorno.
</details>

---

## 10. Chuleta de comandos

```bash
# --- PRIMERA VEZ (solo una vez) ---------------------------------
python -m venv .venv                       # crear el entorno
.\.venv\Scripts\Activate.ps1               # activar (Windows PowerShell)
source .venv/Scripts/activate              # activar (Windows Git Bash)
source .venv/bin/activate                  # activar (macOS / Linux)
python -m pip install -r requirements.txt  # instalar librerías

# --- CADA VEZ QUE ABRES UNA TERMINAL NUEVA ----------------------
.\.venv\Scripts\Activate.ps1               # Windows PowerShell
source .venv/Scripts/activate              # Windows Git Bash
source .venv/bin/activate                  # macOS / Linux

# --- EJECUTAR EL PROYECTO ---------------------------------------
python src/main.py                         # análisis completo (con internet)
python src/main.py --offline               # análisis desde la caché
streamlit run src/app.py                   # demo interactivo
jupyter lab src/memoria.ipynb              # abrir la memoria
python -m pytest tests/ -v                 # verificar que todo funciona
```

---

¿Algo no funciona? Abre una *issue* en el repositorio indicando tu sistema
operativo, tu versión de Python (`python --version`) y el mensaje de error
completo.
