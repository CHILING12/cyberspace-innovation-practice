"""Create and broadcast a transparent, test-network-only P2WPKH transaction."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from bitcoin_codec import (
    N,
    Transaction,
    TxInput,
    TxOutput,
    base58check,
    bip143_sighash_all,
    der_encode_signature,
    ecdsa_sign,
    encode_pubkey,
    hash160,
    p2wpkh_script,
    scalar_mult,
    segwit_address,
)


API_ROOTS = {
    "mutinynet": "https://mutinynet.com/api",
    "signet": "https://mempool.space/signet/api",
    "testnet": "https://mempool.space/testnet/api",
    "testnet4": "https://mempool.space/testnet4/api",
}


def api_request(url: str, data: bytes | None = None) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl:
        command = [curl, "-sS", "-L", "--retry", "3", "--max-time", "60"]
        if data is not None:
            command += ["-H", "Content-Type: text/plain", "--data-binary", "@-"]
        command.append(url)
        result = subprocess.run(command, input=data, capture_output=True, check=False)
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(f"curl failed for {url}: {result.stderr.decode(errors='replace').strip()}")
    last_error: Exception | None = None
    for attempt in range(1, 4):
        request = urllib.request.Request(url, data=data, headers={"User-Agent": "coursework-byte-auditor/1.0"})
        if data is not None:
            request.add_header("Content-Type", "text/plain")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"network request failed after 3 attempts: {url}: {last_error}")


def create_wallet(path: Path, network: str) -> dict[str, object]:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing wallet: {path}")
    secret = int.from_bytes(os.urandom(32), "big")
    while not 1 <= secret < N:
        secret = int.from_bytes(os.urandom(32), "big")
    point = scalar_mult(secret)
    assert point is not None
    pubkey = encode_pubkey(point)
    program = hash160(pubkey)
    wallet = {
        "warning": "TEST NETWORK KEY ONLY - NEVER SEND MAINNET BITCOIN TO THIS KEY",
        "network": network,
        "private_key_hex": secret.to_bytes(32, "big").hex(),
        "wif_testnet_compressed": base58check(b"\xef" + secret.to_bytes(32, "big") + b"\x01"),
        "public_key_compressed": pubkey.hex(),
        "p2wpkh_program": program.hex(),
        "address": segwit_address(program),
        "created_unix": int(time.time()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wallet, ensure_ascii=False, indent=2), encoding="utf-8")
    return wallet


def load_wallet(path: Path) -> dict[str, object]:
    wallet = json.loads(path.read_text(encoding="utf-8"))
    if wallet.get("network") not in API_ROOTS:
        raise ValueError("unsupported network in wallet")
    return wallet


def list_utxos(wallet: dict[str, object]) -> list[dict[str, object]]:
    root = API_ROOTS[str(wallet["network"])]
    raw = api_request(f"{root}/address/{wallet['address']}/utxo")
    return json.loads(raw)


def build_signed_transaction(
    wallet: dict[str, object],
    utxo: dict[str, object],
    destination_program: bytes,
    send_value: int,
    fee_rate: int,
) -> tuple[Transaction, int]:
    input_value = int(utxo["value"])
    destination_script = p2wpkh_script(destination_program)
    change_script = bytes.fromhex(str(wallet["p2wpkh_program"]))
    change_script = p2wpkh_script(change_script)

    # A 1-input/2-output P2WPKH transaction is normally 141 vbytes. Sign once
    # with a provisional fee, then recompute from the exact DER signature size.
    provisional_fee = 141 * fee_rate
    change_value = input_value - send_value - provisional_fee
    if send_value < 294 or change_value < 294:
        raise ValueError("send value or change would be below the P2WPKH dust threshold")
    tx = Transaction(
        version=2,
        inputs=[TxInput(str(utxo["txid"]), int(utxo["vout"]), b"", 0xFFFFFFFD)],
        outputs=[TxOutput(send_value, destination_script), TxOutput(change_value, change_script)],
        locktime=0,
        segwit=True,
    )
    secret = int(str(wallet["private_key_hex"]), 16)
    pubkey = bytes.fromhex(str(wallet["public_key_compressed"]))
    script_code = b"\x76\xa9\x14" + bytes.fromhex(str(wallet["p2wpkh_program"])) + b"\x88\xac"

    def sign() -> None:
        digest = bip143_sighash_all(tx, 0, script_code, input_value)
        r, s = ecdsa_sign(secret, digest)
        tx.inputs[0].witness = [der_encode_signature(r, s) + b"\x01", pubkey]

    sign()
    exact_fee = tx.vsize * fee_rate
    tx.outputs[1].value = input_value - send_value - exact_fee
    if tx.outputs[1].value < 294:
        raise ValueError("exact change would be below dust")
    sign()
    return tx, exact_fee


def command_new(args: argparse.Namespace) -> None:
    wallet = create_wallet(Path(args.wallet), args.network)
    print(json.dumps({"network": wallet["network"], "address": wallet["address"], "wallet": args.wallet}, indent=2))


def command_status(args: argparse.Namespace) -> None:
    wallet = load_wallet(Path(args.wallet))
    utxos = list_utxos(wallet)
    print(json.dumps({"network": wallet["network"], "address": wallet["address"], "utxos": utxos}, indent=2))


def command_send(args: argparse.Namespace) -> None:
    wallet_path = Path(args.wallet)
    wallet = load_wallet(wallet_path)
    hrp, version, program = __import__("bitcoin_codec").decode_segwit_address(args.destination)
    if hrp != "tb" or version != 0 or len(program) != 20:
        raise ValueError("destination must be a tb1q P2WPKH address")
    utxos = [
        item
        for item in list_utxos(wallet)
        if args.allow_unconfirmed or item.get("status", {}).get("confirmed")
    ]
    if not utxos:
        requirement = "UTXO" if args.allow_unconfirmed else "confirmed UTXO"
        raise RuntimeError(f"no {requirement} is available for this wallet")
    utxo = max(utxos, key=lambda item: int(item["value"]))
    tx, fee = build_signed_transaction(wallet, utxo, program, args.amount, args.fee_rate)
    raw_hex = tx.serialize().hex()
    output = {
        "network": wallet["network"],
        "source_address": wallet["address"],
        "destination_address": args.destination,
        "input": utxo,
        "send_value_satoshi": args.amount,
        "change_value_satoshi": tx.outputs[1].value,
        "fee_satoshi": fee,
        "fee_rate_sat_vbyte": args.fee_rate,
        "txid_local": tx.txid,
        "wtxid_local": tx.wtxid,
        "vsize": tx.vsize,
        "weight": tx.weight,
        "raw_transaction": raw_hex,
    }
    if args.broadcast:
        root = API_ROOTS[str(wallet["network"])]
        returned_txid = api_request(f"{root}/tx", raw_hex.encode("ascii")).decode("ascii").strip()
        if returned_txid != tx.txid:
            raise RuntimeError(f"broadcast service returned unexpected txid {returned_txid}")
        output["broadcast_txid"] = returned_txid
        output["explorer_url"] = f"https://mempool.space/{wallet['network']}/tx/{returned_txid}"
        output["broadcast_unix"] = int(time.time())
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    new = subparsers.add_parser("new", help="generate a test-network-only wallet")
    new.add_argument("--network", choices=sorted(API_ROOTS), default="signet")
    new.add_argument("--wallet", default="data/sender_wallet.json")
    new.set_defaults(func=command_new)
    status = subparsers.add_parser("status", help="query wallet UTXOs")
    status.add_argument("--wallet", default="data/sender_wallet.json")
    status.set_defaults(func=command_status)
    send = subparsers.add_parser("send", help="build and optionally broadcast a P2WPKH transaction")
    send.add_argument("--wallet", default="data/sender_wallet.json")
    send.add_argument("--destination", required=True)
    send.add_argument("--amount", type=int, default=10_000, help="satoshi sent to destination")
    send.add_argument("--fee-rate", type=int, default=2, help="satoshi per virtual byte")
    send.add_argument("--output", default="output/broadcast.json")
    send.add_argument("--broadcast", action="store_true")
    send.add_argument("--allow-unconfirmed", action="store_true", help="allow spending an unconfirmed parent")
    send.set_defaults(func=command_send)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
