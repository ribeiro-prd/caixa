from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://vitrinedejoias.caixa.gov.br/Paginas/Busca.aspx"
OUT = Path("data/raw/caixa/debug/resultados_network_urls.txt")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        def log_response(response):
            url = response.url
            if "servicebus2.caixa.gov.br" not in url:
                return

            line = f"{response.status} {response.request.method} {url}"
            if line in seen:
                return

            seen.add(line)
            print(line)
            with OUT.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

        page.on("response", log_response)
        page.goto(URL, wait_until="networkidle")

        print("\nManual steps:")
        print("1. Tipo de Busca = Resultado de Leilões")
        print("2. Select SP / SAO PAULO")
        print("3. Test periods around 2026-05-21 and 2026-05-22")
        print("4. Open result details/download files if available")
        input("\nPress Enter after you finish clicking around...")
        browser.close()


if __name__ == "__main__":
    main()