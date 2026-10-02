"""
Practica 1: Planificacion de rutas y cobertura (Busqueda) -- CasaRobot.

Ver practicas_IA_2026.md (seccion 5) y practica1_busqueda.tex para el
enunciado formal y la referencia de la API de HouseWorld/Robot (practica0).

Ejecuta el fichero tal cual para ver la casa generada y el robot colocado
en ella (nada de lo que hay que implementar se llama todavia):
    python3 practica1_enunciado.py --seed 42
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import sys
from collections import deque
from pathlib import Path
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from house_world import DIRECTIONS, HouseWorld, Robot  # noqa: E402

Coord = Tuple[int, int]
Action = str


# ------------------------------------------------------------------
# Utilidades genericas de busqueda (dadas: no son TODO)
# ------------------------------------------------------------------


class PriorityQueue:
    """Cola de prioridad minima. En caso de empate, respeta el orden de inserción (FIFO)."""

    def __init__(self) -> None:
        self._heap: List[Tuple[float, int, object]] = []
        self._counter = itertools.count()

    def push(self, item: object, priority: float) -> None:
        heapq.heappush(self._heap, (priority, next(self._counter), item))

    def pop(self) -> object:
        return heapq.heappop(self._heap)[2]

    def is_empty(self) -> bool:
        return not self._heap


class SearchProblem:
    """Interfaz comun a todos los problemas de búsqueda de esta práctica."""

    def get_start_state(self):
        raise NotImplementedError

    def is_goal_state(self, state) -> bool:
        raise NotImplementedError

    def get_successors(self, state) -> List[Tuple[object, Action, float]]:
        """Lista de (estado_sucesor, accion, coste_de_la_accion)."""
        raise NotImplementedError

    def get_cost_of_actions(self, actions: List[Action]) -> float:
        state = self.get_start_state()
        total = 0.0
        for action in actions:
            for succ, act, cost in self.get_successors(state):
                if act == action:
                    total += cost
                    state = succ
                    break
            else:
                raise ValueError(f"Acción no válida desde el estado {state}: {action!r}")
        return total


def null_heuristic(state, problem: Optional[SearchProblem] = None) -> float:
    return 0.0


# ------------------------------------------------------------------
# Preguntas 1-4: RobotPositionSearchProblem (dado) + 4 algoritmos (TODO)
# ------------------------------------------------------------------


class RobotPositionSearchProblem(SearchProblem):
    """
    Estado = posición (x, y) del robot en la CasaRobot. Ya resuelto: el
    objetivo de las preguntas 1-4 es implementar el ALGORITMO de búsqueda,
    no la formulación del problema.
    """

    def __init__(
        self,
        world: HouseWorld,
        start: Coord,
        goal: Coord,
        cost_fn: Optional[Callable[[Coord], float]] = None,
    ) -> None:
        if not world.is_free(*start):
            raise ValueError(f"Posición inicial no válida (muro): {start}")
        if not world.is_free(*goal):
            raise ValueError(f"Posición objetivo no válida (muro): {goal}")
        self.world = world
        self.start = start
        self.goal = goal
        self.cost_fn = cost_fn or (lambda pos: 1.0)

    def get_start_state(self) -> Coord:
        return self.start

    def is_goal_state(self, state: Coord) -> bool:
        return state == self.goal

    def get_successors(self, state: Coord) -> List[Tuple[Coord, Action, float]]:
        x, y = state
        successors = []
        for action, (dx, dy) in DIRECTIONS.items():
            nxt = (x + dx, y + dy)
            if self.world.is_free(*nxt):
                successors.append((nxt, action, self.cost_fn(nxt)))
        return successors


def room_terrain_cost(world: HouseWorld) -> Callable[[Coord], float]:
    """
    Función de coste para la Pregunta 3 (UCS): moverse dentro de una
    habitación cuesta 2 (hay que sortear muebles), moverse por un pasillo
    cuesta 1. Se da resuelta: lo que hay que implementar en la Q3 es el
    algoritmo uniform_cost_search, no esta función.
    """

    def cost(pos: Coord) -> float:
        return 2.0 if world.room_at(*pos) is not None else 1.0

    return cost


def manhattan_heuristic(state: Coord, problem: RobotPositionSearchProblem) -> float:
    gx, gy = problem.goal
    x, y = state
    return abs(x - gx) + abs(y - gy)


def depth_first_search(problem: SearchProblem) -> List[Action]:
    """
    Pregunta 1. Búsqueda en grafo (no reexpande estados ya visitados) con
    frontera LIFO (pila). Devuelve la lista de acciones desde el estado
    inicial hasta un estado objetivo (lista vacía si el inicial ya lo es).
    """
    raise NotImplementedError(
        "TODO: DFS con pila explícita (lista + append/pop) y un conjunto de visitados; "
        "marca un estado como visitado al SACARLO de la pila, no al meterlo"
    )


def breadth_first_search(problem: SearchProblem) -> List[Action]:
    """
    Pregunta 2. Búsqueda en grafo con frontera FIFO (cola). Devuelve el
    camino con menor número de pasos hasta un estado objetivo.
    """
    raise NotImplementedError(
        "TODO: BFS con collections.deque (append/popleft) y un conjunto de visitados"
    )


def uniform_cost_search(problem: SearchProblem) -> List[Action]:
    """
    Pregunta 3. Búsqueda en grafo con frontera de prioridad por coste
    acumulado. Devuelve el camino de coste mínimo hasta un estado objetivo.
    """
    raise NotImplementedError(
        "TODO: UCS con PriorityQueue (dada), priorizando por coste acumulado desde el inicio"
    )


def a_star_search(problem: SearchProblem, heuristic: Callable = null_heuristic) -> List[Action]:
    """
    Pregunta 4. Como UCS, pero ordenando la frontera por coste acumulado
    MÁS heurística. Con `heuristic=null_heuristic` debe comportarse
    exactamente como uniform_cost_search.
    """
    raise NotImplementedError(
        "TODO: A* con PriorityQueue (dada), priorizando por coste acumulado + heuristic(estado, problem)"
    )


# ------------------------------------------------------------------
# Pregunta 5-6: ronda de inspección (visitar todas las habitaciones)
# ------------------------------------------------------------------

VisitState = Tuple[Coord, FrozenSet[Coord]]


class InspectionRouteProblem(SearchProblem):
    """
    Pregunta 5 (TODO): visitar, en cualquier orden, todos los puntos de
    `checkpoints` partiendo de `start`, minimizando el número de pasos.

    Estado propuesto: (posición actual, conjunto de checkpoints
    pendientes). Si `start` es ya uno de los checkpoints, no debe contar
    como pendiente.
    """

    def __init__(self, world: HouseWorld, start: Coord, checkpoints: List[Coord]) -> None:
        self.world = world
        self.start = start
        self.checkpoints = frozenset(checkpoints)

    def get_start_state(self) -> VisitState:
        raise NotImplementedError("TODO: (start, checkpoints pendientes tras descontar start si aplica)")

    def is_goal_state(self, state: VisitState) -> bool:
        raise NotImplementedError("TODO: True si ya no quedan checkpoints pendientes")

    def get_successors(self, state: VisitState) -> List[Tuple[VisitState, Action, float]]:
        raise NotImplementedError(
            "TODO: para cada vecino libre, nuevo estado (vecino, pendientes sin el vecino si estaba), coste 1.0"
        )


def inspection_route_heuristic(state: VisitState, problem: InspectionRouteProblem) -> float:
    """Pregunta 6: heurística admisible para InspectionRouteProblem."""
    raise NotImplementedError(
        "TODO: 0.0 si no quedan pendientes; si no, distancia Manhattan al pendiente más lejano"
    )


# ------------------------------------------------------------------
# Pregunta 7: catalogar todos los objetos detectables
# ------------------------------------------------------------------


class CatalogingProblem(SearchProblem):
    """
    Pregunta 7 (TODO): visitar todas las celdas de `target_cells` (donde
    hay objetos detectados) partiendo de `start`, minimizando el número de
    pasos. Misma forma que InspectionRouteProblem, pero con los objetos de
    la casa como objetivos en vez de los centros de las habitaciones.
    """

    def __init__(self, world: HouseWorld, start: Coord, target_cells: List[Coord]) -> None:
        self.world = world
        self.start = start
        self.targets = frozenset(target_cells)

    def get_start_state(self) -> VisitState:
        raise NotImplementedError("TODO: igual patrón que InspectionRouteProblem, con self.targets")

    def is_goal_state(self, state: VisitState) -> bool:
        raise NotImplementedError("TODO: True si ya no quedan objetivos pendientes")

    def get_successors(self, state: VisitState) -> List[Tuple[VisitState, Action, float]]:
        raise NotImplementedError("TODO: igual patrón que InspectionRouteProblem")


def cataloging_heuristic(state: VisitState, problem: CatalogingProblem) -> float:
    """Heurística admisible para CatalogingProblem (mismo criterio que la Q6)."""
    raise NotImplementedError("TODO: 0.0 si no quedan pendientes; si no, distancia Manhattan al más lejano")


# ------------------------------------------------------------------
# Infraestructura de demo (dada: no es TODO)
# ------------------------------------------------------------------


class _CountingProblem(SearchProblem):
    """Envoltorio que cuenta llamadas a get_successors (nodos expandidos). Solo para la demo/stats."""

    def __init__(self, inner: SearchProblem) -> None:
        self._inner = inner
        self.expansions = 0

    def get_start_state(self):
        return self._inner.get_start_state()

    def is_goal_state(self, state) -> bool:
        return self._inner.is_goal_state(state)

    def get_successors(self, state):
        self.expansions += 1
        return self._inner.get_successors(state)

    def get_cost_of_actions(self, actions: List[Action]) -> float:
        return self._inner.get_cost_of_actions(actions)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _room_farthest_from(world: HouseWorld, start: Coord) -> Coord:
    return max(
        (room.center() for room in world.rooms),
        key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]),
    )


def _run(label: str, inner_problem: SearchProblem, algo: Callable[[SearchProblem], List[Action]]) -> List[Action]:
    counting = _CountingProblem(inner_problem)
    actions = algo(counting)
    cost = inner_problem.get_cost_of_actions(actions)
    print(f"  {label:<32s} pasos={len(actions):<4d} coste={cost:<6.1f} nodos_expandidos={counting.expansions}")
    return actions


def _actions_to_path(start: Coord, actions: List[Action]) -> List[Coord]:
    path = [start]
    x, y = start
    for action in actions:
        dx, dy = DIRECTIONS[action]
        x, y = x + dx, y + dy
        path.append((x, y))
    return path


def _show_plan(world: HouseWorld, start: Coord, actions: List[Action], *, use_color: bool, step: bool = False) -> None:
    """Muestra la ruta encontrada como traza sobre el mapa (siempre) y,
    si `step` es True, además la anima casilla a casilla."""
    path = _actions_to_path(start, actions)
    print(f"\nRuta encontrada ({len(actions)} pasos):")
    world.print(robot_pos=start, path=path, use_color=use_color)

    if not step:
        return
    robot = Robot(world, start=start)
    for step_num, action in enumerate(actions, start=1):
        ok = robot.move(action)
        estado = "" if ok else "  *** COLISIÓN INESPERADA ***"
        print(f"\nPaso {step_num}/{len(actions)}: {action}{estado}")
        world.print(robot_pos=robot.pos, path=path, use_color=use_color)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Práctica 1 (búsqueda) sobre una CasaRobot.")
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--height", type=int, default=14)
    parser.add_argument("--rooms", type=int, default=5)
    parser.add_argument("--density", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument(
        "--show",
        choices=["none", "q1", "q2", "q3", "q4", "q5", "q7", "all"],
        default="q7",
        help="qué plan(es) mostrar como ruta sobre el mapa al final (default: q7)",
    )
    parser.add_argument("--step", action="store_true", help="además de la ruta completa, anima --show casilla a casilla")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    use_color = not args.no_color

    world = HouseWorld(args.width, args.height, num_rooms=args.rooms, object_density=args.density, seed=args.seed)
    start = world.random_free_cell()
    goal = _room_farthest_from(world, start)

    print(f"CasaRobot: {world.width}x{world.height}, {len(world.rooms)} habitaciones, seed={args.seed}")
    world.print(robot_pos=start, use_color=use_color)
    print(f"\nInicio: {start}    Objetivo Q1-Q4: {goal}\n")

    uniform_problem = RobotPositionSearchProblem(world, start, goal)
    terrain_problem = RobotPositionSearchProblem(world, start, goal, cost_fn=room_terrain_cost(world))

    # ----------------------------------------------------------------
    # Paso 2: Q1 -- depth_first_search
    # ----------------------------------------------------------------
    # actions = _run("Q1 depth_first_search", uniform_problem, depth_first_search)
    # _show_plan(world, start, actions, use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 3: Q2 -- breadth_first_search
    # ----------------------------------------------------------------
    # actions = _run("Q2 breadth_first_search", uniform_problem, breadth_first_search)
    # _show_plan(world, start, actions, use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 4: Q3 -- uniform_cost_search (coste por terreno: room_terrain_cost, ya dado)
    # ----------------------------------------------------------------
    # actions = _run("Q3 uniform_cost_search", terrain_problem, uniform_cost_search)
    # _show_plan(world, start, actions, use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 5: Q4 -- a_star_search (con manhattan_heuristic, ya dada)
    # ----------------------------------------------------------------
    # actions = _run("Q4 a_star_search", uniform_problem, lambda p: a_star_search(p, manhattan_heuristic))
    # _show_plan(world, start, actions, use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 6: Q5+Q6 -- InspectionRouteProblem + inspection_route_heuristic
    # ----------------------------------------------------------------
    # checkpoints = [room.center() for room in world.rooms]
    # inspection_problem = InspectionRouteProblem(world, start, checkpoints)
    # actions = _run("Q5+Q6 inspection route", inspection_problem, lambda p: a_star_search(p, inspection_route_heuristic))
    # _show_plan(world, start, actions, use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 7: Q7 -- CatalogingProblem + cataloging_heuristic
    # ----------------------------------------------------------------
    # target_cells = sorted({pos for pos, _name in world.all_objects()})
    # if target_cells:
    #     cataloging_problem = CatalogingProblem(world, start, target_cells)
    #     actions = _run("Q7 cataloging", cataloging_problem, lambda p: a_star_search(p, cataloging_heuristic))
    #     _show_plan(world, start, actions, use_color=use_color, step=True)
    # else:
    #     print("  (esta casa no generó objetos con la densidad indicada)")


if __name__ == "__main__":  # pragma: no cover
    main()
