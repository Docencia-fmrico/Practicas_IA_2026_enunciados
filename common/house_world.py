"""
CasaRobot: escenario comun para las practicas de IA 2026/2027.

Genera una casa aleatoria (habitaciones rectangulares conectadas por
pasillos, pobladas con objetos tipicos segun el tipo de habitacion) y
un robot que se mueve por ella con colision contra las paredes.

Uso como libreria:
    from house_world import HouseWorld, Robot
    world = HouseWorld(16, 11, seed=42)
    robot = Robot(world)
    world.print(robot_pos=(robot.x, robot.y))

Uso como script (genera y muestra una casa en la terminal):
    python3 house_world.py --width 16 --height 11 --rooms 5 --seed 42
    python3 house_world.py --walk 6 --no-color
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

Coord = Tuple[int, int]


class RoomType(Enum):
    KITCHEN = "Cocina"
    BEDROOM = "Dormitorio"
    BATHROOM = "Baño"
    LIVING_ROOM = "Salón"


OBJECT_CATALOG: Dict[RoomType, Tuple[str, ...]] = {
    RoomType.KITCHEN: ("nevera", "fogón", "fregadero", "microondas"),
    RoomType.BEDROOM: ("cama", "armario", "mesilla"),
    RoomType.BATHROOM: ("inodoro", "lavabo", "ducha"),
    RoomType.LIVING_ROOM: ("sofá", "televisor", "mesa"),
}

# Direcciones cardinales validas para Robot.move(). "STAY" se trata aparte.
DIRECTIONS: Dict[str, Coord] = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}


@dataclass(frozen=True)
class Room:
    """Habitacion rectangular, coordenadas 1-based e inclusivas."""

    room_id: int
    room_type: RoomType
    x0: int
    y0: int
    x1: int
    y1: int

    def contains(self, x: int, y: int) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def center(self) -> Coord:
        return ((self.x0 + self.x1) // 2, (self.y0 + self.y1) // 2)


class HouseWorld:
    """
    Casa generada aleatoriamente sobre una rejilla 2D.

    Convencion de coordenadas (igual que la practica de HMM del curso
    anterior): API externa 1-based, x en [1..width], y en [1..height].
    Internamente se almacena en una matriz row-major 0-based.
    """

    ROOM_COLORS: Dict[RoomType, Tuple[int, int, int]] = {
        RoomType.KITCHEN: (235, 195, 160),
        RoomType.BEDROOM: (195, 205, 240),
        RoomType.BATHROOM: (180, 230, 230),
        RoomType.LIVING_ROOM: (195, 230, 195),
    }
    WALL_COLOR: Tuple[int, int, int] = (35, 35, 40)
    CORRIDOR_COLOR: Tuple[int, int, int] = (215, 213, 205)
    OBJECT_FG: Tuple[int, int, int] = (60, 35, 10)
    ROBOT_BG: Tuple[int, int, int] = (215, 55, 55)
    ROBOT_FG: Tuple[int, int, int] = (255, 255, 255)

    def __init__(
        self,
        width: int,
        height: int,
        *,
        num_rooms: int = 5,
        min_room_size: int = 3,
        max_room_size: int = 6,
        object_density: float = 0.7,
        seed: Optional[int] = None,
    ) -> None:
        if width < 7 or height < 7:
            raise ValueError(f"width/height demasiado pequeños (mínimo 7x7), recibido {width}x{height}")
        if num_rooms < 1:
            raise ValueError(f"num_rooms debe ser >= 1, recibido {num_rooms}")
        if min_room_size < 2 or max_room_size < min_room_size:
            raise ValueError(f"tamaños de habitación inválidos: min={min_room_size}, max={max_room_size}")
        if max_room_size > min(width, height) - 3:
            raise ValueError(
                f"max_room_size={max_room_size} demasiado grande para un mapa {width}x{height} "
                f"(deja al menos 1 celda de muro exterior en cada lado)"
            )
        if not (0.0 <= object_density <= 1.0):
            raise ValueError(f"object_density debe estar en [0,1], recibido {object_density}")

        self._width = width
        self._height = height
        self._rng = random.Random(seed)

        self._floor: List[List[bool]] = [[False] * width for _ in range(height)]
        self._room_id_at: List[List[int]] = [[-1] * width for _ in range(height)]
        self._objects: Dict[Coord, List[str]] = {}
        self._rooms: List[Room] = []
        # Primero se agotan los 4 tipos (sin repetir), para que una casa con
        # 4-5 habitaciones no salga, por azar, con varias cocinas. A partir
        # de ahí solo se repiten tipos que sí es normal tener duplicados.
        self._room_type_pool: List[RoomType] = self._rng.sample(list(RoomType), k=len(RoomType))
        self._REPEATABLE_ROOM_TYPES = (RoomType.BEDROOM, RoomType.BATHROOM)

        self._generate_rooms(num_rooms, min_room_size, max_room_size)
        self._connect_rooms()
        self._populate_objects(object_density)

    # ------------------------------------------------------------------
    # Generacion
    # ------------------------------------------------------------------

    def _generate_rooms(self, num_rooms: int, min_size: int, max_size: int) -> None:
        max_attempts = max(num_rooms * 200, 400)
        attempts = 0
        while len(self._rooms) < num_rooms and attempts < max_attempts:
            attempts += 1
            w = self._rng.randint(min_size, max_size)
            h = self._rng.randint(min_size, max_size)
            x0 = self._rng.randint(2, self._width - w)
            y0 = self._rng.randint(2, self._height - h)
            x1, y1 = x0 + w - 1, y0 + h - 1

            if self._overlaps_existing(x0, y0, x1, y1, margin=1):
                continue

            room = Room(len(self._rooms), self._next_room_type(), x0, y0, x1, y1)
            self._carve_room(room)
            self._rooms.append(room)
        # Con num_rooms >= 1 (validado en __init__) y max_room_size acotado
        # para caber en la rejilla, el primer intento del bucle siempre tiene
        # éxito (lista de habitaciones vacía => nunca hay solape), así que
        # self._rooms nunca queda vacío aquí.

    def _next_room_type(self) -> RoomType:
        if self._room_type_pool:
            return self._room_type_pool.pop()
        return self._rng.choice(self._REPEATABLE_ROOM_TYPES)

    def _overlaps_existing(self, x0: int, y0: int, x1: int, y1: int, *, margin: int) -> bool:
        for r in self._rooms:
            if (x0 - margin <= r.x1 and x1 + margin >= r.x0
                    and y0 - margin <= r.y1 and y1 + margin >= r.y0):
                return True
        return False

    def _carve_room(self, room: Room) -> None:
        for y in range(room.y0, room.y1 + 1):
            for x in range(room.x0, room.x1 + 1):
                self._set_floor(x, y, room.room_id)

    def _set_floor(self, x: int, y: int, room_id: int = -1) -> None:
        xi, yi = x - 1, y - 1
        self._floor[yi][xi] = True
        if room_id >= 0:
            self._room_id_at[yi][xi] = room_id

    def _connect_rooms(self) -> None:
        # Encadena las habitaciones en el orden en que se generaron con
        # pasillos en L. Un camino que toca todas las salas ya garantiza
        # conectividad total, sin necesidad de un MST.
        for a, b in zip(self._rooms, self._rooms[1:]):
            self._carve_corridor(a.center(), b.center())

    def _carve_corridor(self, start: Coord, end: Coord) -> None:
        (x0, y0), (x1, y1) = start, end
        if self._rng.random() < 0.5:
            for x in range(min(x0, x1), max(x0, x1) + 1):
                self._set_floor(x, y0)
            for y in range(min(y0, y1), max(y0, y1) + 1):
                self._set_floor(x1, y)
        else:
            for y in range(min(y0, y1), max(y0, y1) + 1):
                self._set_floor(x0, y)
            for x in range(min(x0, x1), max(x0, x1) + 1):
                self._set_floor(x, y1)

    def _populate_objects(self, density: float) -> None:
        for room in self._rooms:
            free_cells = [
                (x, y)
                for x in range(room.x0, room.x1 + 1)
                for y in range(room.y0, room.y1 + 1)
            ]
            self._rng.shuffle(free_cells)
            cell_iter = iter(free_cells)
            for obj_name in OBJECT_CATALOG[room.room_type]:
                if self._rng.random() > density:
                    continue
                try:
                    pos = next(cell_iter)
                except StopIteration:
                    break
                self._objects.setdefault(pos, []).append(obj_name)

    # ------------------------------------------------------------------
    # API de consulta (para planificar: no mueve nada)
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def rooms(self) -> List[Room]:
        return list(self._rooms)

    def in_bounds(self, x: int, y: int) -> bool:
        return 1 <= x <= self._width and 1 <= y <= self._height

    def is_wall(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        return not self._floor[y - 1][x - 1]

    def is_free(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and not self.is_wall(x, y)

    def neighbors(self, x: int, y: int) -> List[Coord]:
        out: List[Coord] = []
        for dx, dy in DIRECTIONS.values():
            nx, ny = x + dx, y + dy
            if self.is_free(nx, ny):
                out.append((nx, ny))
        return out

    def room_at(self, x: int, y: int) -> Optional[Room]:
        if not self.in_bounds(x, y):
            return None
        rid = self._room_id_at[y - 1][x - 1]
        return self._rooms[rid] if rid >= 0 else None

    def objects_at(self, x: int, y: int) -> List[str]:
        return list(self._objects.get((x, y), []))

    def all_objects(self) -> List[Tuple[Coord, str]]:
        out = [(pos, name) for pos, names in self._objects.items() for name in names]
        return sorted(out, key=lambda item: (item[0][1], item[0][0]))

    def random_free_cell(self) -> Coord:
        free = [
            (x, y)
            for y in range(1, self._height + 1)
            for x in range(1, self._width + 1)
            if self._floor[y - 1][x - 1]
        ]
        return self._rng.choice(free)

    # ------------------------------------------------------------------
    # Visualizacion en terminal (ANSI 24-bit, sin dependencias externas)
    #
    # Tres capas opcionales, combinables, sobre el mapa base (muros /
    # habitaciones / pasillos / objetos):
    #   - robot_pos: posicion actual de un robot.
    #   - path:      secuencia de celdas de una ruta encontrada (Practica 1).
    #   - heat:      {(x,y): valor} para pintar un mapa de calor rojo->verde
    #                (Practica 4, mismo criterio de color que World.print()
    #                en practicas/Practica_HMMS_localizacion/practica4.py).
    # Prioridad si varias aplican a la vez: robot > muro > heat > path > resto.
    # ------------------------------------------------------------------

    PATH_COLOR: Tuple[int, int, int] = (170, 90, 210)
    PATH_FG: Tuple[int, int, int] = (255, 255, 255)

    @staticmethod
    def _ansi_bg(r: int, g: int, b: int) -> str:
        return f"\x1b[48;2;{r};{g};{b}m"

    @staticmethod
    def _ansi_fg(r: int, g: int, b: int) -> str:
        return f"\x1b[38;2;{r};{g};{b}m"

    @staticmethod
    def _ansi_reset() -> str:
        return "\x1b[0m"

    @staticmethod
    def _clamp01(t: float) -> float:
        return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t

    @classmethod
    def _heat_bg(cls, t: float) -> Tuple[int, int, int]:
        """Rojo (t=0) -> verde (t=1). Misma fórmula que practica4.py del curso anterior."""
        t = cls._clamp01(t)
        return (int(round(255.0 * (1.0 - t))), int(round(255.0 * t)), 0)

    @staticmethod
    def _contrast_fg(bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
        r, g, b = bg
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return (0, 0, 0) if luminance > 140.0 else (255, 255, 255)

    @staticmethod
    def _fit_text(text: str, width: int) -> str:
        """Centra `text` en `width` caracteres. Si no cabe, usa '#' de relleno
        en vez de truncar (truncar un número lo haría parecer uno más corto
        pero válido, p. ej. "0.125" -> "0.1")."""
        if not text:
            return " " * width
        if len(text) > width:
            return "#" * width
        return text.center(width)

    def _resolve_cell_color(
        self,
        x: int,
        y: int,
        *,
        robot_pos: Optional[Coord],
        path_cells: Optional[set],
        heat: Optional[Dict[Coord, float]],
        heat_range: Optional[Tuple[float, float]],
        precision: int,
    ) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], str]:
        if robot_pos is not None and (x, y) == robot_pos:
            return self.ROBOT_BG, self.ROBOT_FG, "R"
        if self.is_wall(x, y):
            return self.WALL_COLOR, self.WALL_COLOR, ""
        if heat is not None and (x, y) in heat:
            value = heat[(x, y)]
            p_min, p_max = heat_range
            t = 0.0 if p_max <= p_min else (value - p_min) / (p_max - p_min)
            bg = self._heat_bg(t)
            return bg, self._contrast_fg(bg), f"{value:.{precision}f}"
        if path_cells is not None and (x, y) in path_cells:
            objs = self.objects_at(x, y)
            # "AR*" en vez de "AR" si además hay un objeto: en modo sin color
            # el fondo no está disponible para distinguir "objeto" de "objeto
            # que además está en la ruta", así que hace falta un marcador.
            text = f"{objs[0][:2].upper()}*" if objs else "*"
            return self.PATH_COLOR, self.PATH_FG, text
        room = self.room_at(x, y)
        bg = self.ROOM_COLORS[room.room_type] if room else self.CORRIDOR_COLOR
        objs = self.objects_at(x, y)
        if objs:
            return bg, self.OBJECT_FG, objs[0][:2].upper()
        return bg, bg, ""

    def render(
        self,
        *,
        robot_pos: Optional[Coord] = None,
        path: Optional[Sequence[Coord]] = None,
        heat: Optional[Dict[Coord, float]] = None,
        precision: int = 3,
        cell_width: int = 3,
        cell_height: int = 1,
        use_color: bool = True,
        show_axes: bool = True,
    ) -> str:
        if cell_width < 1 or cell_height < 1:
            raise ValueError(f"cell_width y cell_height deben ser >= 1, recibido {(cell_width, cell_height)}")

        path_cells = set(path) if path is not None else None
        heat_range = (min(heat.values()), max(heat.values())) if heat else None

        label_width = len(f"y={self._height}") + 2
        blank_prefix = " " * label_width
        content_row = (cell_height - 1) // 2

        lines: List[str] = []
        if show_axes:
            header = blank_prefix + "".join(f"{x:^{cell_width}d}" for x in range(1, self._width + 1))
            lines.append(header)

        for y in range(1, self._height + 1):
            row_cells: List[Tuple[Tuple[int, int, int], Tuple[int, int, int], str]] = []
            plain_texts: List[str] = []
            for x in range(1, self._width + 1):
                bg, fg, text = self._resolve_cell_color(
                    x, y,
                    robot_pos=robot_pos, path_cells=path_cells,
                    heat=heat, heat_range=heat_range, precision=precision,
                )
                row_cells.append((bg, fg, text))
                plain_texts.append(text if text else ("#" if self.is_wall(x, y) else "."))

            for sub_row in range(cell_height):
                is_content_row = sub_row == content_row
                if show_axes:
                    prefix = f"y={y}".ljust(label_width) if is_content_row else blank_prefix
                else:
                    prefix = ""
                parts: List[str] = []
                for (bg, fg, text), plain in zip(row_cells, plain_texts):
                    if use_color:
                        shown = self._fit_text(text, cell_width) if is_content_row else " " * cell_width
                        parts.append(self._ansi_bg(*bg) + self._ansi_fg(*fg) + shown + self._ansi_reset())
                    elif len(plain) <= 1:
                        # simbolo solido (muro/suelo/robot/ruta): rellena toda la celda
                        parts.append(self._fit_text(plain, cell_width))
                    else:
                        # contenido informativo (objeto/valor): una sola vez, fila central
                        parts.append(self._fit_text(plain, cell_width) if is_content_row else " " * cell_width)
                lines.append(prefix + "".join(parts))
        return "\n".join(lines)

    def print(
        self,
        *,
        robot_pos: Optional[Coord] = None,
        path: Optional[Sequence[Coord]] = None,
        heat: Optional[Dict[Coord, float]] = None,
        precision: int = 3,
        cell_width: int = 3,
        cell_height: int = 1,
        use_color: bool = True,
        show_axes: bool = True,
    ) -> None:
        print(
            self.render(
                robot_pos=robot_pos, path=path, heat=heat, precision=precision,
                cell_width=cell_width, cell_height=cell_height,
                use_color=use_color, show_axes=show_axes,
            )
        )

    def legend(self, *, use_color: bool = True, show_path: bool = False, show_heat: bool = False) -> str:
        def swatch(rgb: Tuple[int, int, int], plain: str) -> str:
            return self._ansi_bg(*rgb) + "   " + self._ansi_reset() if use_color else plain

        lines = ["Leyenda:"]
        lines.append(f"  {swatch(self.WALL_COLOR, '###')} muro (no atravesable)")
        for rt in RoomType:
            lines.append(f"  {swatch(self.ROOM_COLORS[rt], '...')} {rt.value}")
        lines.append(f"  {swatch(self.CORRIDOR_COLOR, '...')} pasillo")
        lines.append(f"  {swatch(self.ROBOT_BG, '[R]')} robot")
        lines.append("  2 letras mayúsculas en una celda = inicio del nombre de un objeto detectable ahí")
        if show_path:
            lines.append(f"  {swatch(self.PATH_COLOR, '[*]')} ruta encontrada")
        if show_heat:
            lines.append(
                f"  {swatch(self._heat_bg(0.0), 'rojo')} -> {swatch(self._heat_bg(1.0), 'verde')} "
                "probabilidad baja -> alta (mapa de calor)"
            )
        return "\n".join(lines)


class Robot:
    """Robot que ocupa una celda de una HouseWorld y se mueve por ella."""

    def __init__(self, world: HouseWorld, *, start: Optional[Coord] = None) -> None:
        self.world = world
        self.x, self.y = start if start is not None else world.random_free_cell()
        if not world.is_free(self.x, self.y):
            raise ValueError(f"Posición inicial no válida (colisiona con un muro): {(self.x, self.y)}")

    @property
    def pos(self) -> Coord:
        return (self.x, self.y)

    def wall_contact(self) -> Dict[str, bool]:
        """Sensor de contacto: True si hay un muro justo en esa dirección."""
        return {d: self.world.is_wall(self.x + dx, self.y + dy) for d, (dx, dy) in DIRECTIONS.items()}

    def detect_objects(self, *, radius: int = 0) -> List[str]:
        """Objetos detectables en la celda actual (radius=0) o alrededor."""
        found: List[str] = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                found.extend(self.world.objects_at(self.x + dx, self.y + dy))
        return found

    def move(self, direction: str) -> bool:
        """
        Intenta moverse. Devuelve True si tuvo éxito, False si colisiona
        (el robot no se mueve). "STAY" siempre tiene éxito sin desplazarse.
        """
        if direction == "STAY":
            return True
        if direction not in DIRECTIONS:
            raise ValueError(f"Dirección desconocida: {direction!r} (válidas: {list(DIRECTIONS)} + 'STAY')")
        dx, dy = DIRECTIONS[direction]
        nx, ny = self.x + dx, self.y + dy
        if not self.world.is_free(nx, ny):
            return False
        self.x, self.y = nx, ny
        return True


# ------------------------------------------------------------------
# Demo / CLI: genera una casa con los parametros dados y la muestra
# ------------------------------------------------------------------

def _random_walk_path(world: HouseWorld, start: Coord, steps: int, rng: random.Random) -> List[Coord]:
    """Camino aleatorio autoevitando colisiones (para previsualizar `path=`, no para probar colisiones)."""
    path = [start]
    pos = start
    for _ in range(steps):
        options = world.neighbors(*pos)
        if not options:  # pragma: no cover -- toda celda libre generada tiene >=1 vecino libre
            break
        pos = rng.choice(options)
        path.append(pos)
    return path


def _synthetic_heat(world: HouseWorld, center: Coord) -> Dict[Coord, float]:
    """Distribución de probabilidad de juguete (no es un HMM real) para previsualizar `heat=`."""
    cx, cy = center
    return {
        (x, y): 1.0 / (1 + abs(x - cx) + abs(y - cy))
        for y in range(1, world.height + 1)
        for x in range(1, world.width + 1)
        if world.is_free(x, y)
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera y muestra una CasaRobot en la terminal.")
    parser.add_argument("--width", type=int, default=20, help="ancho de la casa (default: 20)")
    parser.add_argument("--height", type=int, default=14, help="alto de la casa (default: 14)")
    parser.add_argument("--rooms", type=int, default=5, help="número de habitaciones a intentar colocar (default: 5)")
    parser.add_argument("--min-room", type=int, default=3, help="tamaño mínimo de habitación (default: 3)")
    parser.add_argument("--max-room", type=int, default=5, help="tamaño máximo de habitación (default: 5)")
    parser.add_argument("--density", type=float, default=0.7, help="probabilidad de colocar cada objeto típico (default: 0.7)")
    parser.add_argument("--seed", type=int, default=None, help="semilla aleatoria (default: aleatoria en cada ejecución)")
    parser.add_argument("--no-color", action="store_true", help="desactiva el color ANSI (fallback ASCII)")
    parser.add_argument("--cell-width", type=int, default=3, help="ancho de celda en caracteres, tipo 'zoom' (default: 3)")
    parser.add_argument("--cell-height", type=int, default=1, help="alto de celda en filas de terminal, tipo 'zoom' (default: 1)")
    parser.add_argument("--walk", type=int, default=0, help="nº de pasos aleatorios del robot a simular (animado) tras generar la casa")
    parser.add_argument("--demo-path", type=int, default=0, metavar="N", help="previsualiza el overlay de ruta con un paseo aleatorio de N pasos (no es un plan real; ver practica1.py)")
    parser.add_argument("--demo-heat", action="store_true", help="previsualiza el overlay de probabilidad con una distribución de juguete (no es un HMM real; ver practica4)")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()

    world = HouseWorld(
        args.width, args.height,
        num_rooms=args.rooms, min_room_size=args.min_room, max_room_size=args.max_room,
        object_density=args.density, seed=args.seed,
    )
    robot = Robot(world)
    use_color = not args.no_color
    size_kwargs = dict(cell_width=args.cell_width, cell_height=args.cell_height)

    print(f"CasaRobot: {world.width}x{world.height}, {len(world.rooms)}/{args.rooms} habitaciones, seed={args.seed}\n")
    world.print(robot_pos=robot.pos, use_color=use_color, **size_kwargs)
    print()
    print(world.legend(use_color=use_color))

    print(f"\nRobot en (x={robot.x}, y={robot.y})")
    print("\nHabitaciones:")
    for room in world.rooms:
        print(f"  #{room.room_id} {room.room_type.value:<11s} ({room.x0},{room.y0})-({room.x1},{room.y1})")
    print("\nObjetos:")
    for pos, name in world.all_objects():
        print(f"  {name:<12s} en {pos}")

    rng = random.Random(args.seed)

    for step in range(1, args.walk + 1):
        direction = rng.choice(list(DIRECTIONS.keys()))
        ok = robot.move(direction)
        estado = "se mueve" if ok else "COLISIÓN, no se mueve"
        print(f"\nPaso {step}: intenta {direction} -> {estado}")
        world.print(robot_pos=robot.pos, use_color=use_color, **size_kwargs)

    if args.demo_path > 0:
        path = _random_walk_path(world, robot.pos, args.demo_path, rng)
        print(f"\n--- Vista previa de overlay de ruta ({len(path) - 1} pasos, paseo aleatorio de ejemplo) ---")
        world.print(robot_pos=robot.pos, path=path, use_color=use_color, **size_kwargs)
        print(world.legend(use_color=use_color, show_path=True))

    if args.demo_heat:
        heat = _synthetic_heat(world, robot.pos)
        heat_width = max(args.cell_width, 7)
        print("\n--- Vista previa de overlay de probabilidad (distribución de juguete) ---")
        world.print(heat=heat, use_color=use_color, cell_width=heat_width, cell_height=args.cell_height)
        print(world.legend(use_color=use_color, show_heat=True))


if __name__ == "__main__":  # pragma: no cover -- probado via subprocess en test_main_cli_subprocess_smoke
    main()
