"""Capture explorer evidence for the two transactions broadcast by this project.

This optional helper requires Playwright and a locally installed Edge/Chromium.
It does not participate in transaction construction or validation.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES = PROJECT_ROOT / "output" / "figures"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
TRANSACTIONS = {
    "testnet4_funding_explorer.png": "4aa330ae4ecf52c82f38d22149b2b7da79f928e1cdad47bb33b553c093a25f7a",
    "testnet4_signed_explorer.png": "ad00f80a9c85264ebf3ca4299d61cca06efba0487223d4e6caa9d9e58e9ac105",
}


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(EDGE) if EDGE.exists() else None)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        for filename, txid in TRANSACTIONS.items():
            last_error = None
            for attempt in range(3):
                try:
                    page.goto(f"https://mempool.space/testnet4/tx/{txid}", wait_until="domcontentloaded", timeout=60_000)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        page.wait_for_timeout(2_000)
            if last_error is not None:
                raise last_error
            page.wait_for_timeout(8_000)
            page.screenshot(path=str(FIGURES / filename), full_page=False)
            print(f"captured {txid} -> {filename}")
        browser.close()


if __name__ == "__main__":
    main()
