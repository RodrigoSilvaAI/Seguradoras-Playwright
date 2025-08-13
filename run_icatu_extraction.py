from playwright.sync_api import sync_playwright
import time
import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# === CONFIGURAÇÕES ===
@dataclass
class CorretoraConfig:
    nome: str
    usuario: str
    senha: str

class Config:
    CORRETORAS = {
        'WLG': CorretoraConfig(
            nome="WLG CORRETORA DE SEGUROS EIREL",
            usuario="BACKOFFICE_ICATU",
            senha="TTXWQJPB"
        )
    }
    BASE_URL = "https://portalcorretor.icatuseguros.com.br"
    TOKEN_FILE = "token.txt"

# === CLASSE PRINCIPAL ===
class IcatuTokenSaver:
    def __init__(self, corretora_config: CorretoraConfig):
        self.config = corretora_config
        self.playwright = None
        self.browser = None
        self.page = None
        self.token = None

    def _intercept_token_response(self, response):
        """Intercepta a resposta da API que contém o token de acesso final."""
        if "/api/usuarios/corretoras" in response.url and "/contextualizar" in response.url:
            try:
                json_body = response.json()
                token_value = json_body.get("resultado", {}).get("token")
                if token_value:
                    self.token = f"Bearer {token_value}"
                    print("\n" + "="*60)
                    print(f"🔑 TOKEN FINAL CAPTURADO:")
                    print(self.token)
                    print("="*60 + "\n")
                    # Salva o token no arquivo
                    with open(Config.TOKEN_FILE, 'w') as f:
                        f.write(self.token)
                    print(f"💾 Token salvo em '{Config.TOKEN_FILE}'")
            except Exception as e:
                print(f"⚠️ Erro ao processar a resposta para captura de token: {e}")

    def _full_login(self):
        """Executa o processo de login completo no portal."""
        print(f"🔐 Iniciando login para: {self.config.nome}")
        self.page.goto(f"{Config.BASE_URL}/casadocorretor/login")
        try:
            self.page.locator('button#onetrust-accept-btn-handler').click(timeout=10000)
            print("🍪 Banner de cookies aceito.")
        except Exception:
            print("🍪 Banner de cookies não encontrado ou já aceito.")
        
        self.page.locator('input[placeholder="Usuário"]').fill(self.config.usuario)
        self.page.locator('input[placeholder="Senha"]').fill(self.config.senha)
        self.page.locator('button:has-text("Acessar")').click()
        
        print(" Etapa 1: Selecionando plataforma...")
        self.page.locator('div.dsi_header-selected-item:has-text("Selecione")').click()
        self.page.locator('text="OUTLIER CORRETORA LTDA"').first.click()
        
        print(" Etapa 2: Selecionando corretora vinculada...")
        self.page.locator('button.dsi-button-link:has-text("Selecionar corretor vinculado a plataforma")').click()
        self.page.locator('div.dsi_header-selected-item:has-text("Selecione")').click()
        self.page.locator(f'text="{self.config.nome}"').click()
        self.page.locator('button:has-text("Selecionar")').click()
        
        portal_url = f"{Config.BASE_URL}/casadocorretor/portal"
        print(f"Aguardando redirecionamento para {portal_url}...")
        self.page.wait_for_url(portal_url, timeout=60000)
        print("✅ Login completo e na página do portal!")

    def run_session(self):
        """Inicia uma sessão interativa para capturar e salvar o token."""
        print("🚀 Iniciando sessão de captura de token...")
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=False)
            self.page = self.browser.new_page()
            self.page.on("response", self._intercept_token_response)

            self._full_login()

            print("\n" + "="*60)
            print("⏸️  SESSÃO PAUSADA. O NAVEGADOR ESTÁ SOB SEU CONTROLE.")
            print("O token foi capturado e salvo. Você pode fechar o navegador a qualquer momento.")
            input("Pressione Enter nesta janela para finalizar o script e fechar o navegador...\n")

        except Exception as e:
            print(f"❌ Ocorreu um erro fatal: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.browser: self.browser.close()
            if self.playwright: self.playwright.stop()
            print("🎉 Sessão de captura de token finalizada.")

# === EXECUÇÃO PRINCIPAL ===
def main():
    print("🏦 Sistema de Captura de Token Icatu")
    print("=" * 60)
    config = list(Config.CORRETORAS.values())[0]
    saver = IcatuTokenSaver(config)
    saver.run_session()

if __name__ == "__main__":
    main()
