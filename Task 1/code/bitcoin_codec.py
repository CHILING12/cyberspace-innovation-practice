"""Minimal Bitcoin wire-format, secp256k1, and Script utilities.

This module intentionally uses only the Python standard library so that every
byte and every cryptographic calculation remains inspectable for coursework.
It is not intended to replace a production Bitcoin wallet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import math
import struct
from typing import Any


P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G = (GX, GY)


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256d(data: bytes) -> bytes:
    return sha256(sha256(data))


def hash160(data: bytes) -> bytes:
    return hashlib.new("ripemd160", sha256(data)).digest()


def inv_mod(value: int, modulus: int) -> int:
    return pow(value % modulus, -1, modulus)


def point_add(a: tuple[int, int] | None, b: tuple[int, int] | None) -> tuple[int, int] | None:
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if a == b:
        slope = (3 * x1 * x1) * inv_mod(2 * y1, P) % P
    else:
        slope = (y2 - y1) * inv_mod(x2 - x1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    y3 = (slope * (x1 - x3) - y1) % P
    return x3, y3


def scalar_mult(k: int, point: tuple[int, int] | None = G) -> tuple[int, int] | None:
    if point is None or k % N == 0:
        return None
    if k < 0:
        return scalar_mult(-k, (point[0], (-point[1]) % P))
    result = None
    addend = point
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


def encode_pubkey(point: tuple[int, int], compressed: bool = True) -> bytes:
    x, y = point
    if compressed:
        return bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def decode_pubkey(data: bytes) -> tuple[int, int]:
    if len(data) == 33 and data[0] in (2, 3):
        x = int.from_bytes(data[1:], "big")
        if x >= P:
            raise ValueError("compressed public key x-coordinate is out of range")
        y = pow((pow(x, 3, P) + 7) % P, (P + 1) // 4, P)
        if (y & 1) != (data[0] & 1):
            y = P - y
    elif len(data) == 65 and data[0] == 4:
        x = int.from_bytes(data[1:33], "big")
        y = int.from_bytes(data[33:], "big")
    else:
        raise ValueError("unsupported public-key encoding")
    if x >= P or y >= P or (y * y - x * x * x - 7) % P:
        raise ValueError("point is not on secp256k1")
    return x, y


def rfc6979_nonce(secret: int, digest: bytes) -> int:
    """Generate the RFC6979 HMAC-SHA256 nonce for secp256k1."""
    x = secret.to_bytes(32, "big")
    h1 = (int.from_bytes(digest, "big") % N).to_bytes(32, "big")
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        candidate = int.from_bytes(v, "big")
        if 1 <= candidate < N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def ecdsa_sign(secret: int, digest: bytes) -> tuple[int, int]:
    if not 1 <= secret < N or len(digest) != 32:
        raise ValueError("invalid ECDSA signing input")
    z = int.from_bytes(digest, "big")
    nonce = rfc6979_nonce(secret, digest)
    point = scalar_mult(nonce)
    assert point is not None
    r = point[0] % N
    if r == 0:
        raise RuntimeError("RFC6979 produced an unusable nonce")
    s = inv_mod(nonce, N) * (z + r * secret) % N
    if s == 0:
        raise RuntimeError("RFC6979 produced an unusable signature")
    if s > N // 2:
        s = N - s
    return r, s


def ecdsa_verify(pubkey: bytes, digest: bytes, r: int, s: int) -> bool:
    if len(digest) != 32 or not (1 <= r < N and 1 <= s < N):
        return False
    try:
        public_point = decode_pubkey(pubkey)
    except ValueError:
        return False
    z = int.from_bytes(digest, "big")
    w = inv_mod(s, N)
    result = point_add(scalar_mult(z * w % N), scalar_mult(r * w % N, public_point))
    return result is not None and result[0] % N == r


def der_encode_signature(r: int, s: int) -> bytes:
    def der_int(value: int) -> bytes:
        raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw
        return b"\x02" + bytes([len(raw)]) + raw

    body = der_int(r) + der_int(s)
    return b"\x30" + bytes([len(body)]) + body


def der_decode_signature(data: bytes) -> tuple[int, int]:
    if len(data) < 8 or data[0] != 0x30 or data[1] != len(data) - 2:
        raise ValueError("invalid DER signature sequence")
    if data[2] != 0x02:
        raise ValueError("invalid DER r tag")
    r_len = data[3]
    r_start, r_end = 4, 4 + r_len
    if r_end + 2 > len(data) or data[r_end] != 0x02:
        raise ValueError("invalid DER s tag")
    s_len = data[r_end + 1]
    s_start, s_end = r_end + 2, r_end + 2 + s_len
    if s_end != len(data) or not r_len or not s_len:
        raise ValueError("invalid DER integer length")
    r_raw, s_raw = data[r_start:r_end], data[s_start:s_end]
    for raw in (r_raw, s_raw):
        if raw[0] & 0x80 or (len(raw) > 1 and raw[0] == 0 and not raw[1] & 0x80):
            raise ValueError("non-minimal or negative DER integer")
    return int.from_bytes(r_raw, "big"), int.from_bytes(s_raw, "big")


BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58check(payload: bytes) -> str:
    raw = payload + sha256d(payload)[:4]
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + encoded


BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i, generator in enumerate(generators):
            if (top >> i) & 1:
                chk ^= generator
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def convert_bits(data: bytes, from_bits: int, to_bits: int, pad: bool = True) -> list[int]:
    accumulator = 0
    bits = 0
    result: list[int] = []
    max_value = (1 << to_bits) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            raise ValueError("invalid value for bit conversion")
        accumulator = (accumulator << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((accumulator >> bits) & max_value)
    if pad:
        if bits:
            result.append((accumulator << (to_bits - bits)) & max_value)
    elif bits >= from_bits or ((accumulator << (to_bits - bits)) & max_value):
        raise ValueError("invalid non-zero padding")
    return result


def segwit_address(program: bytes, hrp: str = "tb", version: int = 0) -> str:
    if version != 0 or len(program) not in (20, 32):
        raise ValueError("this coursework wallet supports only witness v0")
    data = [version] + convert_bits(program, 8, 5)
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0] * 6) ^ 1
    checksum = [(polymod >> (5 * (5 - i))) & 31 for i in range(6)]
    return hrp + "1" + "".join(BECH32_CHARSET[x] for x in data + checksum)


def decode_segwit_address(address: str) -> tuple[str, int, bytes]:
    if address.lower() != address and address.upper() != address:
        raise ValueError("mixed-case Bech32 address")
    address = address.lower()
    separator = address.rfind("1")
    if separator < 1 or separator + 7 > len(address):
        raise ValueError("invalid Bech32 separator position")
    hrp = address[:separator]
    try:
        data = [BECH32_CHARSET.index(char) for char in address[separator + 1 :]]
    except ValueError as exc:
        raise ValueError("invalid Bech32 character") from exc
    if _bech32_polymod(_bech32_hrp_expand(hrp) + data) != 1:
        raise ValueError("invalid Bech32 checksum")
    version = data[0]
    converted = convert_bits(bytes(data[1:-6]), 5, 8, pad=False)
    program = bytes(converted)
    if version != 0 or len(program) not in (20, 32):
        raise ValueError("unsupported witness version or program length")
    return hrp, version, program


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("CompactSize cannot be negative")
    if value < 0xFD:
        return bytes([value])
    if value <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", value)
    if value <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", value)
    if value <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + struct.pack("<Q", value)
    raise ValueError("CompactSize is too large")


@dataclass
class Span:
    start: int
    end: int
    name: str
    value: str


class ByteReader:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.pos = offset
        self.spans: list[Span] = []

    def take(self, length: int, name: str, value: str | None = None) -> bytes:
        if length < 0 or self.pos + length > len(self.data):
            raise ValueError(f"truncated data while reading {name} at offset {self.pos}")
        start = self.pos
        raw = self.data[start : start + length]
        self.pos += length
        self.spans.append(Span(start, self.pos, name, value if value is not None else raw.hex()))
        return raw

    def uint32(self, name: str) -> int:
        start = self.pos
        raw = self.take(4, name)
        value = struct.unpack("<I", raw)[0]
        self.spans[-1] = Span(start, self.pos, name, str(value))
        return value

    def uint64(self, name: str) -> int:
        start = self.pos
        raw = self.take(8, name)
        value = struct.unpack("<Q", raw)[0]
        self.spans[-1] = Span(start, self.pos, name, str(value))
        return value

    def varint(self, name: str) -> int:
        start = self.pos
        first = self.take(1, name)[0]
        if first < 0xFD:
            value = first
        else:
            width = {0xFD: 2, 0xFE: 4, 0xFF: 8}[first]
            tail = self.take(width, name + ".payload")
            value = int.from_bytes(tail, "little")
            minimum = {2: 0xFD, 4: 0x10000, 8: 0x100000000}[width]
            if value < minimum:
                raise ValueError(f"non-minimal CompactSize at offset {start}")
            self.spans.pop()
        self.spans[-1] = Span(start, self.pos, name, str(value))
        return value


@dataclass
class TxInput:
    prev_txid: str
    prev_vout: int
    script_sig: bytes
    sequence: int
    witness: list[bytes] = field(default_factory=list)

    def serialize(self) -> bytes:
        return (
            bytes.fromhex(self.prev_txid)[::-1]
            + struct.pack("<I", self.prev_vout)
            + encode_varint(len(self.script_sig))
            + self.script_sig
            + struct.pack("<I", self.sequence)
        )


@dataclass
class TxOutput:
    value: int
    script_pubkey: bytes

    def serialize(self) -> bytes:
        return struct.pack("<Q", self.value) + encode_varint(len(self.script_pubkey)) + self.script_pubkey


@dataclass
class Transaction:
    version: int
    inputs: list[TxInput]
    outputs: list[TxOutput]
    locktime: int
    segwit: bool = False
    spans: list[Span] = field(default_factory=list)
    raw: bytes = b""

    def serialize(self, include_witness: bool = True) -> bytes:
        use_witness = include_witness and self.segwit
        result = struct.pack("<I", self.version)
        if use_witness:
            result += b"\x00\x01"
        result += encode_varint(len(self.inputs))
        result += b"".join(item.serialize() for item in self.inputs)
        result += encode_varint(len(self.outputs))
        result += b"".join(item.serialize() for item in self.outputs)
        if use_witness:
            for txin in self.inputs:
                result += encode_varint(len(txin.witness))
                for item in txin.witness:
                    result += encode_varint(len(item)) + item
        return result + struct.pack("<I", self.locktime)

    @property
    def txid(self) -> str:
        return sha256d(self.serialize(include_witness=False))[::-1].hex()

    @property
    def wtxid(self) -> str:
        return sha256d(self.serialize(include_witness=True))[::-1].hex()

    @property
    def stripped_size(self) -> int:
        return len(self.serialize(include_witness=False))

    @property
    def total_size(self) -> int:
        return len(self.serialize(include_witness=True))

    @property
    def weight(self) -> int:
        return self.stripped_size * 4 + (self.total_size - self.stripped_size)

    @property
    def vsize(self) -> int:
        return math.ceil(self.weight / 4)


def parse_transaction(data: bytes, offset: int = 0, prefix: str = "tx") -> tuple[Transaction, int]:
    reader = ByteReader(data, offset)
    start = offset
    version = reader.uint32(prefix + ".version")
    segwit = data[reader.pos : reader.pos + 2] == b"\x00\x01"
    if segwit:
        reader.take(1, prefix + ".marker", "0 (SegWit marker)")
        reader.take(1, prefix + ".flag", "1 (witness present)")
    input_count = reader.varint(prefix + ".input_count")
    inputs: list[TxInput] = []
    for index in range(input_count):
        item_prefix = f"{prefix}.vin[{index}]"
        prev_hash_raw = reader.take(32, item_prefix + ".prev_txid_le")
        prev_vout = reader.uint32(item_prefix + ".prev_vout")
        script_length = reader.varint(item_prefix + ".script_sig_length")
        script_sig = reader.take(script_length, item_prefix + ".script_sig")
        sequence = reader.uint32(item_prefix + ".sequence")
        inputs.append(TxInput(prev_hash_raw[::-1].hex(), prev_vout, script_sig, sequence))
    output_count = reader.varint(prefix + ".output_count")
    outputs: list[TxOutput] = []
    for index in range(output_count):
        item_prefix = f"{prefix}.vout[{index}]"
        value = reader.uint64(item_prefix + ".value_satoshi")
        script_length = reader.varint(item_prefix + ".script_pubkey_length")
        script_pubkey = reader.take(script_length, item_prefix + ".script_pubkey")
        outputs.append(TxOutput(value, script_pubkey))
    if segwit:
        for input_index, txin in enumerate(inputs):
            item_count = reader.varint(f"{prefix}.vin[{input_index}].witness_count")
            for item_index in range(item_count):
                length = reader.varint(f"{prefix}.vin[{input_index}].witness[{item_index}].length")
                txin.witness.append(
                    reader.take(length, f"{prefix}.vin[{input_index}].witness[{item_index}].data")
                )
    locktime = reader.uint32(prefix + ".locktime")
    tx = Transaction(version, inputs, outputs, locktime, segwit, reader.spans, data[start : reader.pos])
    if tx.raw != tx.serialize(include_witness=True):
        raise AssertionError("transaction reserialization differs from wire bytes")
    return tx, reader.pos


@dataclass
class Block:
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    bits: int
    nonce: int
    transactions: list[Transaction]
    spans: list[Span]
    raw: bytes

    @property
    def header(self) -> bytes:
        return self.raw[:80]

    @property
    def block_hash(self) -> str:
        return sha256d(self.header)[::-1].hex()

    @property
    def computed_merkle_root(self) -> str:
        hashes = [bytes.fromhex(tx.txid)[::-1] for tx in self.transactions]
        if not hashes:
            raise ValueError("block has no transactions")
        while len(hashes) > 1:
            if len(hashes) & 1:
                hashes.append(hashes[-1])
            hashes = [sha256d(hashes[i] + hashes[i + 1]) for i in range(0, len(hashes), 2)]
        return hashes[0][::-1].hex()

    @property
    def target(self) -> int:
        exponent = self.bits >> 24
        coefficient = self.bits & 0x007FFFFF
        return coefficient * (1 << (8 * (exponent - 3)))


def parse_block(data: bytes) -> Block:
    if len(data) < 81:
        raise ValueError("truncated block")
    reader = ByteReader(data)
    version = reader.uint32("block.header.version")
    previous_hash = reader.take(32, "block.header.previous_hash_le")[::-1].hex()
    merkle_root = reader.take(32, "block.header.merkle_root_le")[::-1].hex()
    timestamp = reader.uint32("block.header.timestamp")
    bits = reader.uint32("block.header.bits")
    nonce = reader.uint32("block.header.nonce")
    tx_count = reader.varint("block.transaction_count")
    transactions: list[Transaction] = []
    all_spans = list(reader.spans)
    position = reader.pos
    for index in range(tx_count):
        tx, position = parse_transaction(data, position, f"block.tx[{index}]")
        transactions.append(tx)
        all_spans.extend(tx.spans)
    if position != len(data):
        raise ValueError(f"{len(data) - position} trailing bytes after block")
    return Block(version, previous_hash, merkle_root, timestamp, bits, nonce, transactions, all_spans, data)


def p2wpkh_script(program: bytes) -> bytes:
    if len(program) != 20:
        raise ValueError("P2WPKH program must be 20 bytes")
    return b"\x00\x14" + program


def bip143_sighash_details(
    tx: Transaction, input_index: int, script_code: bytes, value: int
) -> dict[str, bytes]:
    if not 0 <= input_index < len(tx.inputs):
        raise IndexError("input index out of range")
    hash_prevouts = sha256d(
        b"".join(bytes.fromhex(item.prev_txid)[::-1] + struct.pack("<I", item.prev_vout) for item in tx.inputs)
    )
    hash_sequence = sha256d(b"".join(struct.pack("<I", item.sequence) for item in tx.inputs))
    hash_outputs = sha256d(b"".join(item.serialize() for item in tx.outputs))
    txin = tx.inputs[input_index]
    preimage = (
        struct.pack("<I", tx.version)
        + hash_prevouts
        + hash_sequence
        + bytes.fromhex(txin.prev_txid)[::-1]
        + struct.pack("<I", txin.prev_vout)
        + encode_varint(len(script_code))
        + script_code
        + struct.pack("<Q", value)
        + struct.pack("<I", txin.sequence)
        + hash_outputs
        + struct.pack("<I", tx.locktime)
        + struct.pack("<I", 1)
    )
    return {
        "hash_prevouts": hash_prevouts,
        "hash_sequence": hash_sequence,
        "hash_outputs": hash_outputs,
        "preimage": preimage,
        "digest": sha256d(preimage),
    }


def bip143_sighash_all(tx: Transaction, input_index: int, script_code: bytes, value: int) -> bytes:
    return bip143_sighash_details(tx, input_index, script_code, value)["digest"]


def verify_p2wpkh_input(
    tx: Transaction, input_index: int, prevout_script: bytes, prevout_value: int
) -> dict[str, Any]:
    """Execute the P2WPKH-equivalent P2PKH script and return an audit trace."""
    if len(prevout_script) != 22 or prevout_script[:2] != b"\x00\x14":
        raise ValueError("previous output is not P2WPKH")
    witness = tx.inputs[input_index].witness
    if len(witness) != 2:
        raise ValueError("P2WPKH witness must contain signature and public key")
    signature_with_type, public_key = witness
    if not signature_with_type or signature_with_type[-1] != 1:
        raise ValueError("only SIGHASH_ALL is supported")
    r, s = der_decode_signature(signature_with_type[:-1])
    expected_hash = prevout_script[2:]
    script_code = b"\x76\xa9\x14" + expected_hash + b"\x88\xac"
    sighash = bip143_sighash_details(tx, input_index, script_code, prevout_value)
    digest = sighash["digest"]
    stack: list[bytes] = [signature_with_type, public_key]
    trace: list[dict[str, Any]] = []

    def snapshot(operation: str, detail: str) -> None:
        trace.append({"operation": operation, "detail": detail, "stack": [item.hex() for item in stack]})

    snapshot("WITNESS", "initial witness stack: signature then public key")
    stack.append(stack[-1])
    snapshot("OP_DUP", "duplicate public key")
    stack.append(hash160(stack.pop()))
    snapshot("OP_HASH160", "HASH160(public key)")
    stack.append(expected_hash)
    snapshot("PUSH20", "push key hash from witness program")
    right, left = stack.pop(), stack.pop()
    if left != right:
        raise ValueError("OP_EQUALVERIFY failed: public-key hash mismatch")
    snapshot("OP_EQUALVERIFY", "equal key hashes removed")
    public_key_from_stack = stack.pop()
    signature_from_stack = stack.pop()
    verified = ecdsa_verify(public_key_from_stack, digest, r, s)
    stack.append(b"\x01" if verified else b"")
    snapshot("OP_CHECKSIG", f"ECDSA verification result={verified}")
    cleanstack = len(stack) == 1 and stack[-1] not in (b"", b"\x00")
    return {
        "script_type": "P2WPKH",
        "script_code": script_code.hex(),
        "sighash_digest": digest.hex(),
        "hash_prevouts": sighash["hash_prevouts"].hex(),
        "hash_sequence": sighash["hash_sequence"].hex(),
        "hash_outputs": sighash["hash_outputs"].hex(),
        "sighash_preimage": sighash["preimage"].hex(),
        "r": hex(r),
        "s": hex(s),
        "low_s": s <= N // 2,
        "pubkey_hash_matches": hash160(public_key) == expected_hash,
        "ecdsa_valid": verified,
        "cleanstack_success": cleanstack,
        "trace": trace,
    }


def verify_p2wsh_op_true_input(tx: Transaction, input_index: int, prevout_script: bytes) -> dict[str, Any]:
    """Audit the explicit P2WSH(OP_TRUE) authorization used for test funding."""
    if len(prevout_script) != 34 or prevout_script[:2] != b"\x00\x20":
        raise ValueError("previous output is not P2WSH")
    witness = tx.inputs[input_index].witness
    if witness != [b"\x51"]:
        raise ValueError("this audit expects a single OP_TRUE witnessScript")
    witness_script = witness[-1]
    expected_program = prevout_script[2:]
    actual_program = sha256(witness_script)
    program_matches = hmac.compare_digest(actual_program, expected_program)
    stack: list[bytes] = []
    trace = [
        {
            "operation": "WITNESS_SCRIPT",
            "detail": "SHA256(witnessScript) equals the 32-byte witness program",
            "stack": [],
        }
    ]
    if not program_matches:
        raise ValueError("P2WSH witnessScript hash mismatch")
    stack.append(b"\x01")
    trace.append({"operation": "OP_TRUE", "detail": "push script number 1", "stack": ["01"]})
    cleanstack = len(stack) == 1 and stack[-1] == b"\x01"
    return {
        "script_type": "P2WSH(OP_TRUE)",
        "witness_script": witness_script.hex(),
        "witness_program_expected": expected_program.hex(),
        "witness_program_computed": actual_program.hex(),
        "witness_program_matches": program_matches,
        "cleanstack_success": cleanstack,
        "trace": trace,
    }
