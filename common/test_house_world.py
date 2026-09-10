"""
Suite de tests de house_world.py (escenario comun CasaRobot).

Combina dos estrategias:
  - Tests de propiedades/invariantes sobre casas generadas al azar (muchas
    semillas/tamaños), para comprobar que el generador es correcto para
    "cualquier entrada válida", no solo para un ejemplo.
  - Tests puntuales, con entradas construidas a mano, para las funciones
    puras y para ramas concretas (colisiones, ramas de color, overlays de
    ruta/calor, tamaño de celda, validación de parámetros, CLI) que no
    dependen de qué haya tocado generar al azar.

Ejecutar con cobertura (ver setup.cfg para los umbrales):
    pytest --cov=house_world --cov-report=term-missing
"""

from __future__ import annotations

import subprocess
import sys
from collections import deque
from pathlib import Path

import pytest

from house_world import (
    DIRECTIONS,
    OBJECT_CATALOG,
    HouseWorld,
    Robot,
    Room,
    RoomType,
    _build_arg_parser,
    _random_walk_path,
    _synthetic_heat,
    main,
)

# ----------------------------------------------------------------------
# Constantes del modulo
# ----------------------------------------------------------------------


def test_object_catalog_covers_every_room_type_with_content():
    assert set(OBJECT_CATALOG.keys()) == set(RoomType)
    for items in OBJECT_CATALOG.values():
        assert len(items) > 0
        assert len(set(items)) == len(items)  # sin duplicados


def test_directions_are_the_four_cardinal_unit_deltas():
    assert DIRECTIONS == {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


# ----------------------------------------------------------------------
# Room
# ----------------------------------------------------------------------


def test_room_contains_boundaries():
    room = Room(0, RoomType.KITCHEN, x0=2, y0=3, x1=5, y1=7)
    assert room.contains(2, 3) is True   # esquina superior izq
    assert room.contains(5, 7) is True   # esquina inferior der
    assert room.contains(3, 5) is True   # interior
    assert room.contains(1, 5) is False  # justo fuera por x
    assert room.contains(2, 8) is False  # justo fuera por y


def test_room_center_integer_division():
    assert Room(0, RoomType.BATHROOM, 2, 3, 5, 7).center() == (3, 5)
    assert Room(0, RoomType.BATHROOM, 1, 1, 4, 4).center() == (2, 2)


# ----------------------------------------------------------------------
# HouseWorld: validacion del constructor
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        dict(width=6, height=14),
        dict(width=20, height=6),
        dict(num_rooms=0),
        dict(num_rooms=-1),
        dict(min_room_size=1),
        dict(min_room_size=5, max_room_size=3),
        dict(max_room_size=100),
        dict(object_density=-0.01),
        dict(object_density=1.01),
    ],
)
def test_constructor_rejects_invalid_params(overrides):
    kwargs = dict(width=20, height=14)
    kwargs.update(overrides)
    width, height = kwargs.pop("width"), kwargs.pop("height")
    with pytest.raises(ValueError):
        HouseWorld(width, height, **kwargs)


def test_constructor_accepts_boundary_valid_params():
    # 7x7 es el minimo permitido, y una unica sala 2x2 es la mas pequeña posible.
    world = HouseWorld(7, 7, num_rooms=1, min_room_size=2, max_room_size=2, object_density=0.0, seed=0)
    assert (world.width, world.height) == (7, 7)
    assert len(world.rooms) == 1


# ----------------------------------------------------------------------
# HouseWorld: invariantes de generacion sobre muchas semillas/tamaños
# ----------------------------------------------------------------------

GRID_SIZES = [(7, 7), (12, 9), (20, 14), (30, 20)]
SEEDS = range(15)


@pytest.mark.parametrize("width,height", GRID_SIZES)
@pytest.mark.parametrize("seed", SEEDS)
def test_generated_house_is_fully_connected(width, height, seed):
    world = HouseWorld(width, height, num_rooms=5, min_room_size=2, max_room_size=min(5, width - 3, height - 3), seed=seed)
    start = world.random_free_cell()
    total_floor = sum(
        1 for y in range(1, world.height + 1) for x in range(1, world.width + 1) if world.is_free(x, y)
    )

    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in world.neighbors(*current):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)

    assert len(seen) == total_floor


@pytest.mark.parametrize("seed", SEEDS)
def test_kitchen_and_living_room_never_repeat_but_bedroom_bathroom_may(seed):
    world = HouseWorld(24, 18, num_rooms=6, min_room_size=2, max_room_size=3, seed=seed)
    types = [room.room_type for room in world.rooms]
    assert types.count(RoomType.KITCHEN) <= 1
    assert types.count(RoomType.LIVING_ROOM) <= 1


def test_first_four_rooms_cover_all_types_when_enough_room_fits():
    world = HouseWorld(24, 18, num_rooms=6, min_room_size=2, max_room_size=3, seed=123)
    assert len(world.rooms) == 6
    first_four_types = [room.room_type for room in world.rooms[:4]]
    assert len(set(first_four_types)) == 4
    for room in world.rooms[4:]:
        assert room.room_type in (RoomType.BEDROOM, RoomType.BATHROOM)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_cell_is_exactly_wall_xor_free_and_room_at_is_consistent(seed):
    world = HouseWorld(20, 14, num_rooms=5, seed=seed)
    corridor_found = False
    for y in range(1, world.height + 1):
        for x in range(1, world.width + 1):
            wall = world.is_wall(x, y)
            free = world.is_free(x, y)
            assert wall != free

            room = world.room_at(x, y)
            if wall:
                assert room is None
            if room is not None:
                assert not wall
                assert room.contains(x, y)
            if free and room is None:
                corridor_found = True
    assert corridor_found  # con 5 salas siempre debe haber algun pasillo


def test_outer_border_is_always_wall():
    world = HouseWorld(20, 14, num_rooms=5, seed=1)
    for x in range(1, world.width + 1):
        assert world.is_wall(x, 1)
        assert world.is_wall(x, world.height)
    for y in range(1, world.height + 1):
        assert world.is_wall(1, y)
        assert world.is_wall(world.width, y)


def test_out_of_bounds_cells_are_walls_and_not_free():
    world = HouseWorld(20, 14, seed=0)
    for x, y in [(0, 5), (-3, 5), (21, 5), (5, 0), (5, 15), (1000, 1000)]:
        assert world.is_wall(x, y) is True
        assert world.is_free(x, y) is False
        assert world.room_at(x, y) is None


def test_in_bounds():
    world = HouseWorld(20, 14, seed=0)
    assert world.in_bounds(1, 1) and world.in_bounds(20, 14)
    for x, y in [(0, 5), (5, 0), (21, 5), (5, 15)]:
        assert world.in_bounds(x, y) is False


def test_single_room_has_no_corridor_cells():
    world = HouseWorld(12, 12, num_rooms=1, min_room_size=3, max_room_size=4, seed=0)
    for y in range(1, world.height + 1):
        for x in range(1, world.width + 1):
            if world.is_free(x, y):
                assert world.room_at(x, y) is not None


def test_neighbors_interior_cell_has_all_four_free():
    world = HouseWorld(20, 14, num_rooms=1, min_room_size=4, max_room_size=4, seed=0)
    room = world.rooms[0]
    cx, cy = (room.x0 + room.x1) // 2, (room.y0 + room.y1) // 2
    expected = {(cx + dx, cy + dy) for dx, dy in DIRECTIONS.values()}
    assert set(world.neighbors(cx, cy)) == expected


def test_neighbors_room_corner_has_exactly_two_free_when_isolated():
    world = HouseWorld(20, 14, num_rooms=1, min_room_size=4, max_room_size=4, seed=0)
    room = world.rooms[0]
    result = world.neighbors(room.x0, room.y0)
    assert set(result) == {(room.x0 + 1, room.y0), (room.x0, room.y0 + 1)}


@pytest.mark.parametrize("seed", SEEDS)
def test_all_objects_are_inside_some_room_sorted_and_consistent_with_objects_at(seed):
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=seed)
    items = world.all_objects()

    assert items == sorted(items, key=lambda item: (item[0][1], item[0][0]))
    total_in_dict = sum(len(names) for names in world._objects.values())
    assert len(items) == total_in_dict

    for (x, y), name in items:
        assert name in world.objects_at(x, y)
        room = world.room_at(x, y)
        assert room is not None
        assert name in OBJECT_CATALOG[room.room_type]


def test_objects_at_empty_cell_returns_empty_list():
    world = HouseWorld(20, 14, num_rooms=5, object_density=0.0, seed=0)
    assert world.all_objects() == []
    assert world.objects_at(1, 1) == []


def test_object_density_zero_places_nothing_and_one_places_full_catalog_when_room_fits():
    world_zero = HouseWorld(20, 14, num_rooms=5, object_density=0.0, seed=0)
    assert world_zero.all_objects() == []

    world_full = HouseWorld(20, 14, num_rooms=5, min_room_size=3, max_room_size=5, object_density=1.0, seed=0)
    placed_by_room = {}
    for (x, y), _name in world_full.all_objects():
        room = world_full.room_at(x, y)
        placed_by_room.setdefault(room.room_id, 0)
        placed_by_room[room.room_id] += 1
    for room in world_full.rooms:
        # con density=1.0 y una sala de al menos 3x3=9 celdas, el catalogo
        # completo (maximo 4 objetos, cocina) siempre cabe entero.
        assert placed_by_room.get(room.room_id, 0) == len(OBJECT_CATALOG[room.room_type])


def test_populate_objects_truncates_gracefully_when_room_smaller_than_catalog(monkeypatch):
    world = HouseWorld(9, 9, num_rooms=1, min_room_size=2, max_room_size=2, object_density=0.0, seed=0)
    original = world.rooms[0]
    room_area = (original.x1 - original.x0 + 1) * (original.y1 - original.y0 + 1)
    assert room_area == 4  # sala 2x2, justo el tamaño del catalogo original de cocina

    forced_room = Room(original.room_id, RoomType.KITCHEN, original.x0, original.y0, original.x1, original.y1)
    bigger_catalog = OBJECT_CATALOG[RoomType.KITCHEN] + ("congelador",)
    monkeypatch.setitem(OBJECT_CATALOG, RoomType.KITCHEN, bigger_catalog)

    world._rooms = [forced_room]
    world._objects = {}
    world._populate_objects(1.0)  # 5 objetos a colocar, solo caben 4: no debe lanzar StopIteration

    placed = sum(len(names) for names in world._objects.values())
    assert placed == room_area


def test_random_free_cell_is_always_free():
    world = HouseWorld(20, 14, num_rooms=5, seed=9)
    for _ in range(30):
        assert world.is_free(*world.random_free_cell())


def test_rooms_property_returns_a_copy_not_internal_list():
    world = HouseWorld(20, 14, num_rooms=5, seed=0)
    rooms = world.rooms
    rooms.append("no debería colarse en el mundo real")
    assert len(world.rooms) == 5


# ----------------------------------------------------------------------
# HouseWorld: metodos internos de generacion, probados de forma aislada
# ----------------------------------------------------------------------


def test_overlaps_existing_true_when_within_margin_false_when_far():
    world = HouseWorld(30, 20, num_rooms=1, min_room_size=3, max_room_size=3, seed=0)
    room = world.rooms[0]

    touching_x0 = room.x1 + 1  # a 0 celdas de distancia real, dentro del margen 1
    assert world._overlaps_existing(touching_x0, room.y0, touching_x0 + 2, room.y1, margin=1) is True

    far_x0 = room.x1 + 6
    assert world._overlaps_existing(far_x0, room.y0, far_x0 + 2, room.y1, margin=1) is False


def test_carve_corridor_horizontal_then_vertical_branch(monkeypatch):
    world = HouseWorld(15, 15, num_rooms=1, min_room_size=2, max_room_size=2, seed=0)
    monkeypatch.setattr(world._rng, "random", lambda: 0.1)  # < 0.5
    world._carve_corridor((3, 3), (7, 6))
    for x in range(3, 8):
        assert world.is_free(x, 3)
    for y in range(3, 7):
        assert world.is_free(7, y)


def test_carve_corridor_vertical_then_horizontal_branch(monkeypatch):
    world = HouseWorld(15, 15, num_rooms=1, min_room_size=2, max_room_size=2, seed=0)
    monkeypatch.setattr(world._rng, "random", lambda: 0.9)  # >= 0.5
    world._carve_corridor((3, 3), (7, 6))
    for y in range(3, 7):
        assert world.is_free(3, y)
    for x in range(3, 8):
        assert world.is_free(x, 6)


def test_connect_rooms_with_a_single_room_carves_no_corridor():
    world = HouseWorld(12, 12, num_rooms=1, min_room_size=3, max_room_size=4, seed=0)
    room = world.rooms[0]
    outside_neighbour = (room.x0 - 1, room.y0)
    assert world.is_wall(*outside_neighbour)


def test_next_room_type_pool_is_exhausted_in_declaration_order():
    world = HouseWorld(30, 20, num_rooms=1, min_room_size=2, max_room_size=2, seed=42)
    pool_before = list(world._room_type_pool)
    assert len(pool_before) == 3  # una ya se consumio al crear la primera (unica) sala
    for expected in reversed(pool_before):
        assert world._next_room_type() == expected
    # agotada la pool, siempre repite un tipo "plausible"
    for _ in range(10):
        assert world._next_room_type() in (RoomType.BEDROOM, RoomType.BATHROOM)


# ----------------------------------------------------------------------
# HouseWorld: primitivas de color / texto puras
# ----------------------------------------------------------------------


def test_ansi_helpers_exact_escape_sequences():
    assert HouseWorld._ansi_bg(1, 2, 3) == "\x1b[48;2;1;2;3m"
    assert HouseWorld._ansi_fg(4, 5, 6) == "\x1b[38;2;4;5;6m"
    assert HouseWorld._ansi_reset() == "\x1b[0m"


@pytest.mark.parametrize("t,expected", [(-1.0, 0.0), (0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (2.0, 1.0)])
def test_clamp01(t, expected):
    assert HouseWorld._clamp01(t) == expected


def test_heat_bg_pure_red_at_zero_pure_green_at_one():
    assert HouseWorld._heat_bg(0.0) == (255, 0, 0)
    assert HouseWorld._heat_bg(1.0) == (0, 255, 0)


def test_heat_bg_midpoint_matches_round_formula():
    r, g, b = HouseWorld._heat_bg(0.5)
    assert (r, g, b) == (round(255 * 0.5), round(255 * 0.5), 0)


def test_heat_bg_clamps_out_of_range_t():
    assert HouseWorld._heat_bg(-5.0) == HouseWorld._heat_bg(0.0)
    assert HouseWorld._heat_bg(5.0) == HouseWorld._heat_bg(1.0)


def test_contrast_fg_bright_background_gets_black_text_dark_gets_white():
    assert HouseWorld._contrast_fg((0, 255, 0)) == (0, 0, 0)      # verde puro: claro
    assert HouseWorld._contrast_fg((255, 0, 0)) == (255, 255, 255)  # rojo puro: oscuro (luminancia baja)


@pytest.mark.parametrize(
    "text,width,expected",
    [
        ("", 3, "   "),
        ("R", 3, " R "),
        ("NE", 3, " NE"),
        ("AB", 4, " AB "),
        ("0.125", 7, " 0.125 "),
        ("0.125", 3, "###"),
        ("*", 1, "*"),
    ],
)
def test_fit_text(text, width, expected):
    assert HouseWorld._fit_text(text, width) == expected


# ----------------------------------------------------------------------
# HouseWorld: _resolve_cell_color (todas las ramas de prioridad)
# ----------------------------------------------------------------------


def _resolve(world, x, y, **kwargs):
    defaults = dict(robot_pos=None, path_cells=None, heat=None, heat_range=None, precision=3)
    defaults.update(kwargs)
    return world._resolve_cell_color(x, y, **defaults)


def test_resolve_cell_color_robot_overrides_everything():
    world = HouseWorld(20, 14, seed=0)
    bg, fg, text = _resolve(world, 1, 1, robot_pos=(1, 1), heat={(1, 1): 0.5}, heat_range=(0.0, 1.0))
    assert (bg, fg, text) == (HouseWorld.ROBOT_BG, HouseWorld.ROBOT_FG, "R")


def test_resolve_cell_color_wall_when_no_robot():
    world = HouseWorld(20, 14, seed=0)
    bg, fg, text = _resolve(world, 1, 1)
    assert (bg, fg, text) == (HouseWorld.WALL_COLOR, HouseWorld.WALL_COLOR, "")


def test_resolve_cell_color_heat_overrides_path_and_objects():
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=3)
    (ox, oy), _name = world.all_objects()[0]
    bg, fg, text = _resolve(
        world, ox, oy,
        path_cells={(ox, oy)}, heat={(ox, oy): 0.25}, heat_range=(0.0, 1.0),
    )
    assert text == "0.250"
    assert bg == HouseWorld._heat_bg(0.25)
    assert fg == HouseWorld._contrast_fg(bg)


def test_resolve_cell_color_heat_flat_range_gives_t_zero():
    world = HouseWorld(20, 14, seed=0)
    pos = world.random_free_cell()
    bg, _fg, text = _resolve(world, *pos, heat={pos: 5.0}, heat_range=(5.0, 5.0))
    assert text == "5.000"
    assert bg == HouseWorld._heat_bg(0.0)


def test_resolve_cell_color_path_without_object_shows_asterisk():
    world = HouseWorld(20, 14, num_rooms=5, object_density=0.0, seed=0)
    pos = world.random_free_cell()
    bg, fg, text = _resolve(world, *pos, path_cells={pos})
    assert (bg, fg, text) == (HouseWorld.PATH_COLOR, HouseWorld.PATH_FG, "*")


def test_resolve_cell_color_path_with_object_shows_code_and_asterisk():
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=3)
    (ox, oy), name = world.all_objects()[0]
    bg, fg, text = _resolve(world, ox, oy, path_cells={(ox, oy)})
    assert (bg, fg) == (HouseWorld.PATH_COLOR, HouseWorld.PATH_FG)
    assert text == f"{name[:2].upper()}*"


def test_resolve_cell_color_room_with_object():
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=3)
    (ox, oy), name = world.all_objects()[0]
    room = world.room_at(ox, oy)
    bg, fg, text = _resolve(world, ox, oy)
    assert bg == HouseWorld.ROOM_COLORS[room.room_type]
    assert fg == HouseWorld.OBJECT_FG
    assert text == name[:2].upper()


def test_resolve_cell_color_room_without_object():
    world = HouseWorld(20, 14, num_rooms=5, object_density=0.0, seed=0)
    room = world.rooms[0]
    bg, fg, text = _resolve(world, room.x0, room.y0)
    assert bg == HouseWorld.ROOM_COLORS[room.room_type]
    assert fg == bg
    assert text == ""


def test_resolve_cell_color_corridor_without_object():
    world = HouseWorld(20, 14, num_rooms=5, seed=3)
    corridor_cell = next(
        (x, y)
        for y in range(1, world.height + 1)
        for x in range(1, world.width + 1)
        if world.is_free(x, y) and world.room_at(x, y) is None
    )
    bg, fg, text = _resolve(world, *corridor_cell)
    assert bg == HouseWorld.CORRIDOR_COLOR
    assert fg == bg
    assert text == ""


# ----------------------------------------------------------------------
# HouseWorld: render / print / legend
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kwargs", [dict(cell_width=0), dict(cell_height=0), dict(cell_width=0, cell_height=0)])
def test_render_rejects_non_positive_cell_size(kwargs):
    world = HouseWorld(20, 14, seed=0)
    with pytest.raises(ValueError):
        world.render(**kwargs)


def test_render_show_axes_adds_header_line():
    world = HouseWorld(20, 14, seed=0)
    with_axes = world.render(use_color=False, show_axes=True).split("\n")
    without_axes = world.render(use_color=False, show_axes=False).split("\n")
    assert len(with_axes) == world.height + 1
    assert len(without_axes) == world.height


def test_render_robot_glyph_present_only_when_robot_pos_given():
    world = HouseWorld(20, 14, seed=0)
    robot_pos = world.random_free_cell()
    assert " R " in world.render(robot_pos=robot_pos, use_color=False)
    assert " R " not in world.render(robot_pos=None, use_color=False)


def test_render_use_color_emits_ansi_escapes():
    world = HouseWorld(20, 14, seed=0)
    assert "\x1b[" in world.render(use_color=True)
    assert "\x1b[" not in world.render(use_color=False)


def test_render_path_overlay_plain_and_color():
    world = HouseWorld(20, 14, num_rooms=5, object_density=0.0, seed=0)
    start = world.random_free_cell()
    path = [start] + world.neighbors(*start)[:1]

    plain = world.render(path=path, use_color=False)
    assert "*" in plain

    colored = world.render(path=path, use_color=True)
    assert HouseWorld._ansi_bg(*HouseWorld.PATH_COLOR) in colored


def test_render_heat_overlay_plain_and_color():
    world = HouseWorld(20, 14, seed=0)
    pos = world.random_free_cell()
    heat = {pos: 0.7}

    plain = world.render(heat=heat, use_color=False, cell_width=7)
    assert "0.700" in plain

    colored = world.render(heat=heat, use_color=True, cell_width=7)
    bg = HouseWorld._heat_bg(0.0)  # unico valor -> rango plano -> t=0 -> rojo puro
    assert HouseWorld._ansi_bg(*bg) in colored


def test_render_cell_width_widens_columns():
    world = HouseWorld(20, 14, seed=0)
    narrow = world.render(use_color=False, cell_width=3, show_axes=False).split("\n")[0]
    wide = world.render(use_color=False, cell_width=6, show_axes=False).split("\n")[0]
    assert len(wide) == 2 * len(narrow)


def test_render_cell_height_repeats_wall_symbol_every_subrow_but_object_text_only_once():
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=3)
    (ox, oy), name = world.all_objects()[0]
    lines = world.render(use_color=False, cell_width=3, cell_height=3, show_axes=False).split("\n")

    wall_x, wall_y = 1, 1
    block_start = (wall_y - 1) * 3
    wall_rows = [lines[block_start + i][(wall_x - 1) * 3:(wall_x - 1) * 3 + 3] for i in range(3)]
    assert wall_rows == [" # ", " # ", " # "]  # simbolo solido: se repite en las 3 filas

    obj_block_start = (oy - 1) * 3
    obj_rows = [lines[obj_block_start + i][(ox - 1) * 3:(ox - 1) * 3 + 3] for i in range(3)]
    non_blank = [r for r in obj_rows if r.strip()]
    assert non_blank == [f" {name[:2].upper()}"]  # contenido informativo: solo en la fila central


def test_render_cell_height_even_uses_first_subrow_as_content_row():
    # "R" es un simbolo solido de 1 caracter (como el muro): en modo sin
    # color se repite en todas las subfilas, por eso esta prueba usa un
    # objeto (contenido de 2 caracteres) para ver la fila de contenido real.
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=3)
    (ox, oy), name = world.all_objects()[0]
    lines = world.render(use_color=False, cell_width=3, cell_height=2, show_axes=False).split("\n")
    block_start = (oy - 1) * 2
    col = (ox - 1) * 3
    assert lines[block_start][col:col + 3] == f" {name[:2].upper()}"
    assert lines[block_start + 1][col:col + 3] == "   "


def test_print_writes_render_output_to_stdout(capsys):
    world = HouseWorld(20, 14, seed=0)
    world.print(use_color=False, show_axes=True, cell_width=4)
    captured = capsys.readouterr()
    assert captured.out.rstrip("\n") == world.render(use_color=False, show_axes=True, cell_width=4)


def test_legend_color_vs_plain_and_content():
    world = HouseWorld(20, 14, seed=0)
    colored = world.legend(use_color=True)
    plain = world.legend(use_color=False)

    assert colored.startswith("Leyenda:") and plain.startswith("Leyenda:")
    assert "\x1b[" in colored
    assert "\x1b[" not in plain
    assert "###" in plain and "[R]" in plain
    for room_type in RoomType:
        assert room_type.value in colored
        assert room_type.value in plain


def test_legend_show_path_and_show_heat_flags():
    world = HouseWorld(20, 14, seed=0)
    base = world.legend()
    with_path = world.legend(show_path=True)
    with_heat = world.legend(show_heat=True)
    with_both = world.legend(show_path=True, show_heat=True)

    assert "ruta encontrada" not in base and "mapa de calor" not in base
    assert "ruta encontrada" in with_path and "mapa de calor" not in with_path
    assert "mapa de calor" in with_heat and "ruta encontrada" not in with_heat
    assert "ruta encontrada" in with_both and "mapa de calor" in with_both


# ----------------------------------------------------------------------
# Robot
# ----------------------------------------------------------------------


def test_robot_explicit_start_sets_position():
    world = HouseWorld(20, 14, num_rooms=1, min_room_size=3, max_room_size=3, seed=0)
    room = world.rooms[0]
    robot = Robot(world, start=(room.x0, room.y0))
    assert robot.x == room.x0 and robot.y == room.y0
    assert robot.pos == (room.x0, room.y0)


def test_robot_default_start_picks_a_free_cell():
    world = HouseWorld(20, 14, seed=0)
    robot = Robot(world)
    assert world.is_free(robot.x, robot.y)


def test_robot_invalid_start_on_wall_raises():
    world = HouseWorld(20, 14, seed=0)
    with pytest.raises(ValueError):
        Robot(world, start=(1, 1))  # (1,1) siempre es muro: las salas empiezan en x0,y0 >= 2


def test_wall_contact_and_directional_move_at_an_isolated_room_corner():
    world = HouseWorld(20, 14, num_rooms=1, min_room_size=3, max_room_size=3, seed=0)
    room = world.rooms[0]
    robot = Robot(world, start=(room.x0, room.y0))

    contact = robot.wall_contact()
    assert contact == {"N": True, "S": False, "E": False, "W": True}

    assert robot.move("N") is False
    assert robot.pos == (room.x0, room.y0)
    assert robot.move("W") is False
    assert robot.pos == (room.x0, room.y0)

    assert robot.move("E") is True
    assert robot.pos == (room.x0 + 1, room.y0)


def test_robot_move_stay_never_fails_and_never_moves():
    world = HouseWorld(20, 14, seed=0)
    robot = Robot(world)
    before = robot.pos
    assert robot.move("STAY") is True
    assert robot.pos == before


def test_robot_move_unknown_direction_raises():
    world = HouseWorld(20, 14, seed=0)
    robot = Robot(world)
    with pytest.raises(ValueError):
        robot.move("NE")


def test_detect_objects_radius_zero_vs_one():
    world = HouseWorld(20, 14, num_rooms=5, object_density=1.0, seed=0)
    (ox, oy), obj_name = world.all_objects()[0]

    robot_on_object = Robot(world, start=(ox, oy))
    assert obj_name in robot_on_object.detect_objects(radius=0)

    neighbour = world.neighbors(ox, oy)[0]
    robot_next_door = Robot(world, start=neighbour)
    assert obj_name not in robot_next_door.detect_objects(radius=0)
    assert obj_name in robot_next_door.detect_objects(radius=1)


# ----------------------------------------------------------------------
# CLI: helpers de demo
# ----------------------------------------------------------------------


def test_random_walk_path_starts_at_start_and_stays_connected():
    world = HouseWorld(20, 14, seed=0)
    start = world.random_free_cell()
    rng = __import__("random").Random(1)
    path = _random_walk_path(world, start, 10, rng)

    assert path[0] == start
    assert len(path) <= 11
    for a, b in zip(path, path[1:]):
        assert b in world.neighbors(*a)


def test_synthetic_heat_peaks_at_center_and_covers_only_free_cells():
    world = HouseWorld(20, 14, seed=0)
    center = world.random_free_cell()
    heat = _synthetic_heat(world, center)

    assert heat[center] == 1.0
    assert set(heat.keys()) == {
        (x, y) for y in range(1, world.height + 1) for x in range(1, world.width + 1) if world.is_free(x, y)
    }
    other = next(pos for pos in heat if pos != center)
    ox, oy = other
    cx, cy = center
    assert heat[other] == 1.0 / (1 + abs(ox - cx) + abs(oy - cy))


# ----------------------------------------------------------------------
# CLI: argparse y main()
# ----------------------------------------------------------------------


def test_arg_parser_defaults():
    args = _build_arg_parser().parse_args([])
    assert (args.width, args.height, args.rooms) == (20, 14, 5)
    assert (args.min_room, args.max_room, args.density) == (3, 5, 0.7)
    assert (args.seed, args.no_color, args.walk) == (None, False, 0)
    assert (args.cell_width, args.cell_height) == (3, 1)
    assert (args.demo_path, args.demo_heat) == (0, False)


def test_arg_parser_overrides():
    args = _build_arg_parser().parse_args(
        [
            "--width", "10", "--height", "9", "--rooms", "2",
            "--min-room", "2", "--max-room", "4", "--density", "0.3",
            "--seed", "7", "--no-color", "--walk", "3",
            "--cell-width", "6", "--cell-height", "2",
            "--demo-path", "5", "--demo-heat",
        ]
    )
    assert (args.width, args.height, args.rooms) == (10, 9, 2)
    assert (args.min_room, args.max_room, args.density) == (2, 4, 0.3)
    assert (args.seed, args.no_color, args.walk) == (7, True, 3)
    assert (args.cell_width, args.cell_height) == (6, 2)
    assert (args.demo_path, args.demo_heat) == (5, True)


def test_main_default_run_prints_expected_sections(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["house_world.py", "--seed", "1", "--width", "12", "--height", "9", "--rooms", "2"])
    main()
    out = capsys.readouterr().out
    for expected in ("CasaRobot:", "Leyenda:", "Robot en", "Habitaciones:", "Objetos:"):
        assert expected in out


def test_main_walk_reports_both_moves_and_collisions(monkeypatch, capsys):
    # seed=5 con los valores por defecto (20x14) produce, comprobado
    # manualmente, tanto movimientos validos como colisiones dentro de
    # los primeros 25 pasos aleatorios.
    monkeypatch.setattr(sys, "argv", ["house_world.py", "--seed", "5", "--no-color", "--walk", "25"])
    main()
    out = capsys.readouterr().out
    assert "se mueve" in out
    assert "COLISIÓN" in out


def test_main_demo_path_shows_route_preview(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["house_world.py", "--seed", "2", "--no-color", "--demo-path", "8"])
    main()
    out = capsys.readouterr().out
    assert "Vista previa de overlay de ruta" in out
    assert "ruta encontrada" in out  # de legend(show_path=True)


def test_main_demo_heat_shows_probability_preview(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["house_world.py", "--seed", "2", "--no-color", "--demo-heat"])
    main()
    out = capsys.readouterr().out
    assert "Vista previa de overlay de probabilidad" in out
    assert "mapa de calor" in out  # de legend(show_heat=True)
    assert "1.000" in out  # la celda centro siempre alcanza probabilidad maxima


def test_main_cell_size_flags_are_applied(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["house_world.py", "--seed", "1", "--no-color", "--cell-width", "6", "--rooms", "2"])
    main()
    out = capsys.readouterr().out
    header = out.splitlines()[2]  # linea de cabecera "1  2  3 ..."
    assert len(header) > 6 * 20 * 0.5  # cabecera claramente mas ancha que con cell_width=3 por defecto


def test_main_propagates_invalid_params_as_value_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["house_world.py", "--width", "3", "--height", "3"])
    with pytest.raises(ValueError):
        main()


def test_main_cli_subprocess_smoke():
    script = Path(__file__).with_name("house_world.py")
    result = subprocess.run(
        [
            sys.executable, str(script),
            "--seed", "1", "--width", "9", "--height", "9", "--rooms", "1",
            "--walk", "1", "--demo-path", "3", "--demo-heat", "--no-color",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "CasaRobot:" in result.stdout
    assert "Vista previa de overlay de ruta" in result.stdout
    assert "Vista previa de overlay de probabilidad" in result.stdout
