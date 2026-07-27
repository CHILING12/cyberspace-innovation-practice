"""Regression tests for the encrypted convolution assignment."""

from __future__ import annotations

import unittest

from fhe_convolution import (
    CKKSParameters,
    DEFAULT_INPUT,
    DEFAULT_KERNEL,
    client_decrypt_output,
    client_encrypt_im2col,
    create_client_context,
    load_server_context,
    plaintext_valid_convolution,
    serialize_evaluation_context,
    server_encrypted_convolution,
)


class EncryptedConvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = create_client_context(CKKSParameters())
        cls.server_context = load_server_context(serialize_evaluation_context(cls.client_context))

    def test_plaintext_reference(self) -> None:
        self.assertEqual(
            plaintext_valid_convolution(DEFAULT_INPUT, DEFAULT_KERNEL),
            [[26.0, 31.0], [46.0, 51.0]],
        )

    def test_shape_and_stride_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "shape 4x4"):
            plaintext_valid_convolution([[1.0]], DEFAULT_KERNEL)
        with self.assertRaisesRegex(ValueError, "stride=1"):
            plaintext_valid_convolution(DEFAULT_INPUT, DEFAULT_KERNEL, stride=2)

    def test_server_has_no_secret_key(self) -> None:
        self.assertTrue(self.client_context.is_private())
        self.assertTrue(self.client_context.has_secret_key())
        self.assertFalse(self.server_context.is_private())
        self.assertFalse(self.server_context.has_secret_key())

    def test_encrypted_convolution_matches_reference(self) -> None:
        encrypted_input, windows, _ = client_encrypt_im2col(self.client_context, DEFAULT_INPUT)
        encrypted_output = server_encrypted_convolution(
            self.server_context,
            encrypted_input,
            DEFAULT_KERNEL,
            windows,
        )
        actual = client_decrypt_output(self.client_context, encrypted_output, windows)
        expected = plaintext_valid_convolution(DEFAULT_INPUT, DEFAULT_KERNEL)
        for actual_row, expected_row in zip(actual, expected):
            for actual_value, expected_value in zip(actual_row, expected_row):
                self.assertAlmostEqual(actual_value, expected_value, delta=1e-3)

    def test_ckks_encryption_is_randomized(self) -> None:
        first, _, _ = client_encrypt_im2col(self.client_context, DEFAULT_INPUT)
        second, _, _ = client_encrypt_im2col(self.client_context, DEFAULT_INPUT)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
