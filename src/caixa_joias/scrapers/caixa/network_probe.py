from __future__ import annotations
from playwright.sync_api import sync_playwright
URL = 'https://vitrinedejoias.caixa.gov.br/Paginas/Busca.aspx'

def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        def log_response(response):
            content_type = response.headers.get('content-type', '')
            if any(token in content_type for token in ['json', 'pdf', 'application']):
                print(response.status, content_type, response.url)
        page.on('response', log_response)
        page.goto(URL, wait_until='networkidle')
        input('Faça buscas manualmente e pressione Enter para fechar...')
        browser.close()
if __name__ == '__main__': main()
