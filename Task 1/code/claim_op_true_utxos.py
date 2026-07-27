"""Spend explicitly public P2WSH(OP_TRUE) Testnet4 outputs into the course wallet.

The locking script is witness-v0 SHA256(0x51), where 0x51 is OP_TRUE.  Supplying
0x51 as the witness script is therefore the complete, publicly authorized
unlocking condition.  No third-party private key or signature is involved.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from bitcoin_codec import Transaction, TxInput, TxOutput, p2wpkh_script, sha256
from wallet_tool import API_ROOTS, api_request, load_wallet


WITNESS_SCRIPT = b"\x51"  # OP_TRUE
WITNESS_PROGRAM = sha256(WITNESS_SCRIPT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet", default="data/testnet4_sender_wallet.json")
    parser.add_argument("--inputs", type=int, default=5)
    parser.add_argument("--output-value", type=int, default=1000)
    parser.add_argument("--output", default="output/testnet4_op_true_funding.json")
    parser.add_argument("--broadcast", action="store_true")
    args = parser.parse_args()

    wallet = load_wallet(Path(args.wallet))
    if wallet["network"] != "testnet4":
        raise ValueError("the public OP_TRUE outputs used here are on Testnet4")
    root = API_ROOTS["testnet4"]
    op_true_address = __import__("bitcoin_codec").segwit_address(WITNESS_PROGRAM)
    utxos = json.loads(api_request(f"{root}/address/{op_true_address}/utxo"))
    confirmed = [item for item in utxos if item.get("status", {}).get("confirmed")]
    if len(confirmed) < args.inputs:
        raise RuntimeError(f"need {args.inputs} confirmed OP_TRUE UTXOs, found {len(confirmed)}")
    selected = confirmed[: args.inputs]
    inputs = [TxInput(item["txid"], int(item["vout"]), b"", 0xFFFFFFFF, [WITNESS_SCRIPT]) for item in selected]
    destination = p2wpkh_script(bytes.fromhex(str(wallet["p2wpkh_program"])))
    tx = Transaction(2, inputs, [TxOutput(args.output_value, destination)], 0, segwit=True)
    input_total = sum(int(item["value"]) for item in selected)
    fee = input_total - args.output_value
    if fee <= 0:
        raise ValueError("output value leaves no transaction fee")
    result: dict[str, object] = {
        "network": "testnet4",
        "authorization": "P2WSH witness program SHA256(OP_TRUE); witnessScript=OP_TRUE",
        "op_true_address": op_true_address,
        "witness_script_hex": WITNESS_SCRIPT.hex(),
        "witness_program_hex": WITNESS_PROGRAM.hex(),
        "selected_utxos": selected,
        "input_total_satoshi": input_total,
        "destination_address": wallet["address"],
        "output_value_satoshi": args.output_value,
        "fee_satoshi": fee,
        "fee_rate_sat_vbyte": fee / tx.vsize,
        "txid_local": tx.txid,
        "wtxid_local": tx.wtxid,
        "size": tx.total_size,
        "weight": tx.weight,
        "vsize": tx.vsize,
        "raw_transaction": tx.serialize().hex(),
    }
    if args.broadcast:
        returned = api_request(f"{root}/tx", tx.serialize().hex().encode("ascii")).decode("ascii").strip()
        if returned != tx.txid:
            raise RuntimeError(f"broadcast service returned unexpected txid {returned}")
        result.update(
            {
                "broadcast_txid": returned,
                "broadcast_unix": int(time.time()),
                "explorer_url": f"https://mempool.space/testnet4/tx/{returned}",
            }
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
