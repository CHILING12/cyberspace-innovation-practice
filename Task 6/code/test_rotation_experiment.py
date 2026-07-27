"""Unit tests for the deterministic parts of Task 6."""

from __future__ import annotations

import unittest

from rotation_experiment import (
    DEFAULT_INPUT,
    build_im2col_matrix,
    next_power_of_two,
    rotation_plan,
)


class RotationExperimentTests(unittest.TestCase):
    def test_next_power_of_two(self) -> None:
        self.assertEqual(next_power_of_two(1), 1)
        self.assertEqual(next_power_of_two(8), 8)
        self.assertEqual(next_power_of_two(9), 16)
        with self.assertRaises(ValueError):
            next_power_of_two(0)

    def test_generic_rotation_plan(self) -> None:
        plan = rotation_plan(term_count=9, windows=4)
        self.assertEqual(plan["padded_terms"], 16)
        self.assertEqual(plan["logical_packed_slots"], 64)
        self.assertEqual(plan["rotation_steps"], [32, 16, 8, 4])
        self.assertEqual(plan["implementation_derived_rotation_count"], 4)
        self.assertEqual(plan["model_lower_bound"], 4)
        self.assertTrue(plan["meets_model_lower_bound"])
        self.assertFalse(plan["runtime_instrumented"])

    def test_sparse_rotation_plan(self) -> None:
        plan = rotation_plan(term_count=8, windows=4)
        self.assertEqual(plan["padded_terms"], 8)
        self.assertEqual(plan["logical_packed_slots"], 32)
        self.assertEqual(plan["rotation_steps"], [16, 8, 4])
        self.assertEqual(plan["implementation_derived_rotation_count"], 3)
        self.assertEqual(plan["model_lower_bound"], 3)

    def test_im2col_matrix(self) -> None:
        matrix = build_im2col_matrix(DEFAULT_INPUT)
        self.assertEqual(len(matrix), 4)
        self.assertTrue(all(len(window) == 9 for window in matrix))
        self.assertEqual(
            matrix[0],
            [1.0, 2.0, 3.0, 5.0, 6.0, 7.0, 9.0, 10.0, 11.0],
        )
        self.assertEqual(
            matrix[-1],
            [6.0, 7.0, 8.0, 10.0, 11.0, 12.0, 14.0, 15.0, 16.0],
        )

    def test_invalid_rotation_plan(self) -> None:
        with self.assertRaises(ValueError):
            rotation_plan(term_count=0, windows=4)
        with self.assertRaises(ValueError):
            rotation_plan(term_count=8, windows=0)


if __name__ == "__main__":
    unittest.main()
