from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright
STATE_PATH = Path('storage_state.json')

def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(STATE_PATH) if STATE_PATH.exists() else None)
        page = context.new_page()
        def log_response(response):
            content_type = response.headers.get('content-type', '')
            if any(token in content_type for token in ['json', 'application']):
                print(response.status, content_type, response.url)
        page.on('response', log_response)
        page.goto('https://minerandojoias.com.br', wait_until='networkidle')
        input('Faça login/navegue e pressione Enter para salvar sessão...')
        context.storage_state(path=str(STATE_PATH))
        browser.close()
if __name__ == '__main__': main()
