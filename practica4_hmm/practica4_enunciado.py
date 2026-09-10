"""
Practica 4: Localizacion con HMM -- CasaRobot.

Ver practicas_IA_2026.md (seccion 8) y practica4_hmm.tex para el
enunciado formal.

El robot no sabe donde esta dentro de la casa (paredes reales, no una
rejilla abierta). Mantiene una creencia bel(x,y) -- una distribucion de
probabilidad sobre las celdas libres -- y la actualiza con dos pasos de
un HMM: prediccion (move, tras cada accion) y correccion (observation,
tras cada lectura del sensor de contacto con paredes). El movimiento es
DIRIGIDO (no un paseo aleatorio) y no hay balizas: toda la informacion
espacial viene de las paredes de la casa generada.

Ejecuta el fichero tal cual para ver la casa generada (nada de lo que
hay que implementar se llama todavia):
    python3 practica4_enunciado.py --seed 42
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from house_world import DIRECTIONS, HouseWorld, Robot  # noqa: E402

Coord = Tuple[int, int]
WallPattern = Dict[str, bool]

# Modelo de sensor: P(medido = patron real) = 0.7; para cada uno de los 4
# patrones que difieren en exactamente 1 bit, 0.075 (0.7 + 4*0.075 = 1.0).
SENSOR_MATCH_PROB = 0.7
SENSOR_ONE_BIT_FLIP_PROB = 0.075


class LocalizingRobot:
    """
    Creencia bel(x,y) del robot sobre su propia posicion dentro de una
    HouseWorld, mantenida y actualizada mediante un HMM.
    """

    def __init__(self, world: HouseWorld, *, move_success_prob: float = 0.8) -> None:
        self.world = world
        self.move_success_prob = move_success_prob
        free_cells = [
            (x, y)
            for y in range(1, world.height + 1)
            for x in range(1, world.width + 1)
            if world.is_free(x, y)
        ]
        self.belief: Dict[Coord, float] = {cell: 1.0 / len(free_cells) for cell in free_cells}

    # ------------------------------------------------------------------
    # Pregunta 1
    # ------------------------------------------------------------------

    def init_pose(self, x0: int, y0: int) -> None:
        """Fija una creencia inicial determinista: bel(x0,y0)=1, el resto 0."""
        raise NotImplementedError("TODO: bel(x0,y0)=1.0, bel(cualquier otra celda)=0.0")

    def most_likely_pose(self) -> Tuple[Coord, float]:
        """Dado: la celda con mayor creencia, y su probabilidad."""
        best_cell = max(self.belief, key=self.belief.get)
        return best_cell, self.belief[best_cell]

    # ------------------------------------------------------------------
    # Pregunta 2: paso de prediccion (modelo de movimiento)
    # ------------------------------------------------------------------

    def move(self, action: str) -> None:
        """
        Paso de prediccion del HMM:
            bel_{t+1}(x2,y2) = sum_{x,y} P(x2,y2 | x,y,action) * bel_t(x,y)

        Modelo de movimiento dirigido: `action` en {N,S,E,W,STAY}.
          - "STAY": el robot se queda siempre donde esta (determinista).
          - N/S/E/W: si la celda destino es libre, se llega a ella con
            probabilidad move_success_prob y se permanece en el origen
            con probabilidad (1 - move_success_prob); si la celda destino
            es un muro, toda la masa se queda en el origen (no puede
            "salir" de la casa).
        """
        raise NotImplementedError(
            "TODO: construye new_belief (diccionario a 0.0 en todas las celdas); "
            "para cada (x,y) con bel_t(x,y)>0: si action=='STAY', suma toda su masa a (x,y); "
            "si no, calcula dest=(x+dx,y+dy) con DIRECTIONS[action]; si world.is_free(*dest), "
            "reparte move_success_prob a dest y (1-move_success_prob) a (x,y); "
            "si no es libre, toda la masa se queda en (x,y). Al final, self.belief = new_belief"
        )

    # ------------------------------------------------------------------
    # Pregunta 3: modelo del sensor de contacto con paredes
    # ------------------------------------------------------------------

    def wall_pattern_at(self, x: int, y: int) -> WallPattern:
        """El patron de contacto con paredes REAL en (x,y) (sin ruido)."""
        raise NotImplementedError(
            "TODO: {d: self.world.is_wall(x+dx, y+dy) for d, (dx,dy) in DIRECTIONS.items()}"
        )

    def sensor_likelihood(self, measured: WallPattern, true_pattern: WallPattern) -> float:
        """
        P(Z=measured | patron real = true_pattern):
          0.7 si coinciden en las 4 direcciones;
          0.075 por cada direccion en la que difieren, si difieren en
          EXACTAMENTE una (4 patrones posibles, 0.075 cada uno);
          0 si difieren en 2 o mas.
        """
        raise NotImplementedError(
            "TODO: cuenta en cuantas direcciones difieren measured y true_pattern; "
            "0 diferencias -> SENSOR_MATCH_PROB; 1 diferencia -> SENSOR_ONE_BIT_FLIP_PROB; 2+ -> 0.0"
        )

    # ------------------------------------------------------------------
    # Pregunta 4: paso de correccion (observacion)
    # ------------------------------------------------------------------

    def observation(self, measured: WallPattern) -> None:
        """
        Paso de correccion del HMM: multiplica cada bel(x,y) por la
        verosimilitud de haber medido `measured` estando en (x,y), y
        normaliza para que vuelva a sumar 1.
        """
        raise NotImplementedError(
            "TODO: para cada (x,y) en self.belief, multiplica bel(x,y) por "
            "sensor_likelihood(measured, wall_pattern_at(x,y)); despues normaliza "
            "(divide cada valor por la suma total de self.belief)"
        )

    # ------------------------------------------------------------------
    # Dado: misma formula de transicion que la Pregunta 2, pero para una
    # unica pareja (origen, destino) en vez de para toda la creencia --
    # la usa la Pregunta 6 (Viterbi), que necesita evaluarla celda a celda.
    # ------------------------------------------------------------------

    def transition_probability(self, x: int, y: int, x2: int, y2: int, action: str) -> float:
        """P((x2,y2) | (x,y), action): igual modelo de movimiento que move() (Pregunta 2)."""
        if action == "STAY":
            return 1.0 if (x2, y2) == (x, y) else 0.0
        dx, dy = DIRECTIONS[action]
        dest = (x + dx, y + dy)
        dest_free = self.world.is_free(*dest)
        if (x2, y2) == dest and dest_free:
            return self.move_success_prob
        if (x2, y2) == (x, y):
            return 1.0 if not dest_free else (1.0 - self.move_success_prob)
        return 0.0

    # ------------------------------------------------------------------
    # Pregunta 6 (opcional): explicacion mas probable (Viterbi)
    # ------------------------------------------------------------------

    def most_likely_trajectory(
        self,
        start_belief: Dict[Coord, float],
        actions: List[str],
        observations: List[WallPattern],
    ) -> List[Coord]:
        """
        Pregunta 6 (opcional). Algoritmo de Viterbi: la secuencia de
        posiciones x_0..x_T que MAXIMIZA P(x_0..x_T | z_0..z_T, a_0..a_{T-1}) --
        no la que se obtendria encadenando el most_likely_pose() de cada
        paso de filtrado por separado (eso no tiene por que ser una
        trayectoria fisicamente valida). len(observations) debe ser
        len(actions) + 1 (una observacion inicial mas una por cada accion).
        """
        raise NotImplementedError(
            "TODO: programacion dinamica hacia adelante guardando, para cada instante t y cada "
            "celda, la probabilidad de la MEJOR trayectoria que termina ahi (delta) y de que celda "
            "viene (psi, para reconstruir el camino al final). Usa transition_probability (dado) y "
            "sensor_likelihood/wall_pattern_at (Pregunta 3) en cada paso; al final, reconstruye el "
            "camino desde argmax(delta en el ultimo instante) siguiendo psi hacia atras"
        )


# ------------------------------------------------------------------
# Infraestructura de demo (dada: no es TODO)
# ------------------------------------------------------------------


def simulate_directed_move(robot: Robot, action: str, rng: random.Random, *, move_success_prob: float = 0.8) -> None:
    """
    Dado: ejecuta `action` sobre un Robot REAL con el modelo de
    movimiento dirigido (0.8 de exito si la celda destino es libre; si
    no, o con probabilidad 0.2, el robot se queda quieto). El robot no
    "sabe" si tuvo exito -- eso es justo lo que LocalizingRobot.move()
    tiene que marginalizar.
    """
    if action == "STAY":
        return
    dx, dy = DIRECTIONS[action]
    dest = (robot.x + dx, robot.y + dy)
    if robot.world.is_free(*dest) and rng.random() < move_success_prob:
        robot.move(action)


def simulate_noisy_wall_observation(true_pattern: WallPattern, rng: random.Random) -> WallPattern:
    """
    Dado: simula la lectura ruidosa del sensor de contacto a partir del
    patron real, con el modelo 0.7 / 0.075x4 (Pregunta 3).
    """
    noisy = dict(true_pattern)
    if rng.random() >= SENSOR_MATCH_PROB:
        flip = rng.choice(list(DIRECTIONS.keys()))
        noisy[flip] = not noisy[flip]
    return noisy


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Práctica 4 (localización con HMM) sobre una CasaRobot.")
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--height", type=int, default=14)
    parser.add_argument("--rooms", type=int, default=5)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--move-success-prob", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument(
        "--unknown-start", action="store_true",
        help="empieza con creencia uniforme (posición realmente desconocida) en vez de con init_pose",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    use_color = not args.no_color
    rng = random.Random(args.seed)

    world = HouseWorld(args.width, args.height, num_rooms=args.rooms, seed=args.seed)
    true_robot = Robot(world)
    localizer = LocalizingRobot(world, move_success_prob=args.move_success_prob)

    # precision=3 formatea cada valor como "0.023" (5 caracteres): con el
    # cell_width=3 por defecto, _fit_text no lo consideraría "cabe" y
    # rellenaría todas las celdas con "###" en vez de mostrar el número
    # (mismo motivo por el que --demo-heat de house_world.py usa
    # heat_width = max(cell_width, 7)).
    heat_kwargs = dict(precision=3, cell_width=7, use_color=use_color)

    print(f"CasaRobot: {world.width}x{world.height}, {len(world.rooms)} habitaciones, seed={args.seed}")
    print(f"Posición real inicial: {true_robot.pos}\n")
    print("Creencia inicial (uniforme sobre las celdas libres):")
    world.print(robot_pos=true_robot.pos, heat=localizer.belief, **heat_kwargs)

    # ----------------------------------------------------------------
    # Paso 2: Q1 -- init_pose (opcional, simplifica la demo: sin ella
    # la posición inicial es realmente desconocida, ver --unknown-start)
    # ----------------------------------------------------------------
    # if not args.unknown_start:
    #     localizer.init_pose(*true_robot.pos)
    #     print("\nCreencia tras init_pose (posición conocida):")
    #     world.print(robot_pos=true_robot.pos, heat=localizer.belief, **heat_kwargs)

    # ----------------------------------------------------------------
    # Paso 3: Q3+Q4 -- primera observación
    # ----------------------------------------------------------------
    # initial_pattern = true_robot.wall_contact()
    # localizer.observation(simulate_noisy_wall_observation(initial_pattern, rng))
    # print("\nTras la primera observación:")
    # world.print(robot_pos=true_robot.pos, heat=localizer.belief, **heat_kwargs)

    # ----------------------------------------------------------------
    # Paso 4-5: Q2+Q4 -- bucle de movimiento + observación (Q5: pipeline completo)
    # ----------------------------------------------------------------
    # for step in range(1, args.steps + 1):
    #     action = rng.choice(list(DIRECTIONS.keys()))
    #     simulate_directed_move(true_robot, action, rng, move_success_prob=args.move_success_prob)
    #     localizer.move(action)
    #     measured = simulate_noisy_wall_observation(true_robot.wall_contact(), rng)
    #     localizer.observation(measured)
    #     print(f"\nPaso {step}: acción intentada {action}. Posición real: {true_robot.pos}")
    #     world.print(robot_pos=true_robot.pos, heat=localizer.belief, **heat_kwargs)
    #
    # guess, confidence = localizer.most_likely_pose()
    # print(f"\nEstimación final: {guess} (confianza {confidence:.3f}) -- posición real: {true_robot.pos}")

    # ----------------------------------------------------------------
    # Paso 6 (opcional): Q6 -- most_likely_trajectory
    # ----------------------------------------------------------------
    # (repite el bucle anterior guardando actions/observations en listas,
    # y compara localizer.most_likely_trajectory(...) con las posiciones
    # reales del robot en cada instante)


if __name__ == "__main__":  # pragma: no cover
    main()
