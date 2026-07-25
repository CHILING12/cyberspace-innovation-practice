"""Deterministic regression tests for the coursework Bitcoin implementation."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bitcoin_codec import (
    N,
    ByteReader,
    decode_segwit_address,
    der_decode_signature,
    der_encode_signature,
    ecdsa_sign,
    ecdsa_verify,
    encode_pubkey,
    hash160,
    parse_block,
    parse_transaction,
    scalar_mult,
    segwit_address,
    sha256,
    verify_p2wpkh_input,
    verify_p2wsh_op_true_input,
)
from chain_analyzer import write_bit_map


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE = PROJECT_ROOT / "output" / "sample_confirmed"


class BitcoinCodecTests(unittest.TestCase):
    def test_secp256k1_generator_and_ecdsa(self) -> None:
        public_key = encode_pubkey(scalar_mult(1))
        self.assertEqual(
            public_key.hex(),
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )
        digest = sha256(b"network-security-coursework")
        r, s = ecdsa_sign(1, digest)
        self.assertLessEqual(s, N // 2)
        self.assertTrue(ecdsa_verify(public_key, digest, r, s))
        self.assertFalse(ecdsa_verify(public_key, sha256(b"mutated"), r, s))
        self.assertEqual(der_decode_signature(der_encode_signature(r, s)), (r, s))

    def test_bech32_round_trip(self) -> None:
        program = hash160(encode_pubkey(scalar_mult(1)))
        address = segwit_address(program)
        self.assertEqual(address, "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx")
        self.assertEqual(decode_segwit_address(address), ("tb", 0, program))

    def test_compact_size_rejects_non_minimal_encoding(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-minimal"):
            ByteReader(b"\xfd\xfc\x00").varint("bad")

    @unittest.skipUnless(SAMPLE.exists(), "run chain_analyzer.py to obtain the confirmed sample")
    def test_confirmed_transaction_and_script(self) -> None:
        raw = bytes.fromhex((SAMPLE / "transaction.raw.hex").read_text(encoding="ascii"))
        tx, consumed = parse_transaction(raw)
        self.assertEqual(consumed, len(raw))
        self.assertEqual(tx.serialize(), raw)
        self.assertEqual(tx.txid, "d083bf3e9d9eb467f9b1577b5d4b85174cce9d94f4c33f6d872d39e5d08c0689")
        self.assertEqual(tx.wtxid, "7742b336d2d4825c2e5c5e68828c6eccd08a295504cc503c361232a7af569e97")
        result = verify_p2wpkh_input(
            tx,
            0,
            bytes.fromhex("0014fbc7a1586fc3c289af9d07dcf249fbab804e7a50"),
            778_123,
        )
        self.assertTrue(result["ecdsa_valid"])
        self.assertTrue(result["cleanstack_success"])
        self.assertEqual(len(result["trace"]), 6)

    @unittest.skipUnless(SAMPLE.exists(), "run chain_analyzer.py to obtain the confirmed sample")
    def test_complete_block_and_byte_accounting(self) -> None:
        raw = bytes.fromhex((SAMPLE / "block.raw.hex").read_text(encoding="ascii"))
        block = parse_block(raw)
        summary = json.loads((SAMPLE / "block_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(block.block_hash, summary["block_hash_computed"])
        self.assertEqual(block.computed_merkle_root, block.merkle_root)
        self.assertLessEqual(int(block.block_hash, 16), block.target)
        self.assertEqual(len(block.transactions), 41)
        self.assertEqual(sum(span.end - span.start for span in block.spans), len(raw))
        with tempfile.TemporaryDirectory() as directory:
            bit_map = Path(directory) / "bits.txt"
            write_bit_map(bit_map, raw, block.spans)
            self.assertEqual(len(bit_map.read_text(encoding="utf-8").splitlines()), len(raw) + 1)

    def test_p2wsh_op_true_authorization(self) -> None:
        from bitcoin_codec import Transaction, TxInput, TxOutput

        tx = Transaction(
            2,
            [TxInput("00" * 32, 0, b"", 0xFFFFFFFF, [b"\x51"])],
            [TxOutput(1, b"\x51")],
            0,
            segwit=True,
        )
        previous_script = b"\x00\x20" + sha256(b"\x51")
        result = verify_p2wsh_op_true_input(tx, 0, previous_script)
        self.assertTrue(result["witness_program_matches"])
        self.assertTrue(result["cleanstack_success"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
