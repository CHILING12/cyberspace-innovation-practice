"""Fetch and independently audit one Bitcoin transaction and one whole block."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from bitcoin_codec import (
    Block,
    Span,
    parse_block,
    parse_transaction,
    verify_p2wpkh_input,
    verify_p2wsh_op_true_input,
)


API_ROOTS = {
    "mutinynet": "https://mutinynet.com/api",
    "signet": "https://mempool.space/signet/api",
    "testnet": "https://mempool.space/testnet/api",
    "testnet4": "https://mempool.space/testnet4/api",
}


def api_get(root: str, path: str) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl:
        result = subprocess.run(
            [curl, "-sS", "-L", "--retry", "3", "--max-time", "60", root + path],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(
            f"curl failed for {path}: {result.stderr.decode(errors='replace').strip()}"
        )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        request = urllib.request.Request(root + path, headers={"User-Agent": "coursework-byte-auditor/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {path}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"network request failed after 3 attempts for {path}: {last_error}")


def write_bit_map(path: Path, raw: bytes, spans: list[Span]) -> None:
    labels = ["UNCLAIMED"] * len(raw)
    for span in spans:
        if not (0 <= span.start <= span.end <= len(raw)):
            raise ValueError(f"span outside byte array: {span}")
        for offset in range(span.start, span.end):
            if labels[offset] != "UNCLAIMED":
                raise ValueError(f"overlapping span at byte {offset}: {labels[offset]} and {span.name}")
            labels[offset] = span.name
    missing = [index for index, label in enumerate(labels) if label == "UNCLAIMED"]
    if missing:
        raise ValueError(f"{len(missing)} bytes were not assigned to a protocol field")
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("offset_dec offset_hex byte_hex bits       field\n")
        for offset, value in enumerate(raw):
            handle.write(f"{offset:10d} 0x{offset:08x} {value:02x}       {value:08b} {labels[offset]}\n")


def write_spans(path: Path, raw: bytes, spans: list[Span]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["start", "end_exclusive", "length", "field", "wire_hex", "interpreted_value"])
        for span in spans:
            writer.writerow([span.start, span.end, span.end - span.start, span.name, raw[span.start:span.end].hex(), span.value])


def block_summary(block: Block) -> dict[str, object]:
    target_ok = int.from_bytes(bytes.fromhex(block.block_hash), "big") <= block.target
    return {
        "block_hash_computed": block.block_hash,
        "version": block.version,
        "previous_hash": block.previous_hash,
        "merkle_root_header": block.merkle_root,
        "merkle_root_computed": block.computed_merkle_root,
        "merkle_root_valid": block.merkle_root == block.computed_merkle_root,
        "timestamp": block.timestamp,
        "timestamp_utc": datetime.fromtimestamp(block.timestamp, timezone.utc).isoformat(),
        "bits_hex": f"0x{block.bits:08x}",
        "target_hex": f"{block.target:064x}",
        "nonce": block.nonce,
        "proof_of_work_valid": target_ok,
        "transaction_count": len(block.transactions),
        "block_size_bytes": len(block.raw),
        "all_bytes_accounted": sum(span.end - span.start for span in block.spans) == len(block.raw),
    }


def analyze(network: str, txid: str, block_hash: str | None, output_dir: Path) -> dict[str, object]:
    root = API_ROOTS[network]
    output_dir.mkdir(parents=True, exist_ok=True)
    tx_raw = bytes.fromhex(api_get(root, f"/tx/{txid}/hex").decode("ascii").strip())
    tx, consumed = parse_transaction(tx_raw)
    if consumed != len(tx_raw) or tx.txid != txid:
        raise ValueError("transaction parse or txid cross-check failed")
    tx_info = json.loads(api_get(root, f"/tx/{txid}"))
    if block_hash is None:
        block_hash = tx_info.get("status", {}).get("block_hash")
    if not block_hash:
        raise ValueError("transaction is unconfirmed; pass --block-hash to audit a complete block")

    script_audits: list[dict[str, object]] = []
    for index, txin in enumerate(tx.inputs):
        prev_tx = json.loads(api_get(root, f"/tx/{txin.prev_txid}"))
        prevout = prev_tx["vout"][txin.prev_vout]
        prev_script = bytes.fromhex(prevout["scriptpubkey"])
        if len(prev_script) == 22 and prev_script[:2] == b"\x00\x14":
            result = verify_p2wpkh_input(tx, index, prev_script, int(prevout["value"]))
        elif len(prev_script) == 34 and prev_script[:2] == b"\x00\x20" and txin.witness == [b"\x51"]:
            result = verify_p2wsh_op_true_input(tx, index, prev_script)
        else:
            continue
        if result:
            result.update(
                {
                    "input_index": index,
                    "prev_txid": txin.prev_txid,
                    "prev_vout": txin.prev_vout,
                    "prevout_value_satoshi": int(prevout["value"]),
                    "prevout_script_pubkey": prev_script.hex(),
                }
            )
            script_audits.append(result)

    block_raw = api_get(root, f"/block/{block_hash}/raw")
    block = parse_block(block_raw)
    summary = block_summary(block)
    if block.block_hash != block_hash:
        raise ValueError("computed block hash does not match requested hash")
    if not summary["merkle_root_valid"] or not summary["proof_of_work_valid"]:
        raise ValueError("block cryptographic validation failed")

    transaction_summary = {
        "network": network,
        "txid_requested": txid,
        "txid_computed": tx.txid,
        "wtxid_computed": tx.wtxid,
        "segwit": tx.segwit,
        "version": tx.version,
        "input_count": len(tx.inputs),
        "output_count": len(tx.outputs),
        "locktime": tx.locktime,
        "total_size_bytes": tx.total_size,
        "stripped_size_bytes": tx.stripped_size,
        "weight_units": tx.weight,
        "virtual_size_bytes": tx.vsize,
        "all_bytes_accounted": sum(span.end - span.start for span in tx.spans) == len(tx_raw),
        "status_from_api": tx_info.get("status"),
        "outputs": [
            {"index": index, "value_satoshi": item.value, "script_pubkey": item.script_pubkey.hex()}
            for index, item in enumerate(tx.outputs)
        ],
    }

    (output_dir / "transaction.raw.hex").write_text(tx_raw.hex() + "\n", encoding="ascii")
    (output_dir / "block.raw.hex").write_text(block_raw.hex() + "\n", encoding="ascii")
    (output_dir / "transaction_summary.json").write_text(
        json.dumps(transaction_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "script_audit.json").write_text(
        json.dumps(script_audits, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "block_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_bit_map(output_dir / "transaction_bits.txt", tx_raw, tx.spans)
    write_bit_map(output_dir / "block_bits.txt", block_raw, block.spans)
    write_spans(output_dir / "transaction_fields.csv", tx_raw, tx.spans)
    write_spans(output_dir / "block_fields.csv", block_raw, block.spans)
    with (output_dir / "block_transaction_index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["index", "txid", "wtxid", "segwit", "size", "stripped_size", "weight", "vsize"])
        for index, item in enumerate(block.transactions):
            writer.writerow([index, item.txid, item.wtxid, item.segwit, item.total_size, item.stripped_size, item.weight, item.vsize])

    final = {"transaction": transaction_summary, "script_audits": script_audits, "block": summary}
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return final


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--network", choices=sorted(API_ROOTS), default="signet")
    result.add_argument("--txid", required=True)
    result.add_argument("--block-hash")
    result.add_argument("--output", default="output")
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    analyze(args.network, args.txid, args.block_hash, Path(args.output))
