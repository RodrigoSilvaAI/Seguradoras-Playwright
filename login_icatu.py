from playwright.sync_api import sync_playwright
import time
from datetime import datetime
import os
import pandas as pd
import psycopg2
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# === CONFIGURAÇÕES ===
USUARIO = "BACKOFFICE_ICATU"
SENHA = "TTXWQJPB"
CORRETORA = "WLG CORRETORA DE SEGUROS EIREL"
PASTA_DOWNLOAD = "/Users/rodrigosilva/Seguradoras_Playwright"
DB_URL = "postgresql://neondb_owner:npg_qbP7KJZnjT6e@ep-shy-bar-aevh6icr.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"

# === INSERE DADOS NO SUPABASE ===
def inserir_dados_supabase(path_arquivo, corretora):
    df = pd.read_excel(path_arquivo)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO defaulters (
                broker_name,
                business_line,
                product_name,
                certificate_number,
                client_name,
                original_due_date,
                current_due_date,
                competency,
                collection_method,
                installment_value,
                client_cpf,
                phone1,
                phone2
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            corretora,
            row.get("Linha de Negócio", "").strip(),
            row.get("Nome Produto", "").strip(),
            str(row.get("Número Certificado", "")).strip(),
            row.get("Nome Cliente", "").strip(),
            str(row.get("Dia do Vencimento Original", "")).strip(),
            str(row.get("Dia de Vencimento Atual", "")).strip(),
            str(row.get("Competência", "")).strip(),
            row.get("Forma de Cobrança", "").strip(),
            float(row.get("Valor Parcela", 0) or 0),
            str(row.get("CPF Cliente", "")).strip(),
            str(row.get("Telefone 1", "")).strip(),
            str(row.get("Telefone 2", "")).strip()
        ))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Dados inseridos no Supabase com sucesso.")

# === FUNÇÃO PRINCIPAL ===
def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto("https://portalcorretor.icatuseguros.com.br/casadocorretor/login")

        # Aceitar cookies
        try:
            page.wait_for_selector('button#onetrust-accept-btn-handler', timeout=5000)
            page.click('button#onetrust-accept-btn-handler')
        except:
            print("Cookies já aceitos ou botão não apareceu.")

        # Login
        page.fill('input[placeholder="Usuário"]', USUARIO)
        page.fill('input[placeholder="Senha"]', SENHA)
        page.click('button.dsi-button-primary')
        page.wait_for_load_state("networkidle")

        # Seleção da primeira corretora (OUTLIER)
        page.wait_for_selector('div.dsi_header-selected-item:has-text("Selecione")')
        page.click('div.dsi_header-selected-item:has-text("Selecione")')
        page.wait_for_selector('text="OUTLIER CORRETORA LTDA"')
        page.click('text="OUTLIER CORRETORA LTDA"')

        # Botão intermediário
        page.wait_for_selector('button.dsi-button-link:has-text("Selecionar corretor vinculado a plataforma")')
        page.click('button.dsi-button-link:has-text("Selecionar corretor vinculado a plataforma")')

        # Seleção da segunda corretora (ALL)
        page.wait_for_selector('div.dsi_header-selected-item:has-text("Selecione")')
        page.click('div.dsi_header-selected-item:has-text("Selecione")')
        page.wait_for_selector(f'text="{CORRETORA}"')
        page.click(f'text="{CORRETORA}"')

        # Botão final
        page.wait_for_selector('button:has-text("Selecionar")')
        page.click('button:has-text("Selecionar")')
        page.wait_for_load_state("networkidle")

        # Navegar até: Clientes > Pendentes de Pagamento
        page.wait_for_selector('span.dsi_submenu-txt:has-text("Clientes")')
        page.click('span.dsi_submenu-txt:has-text("Clientes")')
        time.sleep(1)
        page.wait_for_selector('div.dsi_subitem_menu_item:has-text("Pendentes de Pagamento")')
        page.click('div.dsi_subitem_menu_item:has-text("Pendentes de Pagamento")')

        # Espera e clica no botão de exportar (span mais interno)
        page.wait_for_selector('span:has-text("Exportar para xslx")')
        with page.expect_download() as download_info:
            page.click('span:has-text("Exportar para xslx")')
        download = download_info.value

        # Renomeia e salva
        nome_arquivo = f"{CORRETORA.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        path_final = os.path.join(PASTA_DOWNLOAD, nome_arquivo)
        download.save_as(path_final)
        print(f"📁 Arquivo salvo em: {path_final}")

        browser.close()

        # Importa os dados no banco
        inserir_dados_supabase(path_final, CORRETORA)

# === EXECUTA ===
if __name__ == "__main__":
    main()
