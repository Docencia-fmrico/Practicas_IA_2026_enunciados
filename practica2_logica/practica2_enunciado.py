"""
Practica 2: El robot logico (Logica proposicional y SAT) -- CasaRobot.

Ver practicas_IA_2026.md (seccion 6) y practica2_logica.tex para el
enunciado formal. La infraestructura de logica proposicional (Expr,
to_cnf, el solver SAT find_model) esta en sat_solver.py, dada por
completo -- no hay que tocarla, pero conviene leerla para entender qué
hay disponible.

Ejecuta el fichero tal cual para ver la casa generada y el robot
colocado en ella (nada de lo que hay que implementar se llama todavia):
    python3 practica2_enunciado.py --seed 42
"""

from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sat_solver import Clause, Expr, Literal, Model, find_model, negate_literal, pl_true, symbols, to_cnf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from house_world import DIRECTIONS, HouseWorld, Robot  # noqa: E402

Coord = Tuple[int, int]


# ------------------------------------------------------------------
# Pregunta 1: calentamiento con Expr/CNF (ver sat_solver.py)
# ------------------------------------------------------------------


def sentence1() -> Expr:
    """A ∨ B; ¬A ⇔ (¬B ∨ C); ¬A ∨ ¬B ∨ C -- las tres, sin simplificar, en ese orden."""
    raise NotImplementedError("TODO: construir con Expr y los operadores &, |, ~, %")


def sentence2() -> Expr:
    """C ⇔ (B∨D); A⇒(¬B∧¬D); ¬(B∧¬C)⇒A; ¬D⇒C -- sin simplificar, en ese orden."""
    raise NotImplementedError("TODO: construir con Expr y los operadores &, |, ~, >>, %")


def sentence3() -> Expr:
    """
    RobotAlive_1 ⇔ (RobotAlive_0 ∧ ¬RobotApagado_0) ∨ (¬RobotAlive_0 ∧ RobotEncendido_0);
    en el instante 0 el robot no puede estar vivo y encenderse a la vez;
    el robot se enciende en el instante 0. Conjuncion de las tres, sin simplificar.
    """
    raise NotImplementedError(
        "TODO: usa symbols('RobotAlive_0','RobotAlive_1','RobotEncendido_0','RobotApagado_0')"
    )


def entails(premise: Expr, conclusion: Expr) -> bool:
    """True syss `premise` implica `conclusion` (premise ⊨ conclusion)."""
    raise NotImplementedError(
        "TODO: premise entails conclusion syss (premise & ~conclusion) es insatisfacible "
        "-- usa to_cnf(...) y find_model(...)"
    )


def pl_true_inverse(assignments: Model, inverse_statement: Expr) -> bool:
    """True syss (not inverse_statement) es verdad bajo `assignments`."""
    raise NotImplementedError("TODO: usa pl_true(inverse_statement, assignments)")


# ------------------------------------------------------------------
# Pregunta 2: bloques CNF reutilizables (construccion directa, sin to_cnf)
# ------------------------------------------------------------------


def at_least_one(literals: Sequence[Literal]) -> List[Clause]:
    """CNF que es verdad syss al menos uno de `literals` es verdad."""
    raise NotImplementedError("TODO: una unica clausula con todos los literales")


def at_most_one(literals: Sequence[Literal]) -> List[Clause]:
    """CNF que es verdad syss como mucho uno de `literals` es verdad."""
    raise NotImplementedError(
        "TODO: una clausula [negate_literal(a), negate_literal(b)] por cada pareja de literals "
        "(itertools.combinations)"
    )


def exactly_one(literals: Sequence[Literal]) -> List[Clause]:
    """CNF que es verdad syss exactamente uno de `literals` es verdad."""
    raise NotImplementedError("TODO: at_least_one(literals) + at_most_one(literals)")


# ------------------------------------------------------------------
# RobotPhysics: simbolos (dados) y Pregunta 3 (axiomas)
# ------------------------------------------------------------------


def at_symbol(x: int, y: int, t: int) -> str:
    return f"At_{x}_{y}_{t}"


def action_symbol(action: str, t: int) -> str:
    return f"Act_{action}_{t}"


def blocked_symbol(direction: str, t: int) -> str:
    return f"Blocked_{direction}_{t}"


def detected_symbol(x: int, y: int, t: int) -> str:
    return f"Detected_{x}_{y}_{t}"


def _successor_causes(x: int, y: int, t: int, world: HouseWorld) -> List[Tuple[Literal, Literal]]:
    """
    Dado (parte de la infraestructura de la Pregunta 3): para cada
    direccion por la que se pudo llegar a (x,y), el par (simbolo de
    posicion previa, simbolo de accion previa) que lo causaria.
    """
    causes = []
    for action, (dx, dy) in DIRECTIONS.items():
        px, py = x - dx, y - dy
        if world.is_free(px, py):
            causes.append((at_symbol(px, py, t - 1), action_symbol(action, t - 1)))
    return causes


def robot_successor_axiom_single(x: int, y: int, t: int, world: HouseWorld) -> List[Clause]:
    """
    Pregunta 3a. Clausulas de la equivalencia:
        At(x,y,t) <=> OR_{(pos,accion) en _successor_causes(x,y,t,world)} (pos AND accion)

    El robot se mueve siempre (no hay "quedarse quieto" en este modelo,
    igual que en la Practica 1): si no hay ninguna causa posible (celda
    aislada), At(x,y,t) debe ser falso.

    Cada causa es una conjuncion (pos AND accion); en vez de distribuir
    la disyuncion de conjunciones directamente en CNF (crecimiento
    exponencial en el numero de causas), introduce una variable auxiliar
    por causa: aux_i <=> pos_i AND accion_i (3 clausulas cada una), y
    luego At(x,y,t) <=> OR(aux_i) (lineal en el numero de causas).
    """
    raise NotImplementedError(
        "TODO: usa _successor_causes(x,y,t,world) (dado) y el patron de variables auxiliares "
        "descrito arriba para codificar la equivalencia como clausulas"
    )


def robot_physics_axioms(
    t: int,
    world: HouseWorld,
    free_coords: List[Coord],
    *,
    sensor_model=None,
    include_successor: bool = True,
) -> List[Clause]:
    """
    Pregunta 3b. Clausulas de fisica del robot en el instante t:
      - el robot esta en exactamente una de `free_coords` en el instante t.
      - si `sensor_model` no es None: añade sensor_model(t, world, free_coords).
      - si `include_successor` y t >= 1: añade robot_successor_axiom_single
        para cada celda de `free_coords`.
    """
    raise NotImplementedError(
        "TODO: exactly_one(...) sobre [at_symbol(x,y,t) for x,y in free_coords], "
        "más sensor_model(t, world, free_coords) si se ha dado, "
        "más robot_successor_axiom_single(x,y,t,world) para cada celda si include_successor y t>=1"
    )


def wall_contact_sensor_model(t: int, world: HouseWorld, free_coords: List[Coord]) -> List[Clause]:
    """
    Dado: modelo de sensor de contacto con paredes (igual idea que
    Blocked_W en las diapositivas de PacPhysics, pero aqui Wall(x,y) es
    conocido de antemano -- no hace falta una variable proposicional para
    ello, basta con mirar world.is_wall). Para cada direccion d:
        Blocked_d(t) <=> OR_{c libre : hay muro al lado de c en direccion d} At(c,t)
    """
    clauses: List[Clause] = []
    for direction, (dx, dy) in DIRECTIONS.items():
        b = blocked_symbol(direction, t)
        causes = [at_symbol(x, y, t) for x, y in free_coords if world.is_wall(x + dx, y + dy)]
        if not causes:
            clauses.append([f"-{b}"])
            continue
        clauses.append([f"-{b}"] + causes)
        for c in causes:
            clauses.append([b, f"-{c}"])
    return clauses


def check_position_satisfiability(
    world: HouseWorld,
    pos0: Coord,
    action0: str,
    query_pos: Coord,
) -> Tuple[Optional[Model], Optional[Model]]:
    """
    Pregunta 3c. Dada la posicion en t=0 y la accion tomada en t=0, ¿es
    posible que el robot este en `query_pos` en t=1? ¿Es posible que NO
    lo este? Sin modelo de sensor (fisica pura, el mapa ya se conoce
    entero). Devuelve (modelo_si_esta, modelo_si_no_esta); cualquiera de
    los dos puede ser None si esa posibilidad esta descartada.

    `action0` se asume una accion legal desde `pos0` (no choca con un
    muro): este modelo no tiene accion "quedarse quieto" (igual que la
    Practica 1), asi que forzar una accion ilegal deja la KB sin ningun
    At(*,1) posible y ambas respuestas salen None -- no es un error,
    es la forma en que el modelo señala que el escenario planteado es
    contradictorio.
    """
    raise NotImplementedError(
        "TODO: construir clauses = robot_physics_axioms(0,...,include_successor=False) "
        "+ exactly_one de acciones en t=0 + [at_symbol(*pos0,0)] + [action_symbol(action0,0)] "
        "+ robot_physics_axioms(1,...,include_successor=True), "
        "y llamar find_model dos veces: una añadiendo [at_symbol(*query_pos,1)] "
        "y otra añadiendo [f'-{at_symbol(*query_pos,1)}']"
    )


# ------------------------------------------------------------------
# Extraccion de acciones desde un modelo (dado, compartido por Q4 y Q5)
# ------------------------------------------------------------------


def _extract_actions(model: Model, t_max: int) -> List[str]:
    actions: List[str] = []
    for t in range(t_max):
        for a in DIRECTIONS:
            if model.get(action_symbol(a, t)):
                actions.append(a)
                break
    return actions


# ------------------------------------------------------------------
# Pregunta 4: planificacion por SAT hasta un punto objetivo
# ------------------------------------------------------------------


def robot_position_logic_plan(world: HouseWorld, start: Coord, goal: Coord, max_t: int = 50) -> List[str]:
    """
    Pregunta 4. Analogo logico de la Practica 1 (busqueda): en vez de
    explorar un arbol de busqueda, se construye una KB proposicional
    para T = 0, 1, 2, ... y se pregunta al solver si es satisfacible que
    el robot llegue a `goal` en el paso T. La primera vez que lo sea, se
    extrae la secuencia de acciones del modelo devuelto (usa
    _extract_actions, dado).
    """
    raise NotImplementedError(
        "TODO: para t_max en range(max_t+1): construir la KB (posicion inicial en t=0, "
        "robot_physics_axioms para cada instante 0..t_max, exactly_one de acciones para "
        "cada instante 0..t_max-1, y el objetivo at_symbol(*goal, t_max)); "
        "si find_model(kb) no es None, devuelve _extract_actions(model, t_max); "
        "si no, sigue con el siguiente t_max"
    )


# ------------------------------------------------------------------
# Pregunta 5: planificacion por SAT para catalogar objetos
# ------------------------------------------------------------------


def catalog_logic_plan(world: HouseWorld, start: Coord, targets: List[Coord], max_t: int = 50) -> List[str]:
    """
    Pregunta 5. Como la Pregunta 4, pero el objetivo es haber detectado
    todos los objetos de `targets` en algun momento hasta T (no llegar a
    un unico punto). Se necesita una variable Detected(x,y,t) por cada
    objetivo, con su propio axioma de sucesor:
        Detected(x,y,t) <=> Detected(x,y,t-1) OR At(x,y,t)
    (ojo: el segundo termino es At EN EL INSTANTE ACTUAL t, no t-1 -- la
    deteccion se activa el mismo instante en que se llega a la celda, no
    un paso despues. Una vez detectado, se queda detectado; no hace
    falta variable auxiliar aqui -- a diferencia de la Q3a, es una
    disyuncion simple de 2 terminos, se puede codificar directamente en
    3 clausulas.)
    Detected(x,y,0) es falso salvo que (x,y) == start.
    """
    raise NotImplementedError(
        "TODO: igual que robot_position_logic_plan, pero ademas añadiendo a la KB, para cada "
        "objetivo y cada instante >=1, las 3 clausulas del axioma de sucesor de Detected de "
        "arriba; el objetivo final es la conjuncion de detected_symbol(x,y,t_max) para todos "
        "los (x,y) en targets (una clausula unitaria por cada uno)"
    )


# ------------------------------------------------------------------
# Pregunta 6 (opcional): localizacion por eliminacion logica
# ------------------------------------------------------------------


def localize_by_elimination(
    world: HouseWorld,
    action_history: List[str],
    observation_history: List[Dict[str, bool]],
) -> Set[Coord]:
    """
    Pregunta 6 (opcional). Dada una secuencia de acciones ya ejecutadas y,
    para cada instante, la lectura del sensor de contacto con paredes
    (wall_contact_sensor_model), con posicion inicial DESCONOCIDA: ¿en
    que celdas podria estar el robot ahora, segun lo que la KB permite
    descartar? (`len(observation_history) == len(action_history) + 1`:
    una observacion antes de la primera accion y una tras cada accion.)

    Devuelve el conjunto de celdas todavia consistentes con la KB.
    """
    raise NotImplementedError(
        "TODO: para cada celda candidata (x,y) libre, construir la KB completa (fisica en "
        "cada instante 0..T con sensor_model=wall_contact_sensor_model, las acciones tomadas, "
        "las observaciones percibidas como literales fijos, y at_symbol(x,y,0) como posicion "
        "de partida) y comprobar con find_model si es satisfacible; quedarse con las celdas "
        "para las que lo es"
    )


# ------------------------------------------------------------------
# Infraestructura de demo (dada: no es TODO)
# ------------------------------------------------------------------


def _free_coords(world: HouseWorld) -> List[Coord]:
    return [(x, y) for y in range(1, world.height + 1) for x in range(1, world.width + 1) if world.is_free(x, y)]


def _actions_to_path(start: Coord, actions: List[str]) -> List[Coord]:
    path = [start]
    x, y = start
    for action in actions:
        dx, dy = DIRECTIONS[action]
        x, y = x + dx, y + dy
        path.append((x, y))
    return path


def _replay(world: HouseWorld, start: Coord, actions: List[str]) -> Coord:
    robot = Robot(world, start=start)
    for action in actions:
        if not robot.move(action):
            raise RuntimeError(f"Colisión ejecutando el plan en {robot.pos} con la acción {action!r}")
    return robot.pos


def _room_farthest_from(world: HouseWorld, start: Coord) -> Coord:
    return max(
        (room.center() for room in world.rooms),
        key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]),
    )


def _bfs_distance(world: HouseWorld, start: Coord, goal: Coord) -> int:
    """Distancia real (no Manhattan) para elegir objetivos de demo cercanos. No usa SAT."""
    from collections import deque

    frontier = deque([(start, 0)])
    seen = {start}
    while frontier:
        pos, dist = frontier.popleft()
        if pos == goal:
            return dist
        for neighbor in world.neighbors(*pos):
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append((neighbor, dist + 1))
    return 10**9  # pragma: no cover -- inalcanzable en una CasaRobot conexa


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Práctica 2 (lógica/SAT) sobre una CasaRobot.")
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--height", type=int, default=11)
    parser.add_argument("--rooms", type=int, default=4)
    parser.add_argument("--density", type=float, default=0.3, help="densidad de objetos (baja por defecto: Q5 es cara)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-color", action="store_true")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    use_color = not args.no_color

    world = HouseWorld(args.width, args.height, num_rooms=args.rooms, object_density=args.density, seed=args.seed)
    start = world.random_free_cell()
    goal = _room_farthest_from(world, start)

    print(f"CasaRobot: {world.width}x{world.height}, {len(world.rooms)} habitaciones, seed={args.seed}")
    world.print(robot_pos=start, use_color=use_color)
    print(f"\nInicio: {start}    Objetivo Q4: {goal}\n")

    # ----------------------------------------------------------------
    # Paso 2: Q1 -- sentence1/2/3, entails, pl_true_inverse
    # ----------------------------------------------------------------
    # print("Pregunta 1 (calentamiento):")
    # print(f"  sentence1 |= (A|B)?  {entails(sentence1(), Expr('A') | Expr('B'))}")

    # ----------------------------------------------------------------
    # Paso 3: Q2 -- at_least_one, at_most_one, exactly_one
    # ----------------------------------------------------------------
    # print("\nPregunta 2 (exactly_one) con 3 literales, sanity check:")
    # model = find_model(exactly_one(["A", "B", "C"]) + [["A"]])
    # print(f"  exactly_one([A,B,C]) & A -> B={model['B']}, C={model['C']} (deben ser False)")

    # ----------------------------------------------------------------
    # Paso 4: Q3 -- robot_successor_axiom_single, robot_physics_axioms,
    # check_position_satisfiability
    # ----------------------------------------------------------------
    # legal_direction = next(
    #     d for d, (dx, dy) in DIRECTIONS.items() if world.is_free(start[0] + dx, start[1] + dy)
    # )
    # dx, dy = DIRECTIONS[legal_direction]
    # true_neighbor = (start[0] + dx, start[1] + dy)
    # yes_model, _ = check_position_satisfiability(world, start, legal_direction, true_neighbor)
    # print(f"\n¿posible estar en {true_neighbor} tras mover {legal_direction} desde {start}? "
    #       f"{yes_model is not None} (debe ser True)")

    # ----------------------------------------------------------------
    # Paso 5: Q4 -- robot_position_logic_plan
    # ----------------------------------------------------------------
    # t0 = time.time()
    # actions_q4 = robot_position_logic_plan(world, start, goal)
    # end_pos = _replay(world, start, actions_q4)
    # print(f"\nQ4: {len(actions_q4)} pasos en {time.time()-t0:.2f}s -- termina en {end_pos} "
    #       f"(objetivo {goal}): {'OK' if end_pos == goal else 'FALLO'}")
    # world.print(robot_pos=start, path=_actions_to_path(start, actions_q4), use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 6: Q5 -- catalog_logic_plan (con pocos objetivos: ver nota de
    # rendimiento en el .tex sobre por qué esto puede ser lento)
    # ----------------------------------------------------------------
    # all_targets = sorted({pos for pos, _name in world.all_objects()})
    # target_cells = sorted(all_targets, key=lambda c: _bfs_distance(world, start, c))[:2]
    # if target_cells:
    #     t0 = time.time()
    #     actions_q5 = catalog_logic_plan(world, start, target_cells, max_t=30)
    #     print(f"\nQ5: {len(actions_q5)} pasos en {time.time()-t0:.2f}s")
    #     world.print(robot_pos=start, path=_actions_to_path(start, actions_q5), use_color=use_color)

    # ----------------------------------------------------------------
    # Paso 7 (opcional): Q6 -- localize_by_elimination
    # ----------------------------------------------------------------
    # import random
    # robot = Robot(world, start=start)
    # rng = random.Random(args.seed)
    # action_history, observation_history = [], [robot.wall_contact()]
    # for _ in range(5):
    #     legal = [d for d in DIRECTIONS if world.is_free(robot.x + DIRECTIONS[d][0], robot.y + DIRECTIONS[d][1])]
    #     a = rng.choice(legal)
    #     robot.move(a)
    #     action_history.append(a)
    #     observation_history.append(robot.wall_contact())
    # candidates = localize_by_elimination(world, action_history, observation_history)
    # print(f"\nQ6: posición real {start}, candidatas tras {len(action_history)} pasos: {sorted(candidates)}")


if __name__ == "__main__":  # pragma: no cover
    main()
