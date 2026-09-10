"""
Practica 3: ¿Que habitacion es esta? (Redes Bayesianas) -- CasaRobot.

Ver practicas_IA_2026.md (seccion 7) y practica3_bayes.tex para el
enunciado formal.

El robot detecta objetos con un clasificador ruidoso (puede fallar al
detectar un objeto presente, o "ver" uno que no esta) y debe inferir el
tipo de habitacion en la que esta a partir de esas detecciones ruidosas
y de la tabla de afinidad objeto<->habitacion de CasaRobot
(OBJECT_CATALOG). Es una red bayesiana "naive Bayes": una variable
oculta RoomType, y una variable booleana Detected_<objeto> por cada
tipo de objeto del catalogo completo, condicionalmente independientes
dado RoomType.

Ejecuta el fichero tal cual para ver la casa generada (nada de lo que
hay que implementar se llama todavia):
    python3 practica3_enunciado.py --seed 42
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from house_world import OBJECT_CATALOG, HouseWorld, Room, RoomType  # noqa: E402

Assignment = Tuple[Any, ...]


# ------------------------------------------------------------------
# Factor: dado, no es TODO
# ------------------------------------------------------------------


class Factor:
    """
    Factor de una red bayesiana: una tabla de probabilidad sobre un
    conjunto de variables. `variables` fija el orden en que se leen las
    tuplas de `table`. `domains` es un diccionario variable->valores
    posibles, COMPARTIDO por todos los factores de una misma red (no
    solo contiene las variables de este factor).
    """

    def __init__(self, variables: Sequence[str], domains: Dict[str, Sequence[Any]], table: Dict[Assignment, float]) -> None:
        self.variables = tuple(variables)
        self.domains = domains
        self.table = table

    def value(self, assignment: Dict[str, Any]) -> float:
        """Probabilidad de este factor para una asignacion completa (dict var->valor)."""
        key = tuple(assignment[v] for v in self.variables)
        return self.table[key]

    def __repr__(self) -> str:  # pragma: no cover
        return f"Factor({self.variables})"


def _restrict(factor: Factor, evidence: Dict[str, Any]) -> Factor:
    """
    Dado: fija a su valor observado las variables de `evidence` que
    aparezcan en `factor` (y las retira de la lista de variables). Se
    usa como primer paso de inference_by_variable_elimination.
    """
    relevant = {v: val for v, val in evidence.items() if v in factor.variables}
    if not relevant:
        return factor
    new_variables = [v for v in factor.variables if v not in relevant]
    new_table: Dict[Assignment, float] = {}
    for key, prob in factor.table.items():
        assignment = dict(zip(factor.variables, key))
        if all(assignment[v] == val for v, val in relevant.items()):
            new_key = tuple(assignment[v] for v in new_variables)
            new_table[new_key] = prob
    return Factor(new_variables, factor.domains, new_table)


# ------------------------------------------------------------------
# Preguntas 3-5: operaciones genericas sobre factores
# ------------------------------------------------------------------


def join_factors(factors: List[Factor]) -> Factor:
    """
    Pregunta 3. Combina varios factores en uno solo: el conjunto de
    variables del resultado es la union de las variables de entrada
    (sin repetir, en el orden en que aparecen); su tabla es, para cada
    combinacion de valores de esas variables, el PRODUCTO del valor que
    tiene cada factor de entrada en la sub-asignacion correspondiente a
    sus propias variables.
    """
    raise NotImplementedError(
        "TODO: variables nuevas = union ordenada de las variables de entrada; "
        "para cada combinacion de valores (itertools.product sobre domains de esas variables), "
        "multiplica factor.value(assignment) de cada factor de entrada"
    )


def eliminate(factor: Factor, variable: str) -> Factor:
    """
    Pregunta 4. Marginaliza `variable` fuera de `factor`: para cada
    combinacion de valores del resto de variables, suma la probabilidad
    sobre todos los valores posibles de `variable`.
    """
    raise NotImplementedError(
        "TODO: nuevas variables = las de factor.variables sin `variable`; "
        "para cada fila de factor.table, suma su probabilidad en la entrada "
        "correspondiente (misma tupla, sin la posicion de `variable`) de la tabla nueva"
    )


def normalize(factor: Factor) -> Factor:
    """Pregunta 5. Divide toda la tabla por su suma total, de forma que sume 1."""
    raise NotImplementedError("TODO: divide cada valor de factor.table por sum(factor.table.values())")


# ------------------------------------------------------------------
# Pregunta 6: el algoritmo de eliminacion de variables
# ------------------------------------------------------------------


def inference_by_variable_elimination(
    factors: List[Factor],
    query_variables: List[str],
    evidence: Dict[str, Any],
    elimination_order: List[str],
) -> Factor:
    """
    Pregunta 6. Algoritmo general de eliminacion de variables:
      1. Restringe cada factor con `evidence` (dado, _restrict).
      2. Para cada variable de `elimination_order`, en ese orden: junta
         (join_factors) todos los factores actuales que la mencionan,
         elimina (eliminate) esa variable del resultado, y sustituye
         esos factores por el nuevo factor en la lista.
      3. Junta lo que quede (debe mencionar solo `query_variables`) y
         normaliza.
    """
    raise NotImplementedError(
        "TODO: current = [_restrict(f, evidence) for f in factors] (dado); "
        "para cada var en elimination_order: separa de current los factores que mencionan var, "
        "juntalos (join_factors) y elimina var (eliminate) del resultado, "
        "vuelve a meter ese factor en current; al final, join_factors(current) y normalize"
    )


def default_elimination_order(variables: Sequence[str], query_variables: Sequence[str], evidence: Dict[str, Any]) -> List[str]:
    """Dado: todas las variables de la red que no son consulta ni evidencia, en orden."""
    exclude = set(query_variables) | set(evidence.keys())
    return [v for v in variables if v not in exclude]


# ------------------------------------------------------------------
# Preguntas 1-2: la red bayesiana concreta de RobotPhysics
# ------------------------------------------------------------------


def room_type_variable() -> str:
    return "RoomType"


def detected_variable(object_name: str) -> str:
    return f"Detected_{object_name}"


def all_object_types(room_catalog: Dict[RoomType, Tuple[str, ...]] = OBJECT_CATALOG) -> List[str]:
    """Dado: los nombres de objeto distintos de todo el catalogo, en orden estable."""
    seen: Set[str] = set()
    ordered: List[str] = []
    for room_type in RoomType:
        for obj in room_catalog[room_type]:
            if obj not in seen:
                seen.add(obj)
                ordered.append(obj)
    return ordered


def construct_house_bayes_net(object_types: Sequence[str]) -> Tuple[List[str], Dict[str, Tuple[Any, ...]]]:
    """
    Pregunta 1. Topologia de la red: la variable RoomType (dominio los 4
    tipos de habitacion) y una variable booleana Detected_<obj> por cada
    nombre de `object_types`. Devuelve (variables, domains); `variables`
    lista RoomType primero y luego los Detected_* en el mismo orden que
    `object_types`.
    """
    raise NotImplementedError(
        "TODO: variables = [room_type_variable()] + [detected_variable(o) for o in object_types]; "
        "domains[room_type_variable()] = tuple(RoomType); domains[detected_variable(o)] = (True, False) para cada o"
    )


def fill_detection_cpts(
    variables: List[str],
    domains: Dict[str, Tuple[Any, ...]],
    object_types: Sequence[str],
    room_catalog: Dict[RoomType, Tuple[str, ...]] = OBJECT_CATALOG,
    *,
    object_density: float = 0.7,
    false_positive_rate: float = 0.1,
    false_negative_rate: float = 0.1,
) -> List[Factor]:
    """
    Pregunta 2. Devuelve la lista de factores CPT de la red:
      - P(RoomType): prior uniforme sobre los 4 tipos.
      - P(Detected_X | RoomType), uno por cada objeto de `object_types`:
        P(Detected_X=True | RoomType=r) =
            object_density*(1-false_negative_rate) + (1-object_density)*false_positive_rate   si X esta en room_catalog[r]
            false_positive_rate                                                                 en caso contrario
        (el objeto solo puede estar realmente presente si pertenece al
        catalogo de esa habitacion -- ver HouseWorld._populate_objects --,
        y a partir de ahi se combina con las tasas de error del sensor.)
    """
    raise NotImplementedError(
        "TODO: un Factor([room_type_variable()], domains, {...}) con prior uniforme 1/len(domains[RoomType]), "
        "mas un Factor([room_type_variable(), detected_variable(obj)], domains, {...}) por cada obj, "
        "con la formula de arriba para P(Detected_obj=True|r) y su complementario para False"
    )


# ------------------------------------------------------------------
# Pregunta 7: decision final del robot
# ------------------------------------------------------------------


def best_room_guess(
    factors: List[Factor],
    evidence: Dict[str, Any],
    elimination_order: List[str],
) -> Tuple[RoomType, float]:
    """
    Pregunta 7. Calcula P(RoomType | evidence) con
    inference_by_variable_elimination (Q6) y devuelve (tipo_mas_probable,
    su_probabilidad_posterior).
    """
    raise NotImplementedError(
        "TODO: result = inference_by_variable_elimination(factors, [room_type_variable()], evidence, elimination_order); "
        "recorre result.domains[room_type_variable()] y devuelve el valor con result.table[(valor,)] mas alto, junto a ese valor"
    )


# ------------------------------------------------------------------
# Infraestructura de demo (dada: no es TODO)
# ------------------------------------------------------------------


def true_objects_in_room(world: HouseWorld, room: Room) -> Set[str]:
    """Dado: objetos realmente presentes en esa habitacion (verdad fundamental, sin ruido)."""
    return {name for (x, y), name in world.all_objects() if room.contains(x, y)}


def simulate_noisy_detection(
    world: HouseWorld,
    room: Room,
    object_types: Sequence[str],
    rng: random.Random,
    *,
    false_positive_rate: float = 0.1,
    false_negative_rate: float = 0.1,
) -> Dict[str, bool]:
    """
    Dado: simula lo que el clasificador ruidoso del robot "detectaria"
    en esta habitacion. Para cada tipo de objeto, parte de si esta
    realmente presente (sin ruido) y aplica las tasas de error del
    sensor para decidir si se reporta como detectado.
    """
    present = true_objects_in_room(world, room)
    evidence: Dict[str, bool] = {}
    for obj in object_types:
        p_detect = (1 - false_negative_rate) if obj in present else false_positive_rate
        evidence[detected_variable(obj)] = rng.random() < p_detect
    return evidence


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Práctica 3 (redes bayesianas) sobre una CasaRobot.")
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--height", type=int, default=14)
    parser.add_argument("--rooms", type=int, default=5)
    parser.add_argument("--density", type=float, default=0.7)
    parser.add_argument("--fp-rate", type=float, default=0.1, help="tasa de falsos positivos del sensor")
    parser.add_argument("--fn-rate", type=float, default=0.1, help="tasa de falsos negativos del sensor")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-color", action="store_true")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    use_color = not args.no_color
    rng = random.Random(args.seed)

    world = HouseWorld(args.width, args.height, num_rooms=args.rooms, object_density=args.density, seed=args.seed)

    print(f"CasaRobot: {world.width}x{world.height}, {len(world.rooms)} habitaciones, seed={args.seed}")
    world.print(use_color=use_color)
    print("\nHabitaciones (tipo real, oculto para el robot):")
    for room in world.rooms:
        print(f"  #{room.room_id} {room.room_type.value}")

    # ----------------------------------------------------------------
    # Paso 2: Q1+Q2 -- construir la red y sus CPTs
    # ----------------------------------------------------------------
    # object_types = all_object_types()
    # variables, domains = construct_house_bayes_net(object_types)
    # factors = fill_detection_cpts(
    #     variables, domains, object_types,
    #     object_density=args.density, false_positive_rate=args.fp_rate, false_negative_rate=args.fn_rate,
    # )
    # print(f"\nRed bayesiana: {len(variables)} variables ({room_type_variable()} + {len(object_types)} Detected_*)")

    # ----------------------------------------------------------------
    # Paso 3-6: Q3-Q7 -- para cada habitacion, simular deteccion ruidosa
    # y estimar el tipo con best_room_guess
    # ----------------------------------------------------------------
    # correct = 0
    # for room in world.rooms:
    #     evidence = simulate_noisy_detection(
    #         world, room, object_types, rng,
    #         false_positive_rate=args.fp_rate, false_negative_rate=args.fn_rate,
    #     )
    #     elimination_order = default_elimination_order(variables, [room_type_variable()], evidence)
    #     guess, confidence = best_room_guess(factors, evidence, elimination_order)
    #     detected = sorted(obj for obj in object_types if evidence[detected_variable(obj)])
    #     hit = "OK" if guess == room.room_type else "FALLO"
    #     correct += guess == room.room_type
    #     print(f"\n  Sala #{room.room_id} (real: {room.room_type.value}) detectados={detected}")
    #     print(f"    -> estimado {guess.value} (confianza {confidence:.2f}) [{hit}]")
    # print(f"\nAciertos: {correct}/{len(world.rooms)}")


if __name__ == "__main__":  # pragma: no cover
    main()
