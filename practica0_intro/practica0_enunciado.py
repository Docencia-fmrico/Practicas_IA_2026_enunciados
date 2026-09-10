"""
Practica 0: Familiarizacion con CasaRobot.

Esta practica no introduce ningun algoritmo de IA nuevo: sirve para
aprender a usar la API de HouseWorld/Robot (common/house_world.py, que se
usara en las Practicas 1-4) escribiendo 6 funciones pequeñas. Consulta
practica0_intro.tex para la referencia completa de esa API y el desarrollo
paso a paso de esta practica.

Ejecuta el fichero tal cual para ver la casa generada y el robot colocado
en ella (nada de lo que hay que implementar se llama todavia):
    python3 practica0_enunciado.py --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from house_world import DIRECTIONS, HouseWorld, Robot, RoomType  # noqa: E402

Coord = Tuple[int, int]


def count_free_cells(world: HouseWorld) -> int:
    """Nº de celdas libres (no muro) de la casa. Usa HouseWorld.is_free."""
    raise NotImplementedError("TODO: contar las celdas (x,y) de la casa para las que world.is_free(x,y) es True")


def rooms_by_type(world: HouseWorld) -> Dict[RoomType, int]:
    """
    Nº de habitaciones de cada tipo. Solo incluye los tipos que aparecen
    al menos una vez (no hay entradas a 0). Usa HouseWorld.rooms.
    """
    raise NotImplementedError("TODO: recorrer world.rooms y contar cuántas hay de cada room_type")


def find_object(world: HouseWorld, name: str) -> Optional[Coord]:
    """
    Celda que contiene el objeto `name`, o None si no está en la casa.
    Si hay más de uno (puede pasar con dormitorio/baño duplicados), se
    devuelve el primero según el orden de HouseWorld.all_objects().
    """
    raise NotImplementedError("TODO: buscar `name` en world.all_objects() y devolver su celda")


def nearby_walls(robot: Robot) -> List[str]:
    """Direcciones (N/S/E/W), en orden alfabético, con un muro pegado al robot."""
    raise NotImplementedError("TODO: usar robot.wall_contact() y quedarse con las direcciones a True")


def step_towards(robot: Robot, goal: Coord) -> Optional[str]:
    """
    Mueve al robot UN paso hacia `goal`, sin planificar: de entre los
    vecinos libres de su posición actual, elige el que minimiza la
    distancia Manhattan a `goal` (empates: el primero en orden N,S,E,W) y
    ejecuta robot.move en esa dirección.

    Devuelve la acción ejecutada, o None si el robot ya está en `goal`
    (y por tanto no se mueve).
    """
    raise NotImplementedError(
        "TODO: mirar las 4 direcciones de DIRECTIONS (en ese orden), quedarte con la que lleva "
        "a una celda libre con menor distancia Manhattan a goal, y moverte con robot.move(...)"
    )


def execute_moves(robot: Robot, directions: List[str]) -> List[Coord]:
    """
    Ejecuta la secuencia `directions` sobre el robot, una a una, con
    robot.move. Devuelve la traza de posiciones REALES del robot tras cada
    intento: si una acción colisiona, el robot no se mueve y esa misma
    posición se repite en la traza (no se lanza ningún error).
    """
    raise NotImplementedError("TODO: llamar a robot.move(...) para cada dirección y anotar robot.pos tras cada una")


# ------------------------------------------------------------------
# Demo / CLI
# ------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Demo de la Práctica 0 (familiarización con CasaRobot).")
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--height", type=int, default=14)
    parser.add_argument("--rooms", type=int, default=5)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-color", action="store_true")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    use_color = not args.no_color

    world = HouseWorld(args.width, args.height, num_rooms=args.rooms, seed=args.seed)
    robot = Robot(world)

    print(f"CasaRobot: {world.width}x{world.height}, {len(world.rooms)} habitaciones, seed={args.seed}")
    world.print(robot_pos=robot.pos, use_color=use_color)
    print(world.legend(use_color=use_color))

    # ----------------------------------------------------------------
    # Paso 2: descomenta segun vayas implementando cada función.
    # ----------------------------------------------------------------

    # print(f"\n1) count_free_cells(world) = {count_free_cells(world)}")

    # print(f"\n2) rooms_by_type(world) =")
    # for room_type, count in rooms_by_type(world).items():
    #     print(f"   {room_type.value}: {count}")

    # objects = world.all_objects()
    # print(f"\n3) find_object(world, ...) — hay {len(objects)} objetos en la casa:")
    # if objects:
    #     sample_name = objects[0][1]
    #     print(f"   find_object(world, {sample_name!r}) = {find_object(world, sample_name)}")
    # print(f"   find_object(world, 'unicornio') = {find_object(world, 'unicornio')}")

    # print(f"\n4) nearby_walls(robot) en {robot.pos} = {nearby_walls(robot)}")

    # goal = world.rooms[-1].center()
    # print(f"\n5) step_towards(robot, {goal}) desde {robot.pos}:")
    # for _ in range(6):
    #     if robot.pos == goal:
    #         break
    #     action = step_towards(robot, goal)
    #     print(f"   acción={action}  ->  robot en {robot.pos}")

    # print("\n6) execute_moves(robot, ['N','N','N','N']) (puede chocar):")
    # trail = execute_moves(robot, ["N", "N", "N", "N"])
    # print(f"   traza de posiciones: {trail}")
    # world.print(robot_pos=robot.pos, use_color=use_color)


if __name__ == "__main__":  # pragma: no cover
    main()
