"""
Infraestructura de logica proposicional y SAT para la Practica 2 (CasaRobot).

Todo lo que hay en este fichero esta DADO (no es TODO de ninguna
pregunta): la practica consiste en modelar RobotPhysics con estas
piezas, no en reimplementarlas. Se mantiene en un fichero aparte de
practica2.py para que ese fichero se pueda centrar en la practica.

Sin dependencias externas: no se usa pycosat ni ninguna libreria de SAT.
`find_model` es un solver DPLL propio (propagacion unitaria + rama por
variable mas frecuente) -- validado con margen para los tamanios de esta
practica: una casa 16x11 con un plan de longitud 21 se resuelve en
~1.2s. Ver test_sat_solver.py para su validacion exhaustiva.

Dos capas, pensadas para usos distintos:
  - Expr/to_cnf: algebra simbolica con operadores de Python (~,&,|,>>,%),
    solo se usa en el calentamiento de la Pregunta 1. Convertir formulas
    grandes a CNF via to_cnf es caro; el resto de la practica construye
    clausulas directamente.
  - find_model: opera sobre clausulas ya en CNF, representadas como
    List[List[str]] (cada clausula, una lista de literales; un literal
    negado se escribe con un "-" delante, p.ej. "-At_3_2_0").
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

Literal = str  # "Simbolo" (positivo) o "-Simbolo" (negado)
Clause = List[Literal]
Model = Dict[str, bool]


# ------------------------------------------------------------------
# Expr y to_cnf
# ------------------------------------------------------------------


class Expr:
    """
    Formula proposicional. Una hoja (simbolo) es Expr('Nombre'); una
    formula compuesta es Expr(op, *args) con op en {'~','&','|','>>','%'}.
    Los operadores de Python construyen la formula: ~a, a&b, a|b, a>>b, a%b.
    """

    def __init__(self, op: str, *args: "Expr") -> None:
        self.op = op
        self.args = args

    def is_symbol(self) -> bool:
        return len(self.args) == 0

    def __invert__(self) -> "Expr":
        return Expr("~", self)

    def __and__(self, other: "Expr") -> "Expr":
        return Expr("&", self, other)

    def __or__(self, other: "Expr") -> "Expr":
        return Expr("|", self, other)

    def __rshift__(self, other: "Expr") -> "Expr":
        return Expr(">>", self, other)

    def __mod__(self, other: "Expr") -> "Expr":
        return Expr("%", self, other)

    def __eq__(self, other: object) -> bool:
        return isinstance(
            other, Expr) and self.op == other.op and self.args == other.args

    def __hash__(self) -> int:
        return hash((self.op, self.args))

    def __repr__(self) -> str:
        if self.is_symbol():
            return self.op
        if self.op == "~":
            return f"~{self.args[0]!r}"
        return "(" + f" {self.op} ".join(repr(a) for a in self.args) + ")"


def symbols(*names: str) -> Tuple[Expr, ...]:
    """Azucar sintactico: symbols('A','B','C') -> (Expr('A'), Expr('B'), Expr('C'))."""
    return tuple(Expr(n) for n in names)


def pl_true(expr: Expr, model: Model) -> bool:
    """Evalua `expr` (forma general, no CNF) bajo `model`."""
    if expr.is_symbol():
        return model[expr.op]
    if expr.op == "~":
        return not pl_true(expr.args[0], model)
    if expr.op == "&":
        return pl_true(expr.args[0], model) and pl_true(expr.args[1], model)
    if expr.op == "|":
        return pl_true(expr.args[0], model) or pl_true(expr.args[1], model)
    if expr.op == ">>":
        return (
            not pl_true(
                expr.args[0],
                model)) or pl_true(
            expr.args[1],
            model)
    if expr.op == "%":
        return pl_true(expr.args[0], model) == pl_true(expr.args[1], model)
    raise ValueError(f"Operador desconocido: {expr.op!r}")


def _eliminate_iff_implies(e: Expr) -> Expr:
    if e.is_symbol():
        return e
    args = [_eliminate_iff_implies(a) for a in e.args]
    if e.op == "%":
        a, b = args
        return (~a | b) & (~b | a)
    if e.op == ">>":
        a, b = args
        return ~a | b
    if e.op == "~":
        return ~args[0]
    if e.op == "&":
        return args[0] & args[1]
    if e.op == "|":
        return args[0] | args[1]
    raise ValueError(f"Operador desconocido: {e.op!r}")


def _push_not_inward(e: Expr, negate: bool = False) -> Expr:
    if e.is_symbol():
        return Expr("~", e) if negate else e
    if e.op == "~":
        return _push_not_inward(e.args[0], not negate)
    if e.op in ("&", "|"):
        new_op = {"&": "|", "|": "&"}[e.op] if negate else e.op
        return Expr(new_op, *(_push_not_inward(a, negate) for a in e.args))
    raise ValueError(f"Operador inesperado tras eliminar %/>>: {e.op!r}")


def _distribute_or_over_and(e: Expr) -> Expr:
    if e.is_symbol() or e.op == "~":
        return e
    if e.op == "&":
        a, b = (_distribute_or_over_and(x) for x in e.args)
        return a & b
    if e.op == "|":
        a, b = (_distribute_or_over_and(x) for x in e.args)
        if not a.is_symbol() and a.op == "&":
            return _distribute_or_over_and((a.args[0] | b) & (a.args[1] | b))
        if not b.is_symbol() and b.op == "&":
            return _distribute_or_over_and((a | b.args[0]) & (a | b.args[1]))
        return a | b
    raise ValueError(f"Operador inesperado: {e.op!r}")


def _literal_str(e: Expr) -> str:
    if e.is_symbol():
        return e.op
    if e.op == "~" and e.args[0].is_symbol():
        return f"-{e.args[0].op}"
    raise ValueError(f"No es un literal: {e!r}")


def _flatten_clauses(e: Expr) -> List[Clause]:
    if e.is_symbol() or e.op == "~":
        return [[_literal_str(e)]]
    if e.op == "&":
        return _flatten_clauses(e.args[0]) + _flatten_clauses(e.args[1])
    if e.op == "|":
        def collect(x: Expr) -> Clause:
            if x.is_symbol() or x.op == "~":
                return [_literal_str(x)]
            if x.op == "|":
                return collect(x.args[0]) + collect(x.args[1])
            raise ValueError(f"Clausula mal formada: {x!r}")
        return [collect(e)]
    raise ValueError(f"Operador inesperado en forma final: {e.op!r}")


def to_cnf(expr: Expr) -> List[Clause]:
    """
    Convierte una formula arbitraria en una lista de clausulas (CNF),
    mediante el proceso estandar: eliminar %/>>, empujar las negaciones
    hasta las hojas (De Morgan), distribuir OR sobre AND, y aplanar.
    """
    e = _eliminate_iff_implies(expr)
    e = _push_not_inward(e)
    e = _distribute_or_over_and(e)
    return _flatten_clauses(e)


# ------------------------------------------------------------------
# Utilidades sobre literales en forma de texto
# ------------------------------------------------------------------


def var_of(lit: Literal) -> str:
    """"-X" -> "X"; "X" -> "X"."""
    return lit[1:] if lit.startswith("-") else lit


def is_positive(lit: Literal) -> bool:
    return not lit.startswith("-")


def negate_literal(lit: Literal) -> Literal:
    """"X" -> "-X"; "-X" -> "X"."""
    return lit[1:] if lit.startswith("-") else f"-{lit}"


# ------------------------------------------------------------------
# Solver SAT (DPLL)
# ------------------------------------------------------------------


def find_model(clauses: Sequence[Clause]) -> Optional[Model]:
    """
    Busca un modelo mediante DPLL con watched literals.

    La API publica no cambia: `find_model(clauses)`.

    Se mantiene el orden de ramificacion temporal del solver original:
    se elige la primera variable sin asignar segun el orden de aparicion
    en la CNF. La mejora principal esta en la propagacion: en lugar de
    recorrer todas las clausulas repetidamente, se revisan solo las
    clausulas afectadas por un literal que acaba de hacerse falso.

    La polaridad que se prueba primero se elige segun la frecuencia
    global de aparicion de cada variable. Esto solo cambia el orden de
    exploracion; ambas ramas siguen siendo exploradas.
    """
    # ---------------------------------------------------------------
    # Variables y conversion a enteros.
    # ---------------------------------------------------------------

    if not clauses:
        return {}

    for clause in clauses:
        if not clause:
            return None

    var_names: List[str] = []
    var_index: Dict[str, int] = {}

    for clause in clauses:
        for lit in clause:
            name = var_of(lit)
            if name not in var_index:
                var_index[name] = len(var_names) + 1
                var_names.append(name)

    n = len(var_names)

    int_clauses: List[List[int]] = []

    for clause in clauses:
        int_clause = []

        for lit in clause:
            var = var_index[var_of(lit)]
            int_clause.append(var if is_positive(lit) else -var)

        int_clauses.append(int_clause)

    # ---------------------------------------------------------------
    # Asignacion:
    #   0  -> sin asignar
    #   1  -> True
    #   -1 -> False
    #
    # El indice 0 no se utiliza.
    # ---------------------------------------------------------------

    assignment = [0] * (n + 1)

    # Trail de variables asignadas.
    trail: List[int] = []

    # Indice de la siguiente asignacion pendiente de propagar.
    qhead = 0

    # ---------------------------------------------------------------
    # Watched literals.
    #
    # Cada clausula mantiene dos literales observados. Cuando uno de
    # ellos se hace falso, solo hay que revisar las clausulas que lo
    # estaban observando.
    # ---------------------------------------------------------------

    watch_lists: Dict[int, List[int]] = defaultdict(list)
    watch_a: List[int] = []
    watch_b: List[int] = []

    for clause_id, clause in enumerate(int_clauses):
        watch_a.append(0)
        watch_b.append(0)

        watch_lists[clause[0]].append(clause_id)

        if len(clause) > 1:
            watch_b[clause_id] = 1
            watch_lists[clause[1]].append(clause_id)

    # ---------------------------------------------------------------
    # Polaridad preferida.
    #
    # No cambia la correccion: solo determina que rama se prueba
    # primero.
    # ---------------------------------------------------------------

    positive_count = [0] * (n + 1)
    negative_count = [0] * (n + 1)

    for clause in int_clauses:
        for lit in clause:
            var = abs(lit)
            if lit > 0:
                positive_count[var] += 1
            else:
                negative_count[var] += 1

    def literal_value(lit: int) -> int:
        """1 si es True, -1 si es False, 0 si esta sin asignar."""
        value = assignment[abs(lit)]

        if value == 0:
            return 0

        return value if lit > 0 else -value

    def assign_literal(lit: int) -> bool:
        """
        Asigna un literal.

        Devuelve False si contradice una asignacion existente.
        """
        var = abs(lit)
        value = 1 if lit > 0 else -1

        current = assignment[var]

        if current == 0:
            assignment[var] = value
            trail.append(var)
            return True

        return current == value

    def propagate() -> bool:
        """
        Propagacion unitaria usando watched literals.

        Solo se inspeccionan las clausulas cuyo literal observado acaba
        de hacerse falso.
        """
        nonlocal qhead

        while qhead < len(trail):
            var = trail[qhead]
            qhead += 1

            value = assignment[var]
            false_lit = -var if value == 1 else var

            pending = watch_lists[false_lit]
            i = 0

            while i < len(pending):
                clause_id = pending[i]
                clause = int_clauses[clause_id]

                a = watch_a[clause_id]
                b = watch_b[clause_id]

                if clause[a] == false_lit:
                    false_index = a
                    other_index = b
                else:
                    false_index = b
                    other_index = a

                other_lit = clause[other_index]

                # El otro literal observado satisface la clausula.
                if literal_value(other_lit) == 1:
                    i += 1
                    continue

                # Intentar mover el watch a otro literal que no sea falso.
                replacement = None

                for candidate_index, candidate in enumerate(clause):
                    if candidate_index == false_index:
                        continue
                    if candidate_index == other_index:
                        continue
                    if literal_value(candidate) != -1:
                        replacement = candidate_index
                        break

                if replacement is not None:
                    if false_index == a:
                        watch_a[clause_id] = replacement
                    else:
                        watch_b[clause_id] = replacement

                    # Quitar la clausula de esta watch-list y añadirla
                    # a la lista del nuevo literal observado.
                    pending[i] = pending[-1]
                    pending.pop()
                    watch_lists[clause[replacement]].append(clause_id)
                    continue

                # No hay otro literal disponible. La clausula es:
                #   - conflictiva si el otro watch es falso;
                #   - unitaria si el otro watch esta sin asignar.
                other_value = literal_value(other_lit)

                if other_value == -1:
                    return False

                if not assign_literal(other_lit):  # pragma: no cover -- no alcanzable con estado valido
                    return False

                i += 1

        return True

    def undo_to(trail_size: int) -> None:
        """Deshace las asignaciones posteriores a trail_size."""
        nonlocal qhead

        while len(trail) > trail_size:
            var = trail.pop()
            assignment[var] = 0

        # Todo lo anterior a trail_size ya estaba propagado al entrar
        # en la rama. Las asignaciones posteriores se deben reprocesar
        # si se vuelven a crear en otra rama.
        qhead = min(qhead, trail_size)

    def pick_branch_variable() -> Optional[int]:
        """
        Mantiene el orden temporal del solver original.

        Las variables se almacenan en el orden de primera aparicion en
        la CNF, que en esta practica coincide con t=0, t=1, t=2, ...
        """
        for var in range(1, n + 1):
            if assignment[var] == 0:
                return var

        return None

    def preferred_value(var: int) -> int:
        """Devuelve la polaridad que se probara primero."""
        if positive_count[var] >= negative_count[var]:
            return 1

        return -1

    def backtrack() -> bool:
        """
        DPLL con backtracking cronologico.
        """
        if not propagate():
            return False

        branch_var = pick_branch_variable()

        if branch_var is None:
            return True

        trail_size = len(trail)
        first = preferred_value(branch_var)

        # Primera rama
        if assign_literal(branch_var if first == 1 else -branch_var):  # pragma: no branch
            if backtrack():
                return True

        undo_to(trail_size)

        # Segunda rama
        if assign_literal(-branch_var if first == 1 else branch_var):  # pragma: no branch
            if backtrack():
                return True

        undo_to(trail_size)
        return False

    # Las clausulas unitarias deben entrar en el trail antes de empezar
    # la propagacion normal.
    for clause in int_clauses:
        if len(clause) == 1:
            if not assign_literal(clause[0]):
                return None

    if not backtrack():
        return None

    model = {
        var_names[var - 1]: assignment[var] == 1
        for var in range(1, n + 1)
    }

    # Comprobacion defensiva: nunca devolver un modelo incorrecto.
    if not clauses_satisfied(clauses, model):  # pragma: no cover -- modelo incorrecto
        raise RuntimeError(
            "Error interno del solver SAT: el modelo no satisface "
            "todas las clausulas."
        )

    return model


def clauses_satisfied(clauses: Sequence[Clause], model: Model) -> bool:
    """Comprueba independientemente que `model` satisface todas las `clauses`."""
    return all(any((model[var_of(lit)]) == is_positive(lit)
               for lit in clause) for clause in clauses)
