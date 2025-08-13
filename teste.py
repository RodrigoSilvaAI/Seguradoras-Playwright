from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://portalcorretor.icatuseguros.com.br/casadocorretor/login")
    print(page.title())
    browser.close()

