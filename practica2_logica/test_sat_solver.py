"""
Tests exhaustivos de sat_solver.py: la infraestructura de logica
proposicional y SAT dada para la Practica 2 (no es TODO, pero si se
rompe, se rompe todo lo que se construye encima). 100% de cobertura de
ramas (ver setup.cfg).

Estrategia, de mas a menos "fuerza bruta":
  - to_cnf: para cada formula de prueba se compara, sobre TODAS las
    asignaciones posibles de sus variables, pl_true(formula) contra
    clauses_satisfied(to_cnf(formula)) -- si difieren en una sola
    asignacion, to_cnf tiene un bug. Se incluyen formulas fijas
    (De Morgan, distribucion, iff/implica anidados) y formulas
    aleatorias generadas con un pequeño generador de arboles.
  - find_model: para instancias pequeñas (hasta ~10 variables) se
    compara el veredicto SAT/UNSAT contra una tabla de verdad completa
    por fuerza bruta, con muchas instancias aleatorias ademas de casos
    estructurados clasicos (pigeonhole, ciclos 2-SAT, cadenas de
    propagacion unitaria, formulas tautologicas, clausula vacia...).
    Cuando hay modelo, se verifica ademas que satisface las clausulas
    de verdad (no nos fiamos de que "no sea None" sea suficiente).
"""

from __future__ import annotations

import itertools
import random
from typing import Dict, List, Sequence

import pytest

from sat_solver import (
    Clause,
    Expr,
    _distribute_or_over_and,
    _eliminate_iff_implies,
    _flatten_clauses,
    _literal_str,
    _push_not_inward,
    clauses_satisfied,
    find_model,
    is_positive,
    negate_literal,
    pl_true,
    symbols,
    to_cnf,
    var_of,
)


# ------------------------------------------------------------------
# Utilidades de test
# ------------------------------------------------------------------


def _all_models(var_names: Sequence[str]):
    for bits in itertools.product((False, True), repeat=len(var_names)):
        yield dict(zip(var_names, bits))


def _brute_force_model(clauses: Sequence[Clause], var_names: Sequence[str]) -> Dict[str, bool] | None:
    for model in _all_models(var_names):
        if clauses_satisfied(clauses, model):
            return model
    return None


def _expr_vars(expr: Expr) -> set:
    if expr.is_symbol():
        return {expr.op}
    out = set()
    for a in expr.args:
        out |= _expr_vars(a)
    return out


def _assert_cnf_equivalent(expr: Expr) -> None:
    """to_cnf(expr) debe ser SAT exactamente en las mismas asignaciones que expr."""
    var_names = sorted(_expr_vars(expr))
    cnf = to_cnf(expr)
    for model in _all_models(var_names):
        assert pl_true(expr, model) == clauses_satisfied(cnf, model), (
            f"to_cnf({expr!r}) difiere de la formula original bajo {model}"
        )


def _random_expr(rng: random.Random, var_names: Sequence[str], depth: int) -> Expr:
    if depth <= 0 or rng.random() < 0.35:
        return Expr(rng.choice(var_names))
    op = rng.choice(["~", "&", "|", ">>", "%"])
    if op == "~":
        return ~_random_expr(rng, var_names, depth - 1)
    a = _random_expr(rng, var_names, depth - 1)
    b = _random_expr(rng, var_names, depth - 1)
    return {"&": lambda: a & b, "|": lambda: a | b, ">>": lambda: a >> b, "%": lambda: a % b}[op]()


def _random_cnf(rng: random.Random, var_names: Sequence[str], n_clauses: int, max_width: int = 3) -> List[Clause]:
    clauses = []
    for _ in range(n_clauses):
        width = rng.randint(1, max_width)
        chosen = rng.sample(var_names, min(width, len(var_names)))
        clauses.append([v if rng.random() < 0.5 else f"-{v}" for v in chosen])
    return clauses


# ------------------------------------------------------------------
# Expr: construccion, operadores, igualdad, repr
# ------------------------------------------------------------------


class TestExpr:
    def test_symbol_is_symbol(self):
        assert Expr("A").is_symbol()

    def test_compound_is_not_symbol(self):
        assert not (Expr("A") & Expr("B")).is_symbol()

    def test_invert_builds_not_node(self):
        e = ~Expr("A")
        assert e.op == "~"
        assert e.args == (Expr("A"),)

    @pytest.mark.parametrize(
        "op,method",
        [("&", "__and__"), ("|", "__or__"), (">>", "__rshift__"), ("%", "__mod__")],
    )
    def test_binary_operators_build_correct_node(self, op, method):
        a, b = Expr("A"), Expr("B")
        e = getattr(a, method)(b)
        assert e.op == op
        assert e.args == (a, b)

    def test_symbols_helper(self):
        a, b, c = symbols("A", "B", "C")
        assert (a, b, c) == (Expr("A"), Expr("B"), Expr("C"))

    def test_symbols_helper_empty(self):
        assert symbols() == ()

    def test_equal_symbols(self):
        assert Expr("A") == Expr("A")

    def test_different_symbols_not_equal(self):
        assert Expr("A") != Expr("B")

    def test_equal_compounds(self):
        assert (Expr("A") & Expr("B")) == (Expr("A") & Expr("B"))

    def test_different_ops_not_equal(self):
        assert (Expr("A") & Expr("B")) != (Expr("A") | Expr("B"))

    def test_not_equal_to_non_expr(self):
        assert Expr("A") != "A"
        assert Expr("A") != 42
        assert Expr("A") != None  # noqa: E711

    def test_hash_consistent_with_equality(self):
        assert hash(Expr("A") & Expr("B")) == hash(Expr("A") & Expr("B"))

    def test_hashable_in_set(self):
        s = {Expr("A"), Expr("A"), Expr("B")}
        assert len(s) == 2

    def test_repr_symbol(self):
        assert repr(Expr("Foo")) == "Foo"

    def test_repr_negation(self):
        assert repr(~Expr("A")) == "~A"

    def test_repr_compound(self):
        assert repr(Expr("A") & Expr("B")) == "(A & B)"


# ------------------------------------------------------------------
# pl_true
# ------------------------------------------------------------------


class TestPlTrue:
    def test_symbol_true(self):
        assert pl_true(Expr("A"), {"A": True}) is True

    def test_symbol_false(self):
        assert pl_true(Expr("A"), {"A": False}) is False

    @pytest.mark.parametrize("a,expected", [(True, False), (False, True)])
    def test_not(self, a, expected):
        assert pl_true(~Expr("A"), {"A": a}) == expected

    @pytest.mark.parametrize(
        "a,b,expected",
        [(False, False, False), (False, True, False), (True, False, False), (True, True, True)],
    )
    def test_and(self, a, b, expected):
        assert pl_true(Expr("A") & Expr("B"), {"A": a, "B": b}) == expected

    @pytest.mark.parametrize(
        "a,b,expected",
        [(False, False, False), (False, True, True), (True, False, True), (True, True, True)],
    )
    def test_or(self, a, b, expected):
        assert pl_true(Expr("A") | Expr("B"), {"A": a, "B": b}) == expected

    @pytest.mark.parametrize(
        "a,b,expected",
        [(False, False, True), (False, True, True), (True, False, False), (True, True, True)],
    )
    def test_implies(self, a, b, expected):
        assert pl_true(Expr("A") >> Expr("B"), {"A": a, "B": b}) == expected

    @pytest.mark.parametrize(
        "a,b,expected",
        [(False, False, True), (False, True, False), (True, False, False), (True, True, True)],
    )
    def test_iff(self, a, b, expected):
        assert pl_true(Expr("A") % Expr("B"), {"A": a, "B": b}) == expected

    def test_nested_expression(self):
        expr = (Expr("A") & Expr("B")) | (~Expr("C"))
        assert pl_true(expr, {"A": True, "B": False, "C": False}) is True
        assert pl_true(expr, {"A": True, "B": False, "C": True}) is False

    def test_unknown_operator_raises(self):
        bogus = Expr("nand", Expr("A"), Expr("B"))
        with pytest.raises(ValueError):
            pl_true(bogus, {"A": True, "B": True})

    def test_missing_variable_raises_keyerror(self):
        with pytest.raises(KeyError):
            pl_true(Expr("A"), {})


# ------------------------------------------------------------------
# to_cnf: equivalencia exacta por fuerza bruta
# ------------------------------------------------------------------


class TestToCnfFixedFormulas:
    def test_single_symbol(self):
        _assert_cnf_equivalent(Expr("A"))

    def test_negated_symbol(self):
        _assert_cnf_equivalent(~Expr("A"))

    def test_double_negation(self):
        _assert_cnf_equivalent(~~Expr("A"))

    def test_triple_negation(self):
        _assert_cnf_equivalent(~~~Expr("A"))

    def test_and(self):
        _assert_cnf_equivalent(Expr("A") & Expr("B"))

    def test_or(self):
        _assert_cnf_equivalent(Expr("A") | Expr("B"))

    def test_implies(self):
        _assert_cnf_equivalent(Expr("A") >> Expr("B"))

    def test_iff(self):
        _assert_cnf_equivalent(Expr("A") % Expr("B"))

    def test_demorgan_not_and(self):
        _assert_cnf_equivalent(~(Expr("A") & Expr("B")))

    def test_demorgan_not_or(self):
        _assert_cnf_equivalent(~(Expr("A") | Expr("B")))

    def test_not_implies(self):
        _assert_cnf_equivalent(~(Expr("A") >> Expr("B")))

    def test_not_iff(self):
        _assert_cnf_equivalent(~(Expr("A") % Expr("B")))

    def test_distribute_or_over_and_left(self):
        A, B, C = symbols("A", "B", "C")
        _assert_cnf_equivalent(A | (B & C))

    def test_distribute_or_over_and_right(self):
        A, B, C = symbols("A", "B", "C")
        _assert_cnf_equivalent((B & C) | A)

    def test_distribute_both_sides_are_conjunctions(self):
        A, B, C, D = symbols("A", "B", "C", "D")
        _assert_cnf_equivalent((A & B) | (C & D))

    def test_nested_iff_chain(self):
        A, B, C = symbols("A", "B", "C")
        _assert_cnf_equivalent((A % B) % C)

    def test_nested_implies_chain(self):
        A, B, C = symbols("A", "B", "C")
        _assert_cnf_equivalent(A >> (B >> C))
        _assert_cnf_equivalent((A >> B) >> C)

    def test_mixed_everything(self):
        A, B, C, D, E = symbols("A", "B", "C", "D", "E")
        _assert_cnf_equivalent((A >> B) % (~C | (D & E)))

    def test_repeated_symbol_across_formula(self):
        A, B = symbols("A", "B")
        _assert_cnf_equivalent((A | B) & (~A % (~B | A)) & (~A | ~B | A))

    def test_tautology(self):
        A = Expr("A")
        _assert_cnf_equivalent(A | ~A)

    def test_contradiction(self):
        A = Expr("A")
        _assert_cnf_equivalent(A & ~A)

    def test_to_cnf_of_unsatisfiable_formula_is_unsat(self):
        A = Expr("A")
        assert find_model(to_cnf(A & ~A)) is None

    def test_to_cnf_of_valid_formula_model_satisfies_original(self):
        A = Expr("A")
        clauses = to_cnf(A | ~A)
        model = find_model(clauses)
        assert model is not None
        assert pl_true(A | ~A, model) is True


class TestToCnfRandomFormulas:
    @pytest.mark.parametrize("seed", range(60))
    def test_random_formula_equivalence(self, seed):
        rng = random.Random(seed)
        n_vars = rng.randint(1, 4)
        var_names = [f"V{i}" for i in range(n_vars)]
        expr = _random_expr(rng, var_names, depth=rng.randint(2, 5))
        _assert_cnf_equivalent(expr)

    @pytest.mark.parametrize("seed", range(30))
    def test_random_formula_find_model_agrees_with_truth_table(self, seed):
        rng = random.Random(seed)
        n_vars = rng.randint(1, 4)
        var_names = [f"V{i}" for i in range(n_vars)]
        expr = _random_expr(rng, var_names, depth=rng.randint(2, 5))

        truly_satisfiable = any(pl_true(expr, m) for m in _all_models(var_names))
        model = find_model(to_cnf(expr))

        assert (model is not None) == truly_satisfiable
        if model is not None:
            assert pl_true(expr, model) is True


# ------------------------------------------------------------------
# Helpers privados de to_cnf: contratos internos (entradas mal
# formadas para las ramas defensivas que el pipeline normal no
# alcanza, pero que siguen siendo parte del contrato de la funcion).
# ------------------------------------------------------------------


class TestCnfPipelineInternals:
    def test_eliminate_unknown_operator_raises(self):
        with pytest.raises(ValueError):
            _eliminate_iff_implies(Expr("xor", Expr("A"), Expr("B")))

    def test_push_not_inward_unexpected_operator_raises(self):
        # se supone llamado tras _eliminate_iff_implies (sin %/>>): si
        # se le pasa una formula con %/>> directamente, debe rechazarla.
        with pytest.raises(ValueError):
            _push_not_inward(Expr(">>", Expr("A"), Expr("B")))

    def test_distribute_unexpected_operator_raises(self):
        with pytest.raises(ValueError):
            _distribute_or_over_and(Expr("%", Expr("A"), Expr("B")))

    def test_literal_str_positive(self):
        assert _literal_str(Expr("A")) == "A"

    def test_literal_str_negative(self):
        assert _literal_str(~Expr("A")) == "-A"

    def test_literal_str_rejects_non_literal(self):
        with pytest.raises(ValueError):
            _literal_str(Expr("A") & Expr("B"))

    def test_literal_str_rejects_double_negation(self):
        with pytest.raises(ValueError):
            _literal_str(~~Expr("A"))

    def test_flatten_clauses_rejects_malformed_or_of_and(self):
        malformed = Expr("|", Expr("&", Expr("A"), Expr("B")), Expr("C"))
        with pytest.raises(ValueError):
            _flatten_clauses(malformed)

    def test_flatten_clauses_rejects_unexpected_top_operator(self):
        with pytest.raises(ValueError):
            _flatten_clauses(Expr(">>", Expr("A"), Expr("B")))


# ------------------------------------------------------------------
# Utilidades sobre literales
# ------------------------------------------------------------------


class TestLiteralUtils:
    def test_var_of_positive(self):
        assert var_of("A") == "A"

    def test_var_of_negative(self):
        assert var_of("-A") == "A"

    def test_is_positive_true(self):
        assert is_positive("A") is True

    def test_is_positive_false(self):
        assert is_positive("-A") is False

    def test_negate_literal_positive_to_negative(self):
        assert negate_literal("A") == "-A"

    def test_negate_literal_negative_to_positive(self):
        assert negate_literal("-A") == "A"

    @pytest.mark.parametrize("lit", ["A", "-A", "LongVarName_1_2_3"])
    def test_negate_literal_is_involution(self, lit):
        assert negate_literal(negate_literal(lit)) == lit


# ------------------------------------------------------------------
# clauses_satisfied
# ------------------------------------------------------------------


class TestClausesSatisfied:
    def test_empty_clause_list_vacuously_true(self):
        assert clauses_satisfied([], {}) is True

    def test_all_clauses_satisfied(self):
        assert clauses_satisfied([["A"], ["-B", "A"]], {"A": True, "B": True}) is True

    def test_one_clause_unsatisfied_short_circuits_false(self):
        assert clauses_satisfied([["A"], ["B"]], {"A": True, "B": False}) is False

    def test_multi_literal_clause_true_if_any_literal_true(self):
        assert clauses_satisfied([["A", "B", "C"]], {"A": False, "B": False, "C": True}) is True

    def test_multi_literal_clause_false_if_all_literals_false(self):
        assert clauses_satisfied([["A", "B"]], {"A": False, "B": False}) is False


# ------------------------------------------------------------------
# find_model: casos limite estructurados
# ------------------------------------------------------------------


class TestFindModelBasics:
    def test_empty_clause_list_is_satisfiable_with_empty_model(self):
        assert find_model([]) == {}

    def test_single_positive_unit_clause(self):
        assert find_model([["A"]]) == {"A": True}

    def test_single_negative_unit_clause(self):
        assert find_model([["-A"]]) == {"A": False}

    def test_direct_contradiction_is_unsat(self):
        assert find_model([["A"], ["-A"]]) is None

    def test_empty_clause_is_immediately_unsat(self):
        assert find_model([[]]) is None

    def test_empty_clause_among_satisfiable_ones_is_still_unsat(self):
        assert find_model([["A"], []]) is None

    def test_two_literal_clause_alone_is_satisfiable(self):
        model = find_model([["A", "B"]])
        assert model is not None
        assert clauses_satisfied([["A", "B"]], model)

    def test_repeated_literal_within_clause(self):
        assert find_model([["A", "A"]]) == {"A": True}

    def test_duplicate_clauses_same_result_as_single(self):
        assert find_model([["A"], ["A"]]) == {"A": True}

    def test_tautological_clause_is_satisfiable(self):
        model = find_model([["A", "-A"]])
        assert model is not None
        assert clauses_satisfied([["A", "-A"]], model)

    def test_tautological_clause_combined_with_forcing_unit(self):
        model = find_model([["A", "-A"], ["B"]])
        assert model == {"A": True, "B": True} or model == {"A": False, "B": True}

    def test_unit_propagation_cascade_all_forced_true(self):
        clauses = [["A"], ["-A", "B"], ["-B", "C"]]
        assert find_model(clauses) == {"A": True, "B": True, "C": True}

    def test_unit_propagation_cascade_detects_contradiction(self):
        # A fuerza B, B fuerza C, y C fuerza -A: contradice el A unitario inicial.
        clauses = [["A"], ["-A", "B"], ["-B", "C"], ["-C", "-A"]]
        assert find_model(clauses) is None

    def test_disconnected_components_both_satisfiable(self):
        clauses = [["A"], ["-B"], ["C"], ["-D"]]
        model = find_model(clauses)
        assert model == {"A": True, "B": False, "C": True, "D": False}

    def test_one_unsat_component_makes_everything_unsat(self):
        # {A,B} es trivialmente satisfacible; {C,D} es contradictorio.
        clauses = [["A"], ["B"], ["C"], ["-C"]]
        assert find_model(clauses) is None

    def test_returned_model_covers_every_clause_variable(self):
        clauses = [["A", "B"], ["-B", "C"], ["-C", "D"]]
        model = find_model(clauses)
        assert set(model.keys()) == {"A", "B", "C", "D"}

    def test_model_actually_satisfies_clauses_not_just_non_none(self):
        clauses = [["A", "B", "C"], ["-A", "D"], ["-B", "-D"], ["C", "-C", "A"]]
        model = find_model(clauses)
        assert model is not None
        assert clauses_satisfied(clauses, model)


class TestFindModelRequiresBacktracking:
    def test_unsat_requires_trying_both_branch_values(self):
        clauses = [
            ["A", "B"],
            ["A", "-B"],
            ["-A", "B"],
            ["-A", "-B"],
        ]

        assert find_model(clauses) is None

    def test_sat_requires_backtracking_from_first_branch_value(self):
        clauses = [
            ["A", "B"],
            ["-A", "-B"],
            ["-A", "B"],
        ]

        model = find_model(clauses)

        assert model == {"A": False, "B": True}


class TestFindModelBacktrackingBranches:
    def test_first_branch_fails_and_second_succeeds(self):
        clauses = [
            ["A", "C"],
            ["A", "D"],
            ["-A", "B"],
            ["-A", "-B"],
        ]

        model = find_model(clauses)

        assert model is not None
        assert model["A"] is False
        assert clauses_satisfied(clauses, model)

    def test_both_branches_fail(self):
        clauses = [
            ["A", "B"],
            ["A", "-B"],
            ["-A", "B"],
            ["-A", "-B"],
        ]

        assert find_model(clauses) is None


class TestFindModelPigeonhole:
    @staticmethod
    def _pigeonhole_clauses(pigeons: int, holes: int) -> List[Clause]:
        def sym(p, h):
            return f"P_{p}_{h}"

        clauses: List[Clause] = []
        for p in range(pigeons):
            clauses.append([sym(p, h) for h in range(holes)])  # cada paloma, algun agujero
        for h in range(holes):
            for p1, p2 in itertools.combinations(range(pigeons), 2):  # a lo sumo una paloma por agujero
                clauses.append([f"-{sym(p1, h)}", f"-{sym(p2, h)}"])
        return clauses

    def test_more_pigeons_than_holes_is_unsat(self):
        clauses = self._pigeonhole_clauses(pigeons=3, holes=2)
        assert find_model(clauses) is None

    def test_four_pigeons_three_holes_is_unsat(self):
        clauses = self._pigeonhole_clauses(pigeons=4, holes=3)
        assert find_model(clauses) is None

    def test_pigeons_fit_exactly_is_sat(self):
        clauses = self._pigeonhole_clauses(pigeons=3, holes=3)
        model = find_model(clauses)
        assert model is not None
        assert clauses_satisfied(clauses, model)

    def test_fewer_pigeons_than_holes_is_sat(self):
        clauses = self._pigeonhole_clauses(pigeons=2, holes=4)
        model = find_model(clauses)
        assert model is not None
        assert clauses_satisfied(clauses, model)


class TestFindModelTwoSatCycle:
    def test_implication_cycle_forces_contradiction(self):
        # A; A->B; B->C; C->-A. La cadena obliga A=False, contradiciendo el A unitario.
        clauses = [["A"], ["-A", "B"], ["-B", "C"], ["-C", "-A"]]
        assert find_model(clauses) is None

    def test_implication_cycle_without_forcing_unit_is_sat(self):
        # Mismo ciclo de implicaciones, pero sin forzar A: A=False,B=False,C=False lo satisface.
        clauses = [["-A", "B"], ["-B", "C"], ["-C", "-A"]]
        model = find_model(clauses)
        assert model is not None
        assert clauses_satisfied(clauses, model)


class TestFindModelHornChain:
    def test_horn_chain_resolved_purely_by_propagation(self):
        # Cadena de implicaciones tipo Horn: se resuelve entera sin ramificar.
        clauses = [["A"], ["-A", "B"], ["-B", "C"], ["-C", "D"], ["-D", "E"]]
        assert find_model(clauses) == {"A": True, "B": True, "C": True, "D": True, "E": True}


class TestFindModelStress:
    @pytest.mark.parametrize("seed", range(80))
    def test_random_small_cnf_matches_brute_force(self, seed):
        rng = random.Random(seed)
        n_vars = rng.randint(1, 9)
        var_names = [f"V{i}" for i in range(n_vars)]
        n_clauses = rng.randint(0, 22)
        clauses = _random_cnf(rng, var_names, n_clauses, max_width=3)

        expected_model = _brute_force_model(clauses, var_names)
        result = find_model(clauses)

        assert (result is not None) == (expected_model is not None), (
            f"seed={seed}: clauses={clauses} -- veredicto SAT/UNSAT no coincide con fuerza bruta"
        )
        if result is not None:
            assert clauses_satisfied(clauses, result)

    def test_larger_underconstrained_instance_is_fast_and_correct(self):
        rng = random.Random(12345)
        n_vars = 80
        var_names = [f"V{i}" for i in range(n_vars)]
        clauses = _random_cnf(rng, var_names, n_clauses=120, max_width=3)
        result = find_model(clauses)
        if result is not None:
            assert clauses_satisfied(clauses, result)
