# Prácticas de Inteligencia Artificial — Curso 2026/2027

Prácticas de la asignatura **Inteligencia Artificial**, 3º curso del
**Grado en Ingeniería en Robótica Software** (URJC).

- **Francisco Martín Rico** — francisco.rico@urjc.es
- **Esther Aguado González** — esther.aguado@urjc.es

## Descripción

Todas las prácticas comparten un mismo escenario, **CasaRobot**: una
casa generada aleatoriamente (habitaciones con paredes reales,
pasillos, objetos típicos por tipo de habitación) sobre la que un
robot se mueve, detecta objetos y colisiona contra las paredes. Cada
práctica reutiliza este mismo escenario para trabajar un tipo de
razonamiento distinto:

| Práctica | Tema | Qué hace el robot |
|---|---|---|
| [`practica0_intro/`](practica0_intro/) | Familiarización con la API | Aprender a usar `HouseWorld`/`Robot` (no puntúa como las demás, es material de preparación) |
| [`practica1_busqueda/`](practica1_busqueda/) | Búsqueda (DFS/BFS/UCS/A\*) | Planifica rutas y rondas de inspección/catalogación |
| [`practica2_logica/`](practica2_logica/) | Lógica proposicional y SAT | Planifica por inferencia lógica en vez de búsqueda, con un solver SAT (DPLL) propio |
| [`practica3_bayes/`](practica3_bayes/) | Redes bayesianas | Infiere en qué tipo de habitación está a partir de un clasificador de objetos ruidoso |
| [`practica4_hmm/`](practica4_hmm/) | Modelos ocultos de Markov | Se localiza dentro de la casa combinando movimiento incierto y un sensor de contacto con paredes ruidoso |

Cada práctica trae su enunciado en PDF (`practicaN_*.pdf`) y el código
de partida (`practicaN_enunciado.py`), con los métodos a implementar
marcados con `raise NotImplementedError(...)`.

## Estructura del repositorio

```
practicas_IA/
├── common/                    Escenario compartido (HouseWorld, Robot) — dado, no se toca
│   ├── house_world.py
│   ├── test_house_world.py
│   └── casa_intro.pdf         Introducción al escenario CasaRobot
├── practica0_intro/
│   ├── practica0_enunciado.py     código de partida (renómbralo a practica0.py)
│   └── practica0_intro.pdf
├── practica1_busqueda/        (mismos 2 ficheros: practica1_enunciado.py, practica1_busqueda.pdf)
├── practica2_logica/          (+ sat_solver.py y test_sat_solver.py: solver SAT propio, dado)
├── practica3_bayes/           (mismo esquema)
└── practica4_hmm/             (mismo esquema)
```

## Cómo trabajar cada práctica

1. Copia `practicaN_enunciado.py` a `practicaN.py` dentro de la misma
   carpeta (ese es el nombre con el que se entrega).
2. Completa los métodos marcados con `raise NotImplementedError(...)`,
   siguiendo el enunciado en PDF.
3. Ejecuta el fichero directamente para ver una CasaRobot generada y
   una demo de la práctica en la terminal. Esto requiere el entorno de
   pixi activo (ver más abajo), así que primero entra con `pixi shell`:

   ```bash
   pixi shell
   python3 practica1_busqueda/practica1.py --seed 42
   ```

   Todos los scripts aceptan `--seed`, `--no-color` (logs sin ANSI), y
   opciones propias de cada práctica (`--help` para verlas todas).

## Pixi: lo que necesitas para trabajar

Este repositorio se gestiona con [pixi](https://pixi.sh). No hace
falta instalar Python ni nada más a mano: pixi crea el entorno a
partir de `pixi.toml`/`pixi.lock`.

**Instalar pixi** (una sola vez, si no lo tienes ya):

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

**Instalar el entorno del repositorio** (desde la raíz del repo):

```bash
pixi install
```

Todo lo que no sea `pixi run <tarea>` (es decir, cualquier `python3`,
`pytest`, `flake8`... que lances tú directamente) necesita el entorno
de pixi activo. Entra en él una vez por sesión de terminal con:

```bash
pixi shell
```

y a partir de ahí ya tienes `python3`, `pytest`, `coverage` y `flake8`
disponibles en ese mismo shell (para salir, `exit`).

**Comandos disponibles** (`pixi run <tarea>`, estos sí funcionan sin
`pixi shell` porque ya ejecutan dentro del entorno):

| Tarea | Qué hace |
|---|---|
| `pixi run lint` | `flake8` sobre todo el repositorio |
| `pixi run test-common` | Tests de `common/house_world.py` (con cobertura) |
| `pixi run test-sat-solver` | Tests de `practica2_logica/sat_solver.py` (con cobertura) |
| `pixi run test` | Los dos anteriores juntos |
| `pixi run ci` | Todo lo anterior (`lint` + `test`), lo mismo que ejecuta el CI |

Ejemplo típico mientras trabajas en una práctica:

```bash
pixi install                    # solo la primera vez
pixi shell                      # una vez por sesión de terminal
python3 practica1_busqueda/practica1.py --seed 42
exit                            # sales del entorno de pixi
pixi run lint                   # revisa el estilo antes de entregar
```

### Tests del escenario común y del solver SAT

`common/house_world.py` y `practica2_logica/sat_solver.py` son
infraestructura dada (no se entregan), con su propia batería `pytest`.
Necesita el entorno de pixi activo:

```bash
pixi shell
cd common               # o cd practica2_logica
python3 -m pytest -q
python3 -m coverage run -m pytest -q && python3 -m coverage report -m
```

## Integración continua

En cada push/pull request a `main`, [GitHub Actions](.github/workflows/ci.yml)
ejecuta automáticamente `lint` y los tests de `common`/`sat_solver.py`.

## Requisitos

Solo **librería estándar de Python** (3.10 o superior) — no hace falta
instalar ninguna dependencia adicional en tu código. Esto incluye
deliberadamente el solver SAT de la Práctica 2 (implementación propia,
sin `pycosat` ni similares). Las dependencias de desarrollo (`pytest`,
`coverage`, `flake8`) las gestiona pixi por ti.
