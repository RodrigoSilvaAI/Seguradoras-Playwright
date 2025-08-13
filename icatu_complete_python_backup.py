from playwright.sync_api import sync_playwright
import time
import json
import requests
from datetime import datetime, timedelta
import os
import pandas as pd
import psycopg2
import warnings
from urllib.parse import urljoin
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# === CONFIGURAÇÕES ===
@dataclass
class CorretoraConfig:
    nome: str
    usuario: str
    senha: str
    codigo: str = ""

class Config:
    CORRETORAS = {
        'WLG': CorretoraConfig(
            nome="WLG CORRETORA DE SEGUROS EIREL",
            usuario="BACKOFFICE_ICATU",
            senha="TTXWQJPB"
        )
    }
    
    PASTA_DOWNLOAD = "/Users/rodrigosilva/Seguradoras_Playwright"
    DB_URL = "postgresql://neondb_owner:npg_qbP7KJZnjT6e@ep-shy-bar-aevh6icr.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    
    BASE_URL = "https://portalcorretor.icatuseguros.com.br"
    API_BASE = "https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api"

# === CLASSE PRINCIPAL ===
class IcatuExtractor:
    def __init__(self, corretora_config: CorretoraConfig):
        self.config = corretora_config
        self.session = requests.Session()
        self.token = None
        self.page = None
        self.context = None
        
    def setup_browser(self):
        """Configura o browser Playwright"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        
        # Intercepta requests para capturar token
        self.page.on("request", self._intercept_request)
        self.page.on("response", self._intercept_response)
        
    def _intercept_request(self, request):
        """Intercepta requests para capturar Authorization token"""
        auth_header = request.headers.get("authorization")
        if auth_header and not self.token:
            self.token = auth_header
            print(f"🔑 Token capturado: {self.token[:50]}...")
            
    def _intercept_response(self, response):
        """Intercepta responses para debug"""
        if "/api/" in response.url:
            print(f"📡 API Response: {response.status} - {response.url}")
    
    def login(self):
        """Realiza o login no portal"""
        print(f"🔐 Fazendo login para: {self.config.nome}")
        
        self.page.goto(f"{Config.BASE_URL}/casadocorretor/login")

        # Aceitar cookies
        try:
            self.page.wait_for_selector('button#onetrust-accept-btn-handler', timeout=5000)
            self.page.click('button#onetrust-accept-btn-handler')
        except:
            pass

        # Login
        self.page.fill('input[placeholder="Usuário"]', self.config.usuario)
        self.page.fill('input[placeholder="Senha"]', self.config.senha)
        self.page.click('button.dsi-button-primary')
        self.page.wait_for_load_state("networkidle")

        # Seleção da primeira corretora (OUTLIER)
        self.page.wait_for_selector('div.dsi_header-selected-item:has-text("Selecione")')
        self.page.click('div.dsi_header-selected-item:has-text("Selecione")')
        self.page.wait_for_selector('text="OUTLIER CORRETORA LTDA"')
        self.page.click('text="OUTLIER CORRETORA LTDA"')

        # Botão intermediário
        self.page.wait_for_selector('button.dsi-button-link:has-text("Selecionar corretor vinculado a plataforma")')
        self.page.click('button.dsi-button-link:has-text("Selecionar corretor vinculado a plataforma")')

        # Seleção da segunda corretora
        self.page.wait_for_selector('div.dsi_header-selected-item:has-text("Selecione")')
        self.page.click('div.dsi_header-selected-item:has-text("Selecione")')
        self.page.wait_for_selector(f'text="{self.config.nome}"')
        self.page.click(f'text="{self.config.nome}"')

        # Botão final
        self.page.wait_for_selector('button:has-text("Selecionar")')
        self.page.click('button:has-text("Selecionar")')
        self.page.wait_for_load_state("networkidle")
        
        print("✅ Login realizado com sucesso!")

    def _make_api_request(self, method: str, url: str, data: dict = None) -> dict:
        """Faz requisição para API usando o token capturado"""
        headers = {
            'Authorization': self.token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        try:
            if method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na requisição {url}: {e}")
            return None

    def extrair_pagamentos_pendentes(self, callback_status=None) -> List[Dict]:
        """Extrai todos os pagamentos pendentes"""
        print("💰 Extraindo pagamentos pendentes...")
        
        # Navega para página de pendentes
        self.page.goto(f"{Config.BASE_URL}/casadocorretor/meus-clientes/pendentes")
        self.page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # Aguarda token ser capturado
        timeout = 30
        while not self.token and timeout > 0:
            time.sleep(1)
            timeout -= 1
            
        if not self.token:
            raise Exception("❌ Token não foi capturado")

        pagina = 1
        todos_pendentes = []
        
        while True:
            if callback_status:
                callback_status(f"Página {pagina}")
                
            # Dados para buscar lista de pendentes
            post_data = {
                "Pagina": pagina,
                "ItensPorPagina": 100,
                "Ordenacao": "NomeCliente",
                "Crescente": True
            }
            
            # Faz requisição
            url = f"{Config.API_BASE}/RelacionamentoCliente/Tombamento/pendentes"
            response = self._make_api_request('POST', url, post_data)
            
            if not response or not response.get('clientesPendentes'):
                break
                
            clientes_pagina = response['clientesPendentes']
            if not clientes_pagina:
                break
                
            todos_pendentes.extend(clientes_pagina)
            pagina += 1
            
            print(f"📄 Página {pagina-1}: {len(clientes_pagina)} clientes")
            
        print(f"✅ Total de clientes pendentes: {len(todos_pendentes)}")
        return todos_pendentes

    def extrair_detalhes_produtos(self, clientes_pendentes: List[Dict], callback_status=None) -> Dict[str, List[Dict]]:
        """Extrai detalhes dos produtos para cada cliente"""
        print("🔍 Extraindo detalhes dos produtos...")
        
        produtos_por_cliente = {}
        total = len(clientes_pendentes)
        
        for i, pendente in enumerate(clientes_pendentes, 1):
            if callback_status:
                callback_status(f"Produtos {i}/{total}")
                
            cliente_id = pendente['cliente']['id']
            cpf = pendente['cliente']['cpf']
            
            url = f"{Config.API_BASE}/RelacionamentoCliente/Tombamento/clientes/{cliente_id}/produtos"
            params = {"documento": cpf}
            
            # Constrói URL com parâmetros
            full_url = f"{url}?documento={cpf}"
            response = self._make_api_request('GET', full_url)
            
            if response and response.get('produtosCliente'):
                produtos_por_cliente[cliente_id] = response['produtosCliente']['listarProdutos']
            
            # Rate limiting
            if i % 10 == 0:
                time.sleep(0.5)
                
        return produtos_por_cliente

    def extrair_parcelas_detalhadas(self, clientes_pendentes: List[Dict], produtos_por_cliente: Dict, callback_status=None) -> Dict[str, List[Dict]]:
        """Extrai parcelas detalhadas para cada cliente/produto"""
        print("💳 Extraindo parcelas detalhadas...")
        
        parcelas_por_cliente = {}
        total = len(clientes_pendentes)
        
        for i, pendente in enumerate(clientes_pendentes, 1):
            if callback_status:
                callback_status(f"Parcelas {i}/{total}")
                
            cliente_id = pendente['cliente']['id']
            cpf = pendente['cliente']['cpf']
            proposta = pendente['produto']['proposta']
            
            # Encontra produto correspondente
            produtos = produtos_por_cliente.get(cliente_id, [])
            produto = next((p for p in produtos if p['proposta'] == proposta), None)
            
            if not produto:
                continue
                
            # URL para buscar parcelas
            certificado = produto.get('certificadoOfuscado', '')
            linha_negocio = produto.get('linhaNegocio', '')
            
            url = f"{Config.API_BASE}/cobranca/cobrancas/{certificado}/{certificado}/{linha_negocio}/{cpf}"
            response = self._make_api_request('GET', url)
            
            if response and response.get('result'):
                parcelas_por_cliente[cliente_id] = response['result']
            
            # Rate limiting
            if i % 5 == 0:
                time.sleep(0.3)
                
        return parcelas_por_cliente

    def extrair_repiques(self, clientes_pendentes: List[Dict], parcelas_por_cliente: Dict, callback_status=None) -> Dict[str, List[Dict]]:
        """Extrai informações de repiques/tentativas de cobrança"""
        print("🔄 Extraindo informações de repiques...")
        
        repiques_por_chave = {}
        contador = 0
        
        for pendente in clientes_pendentes:
            cliente_id = pendente['cliente']['id']
            cpf = pendente['cliente']['cpf']
            certificado = pendente['produto']['certificado']
            
            parcelas = parcelas_por_cliente.get(cliente_id, [])
            
            for parcela in parcelas:
                contador += 1
                if callback_status:
                    callback_status(f"Repiques {contador}")
                    
                numero_parcela = parcela.get('parcela', '')
                chave = f"{pendente['produto']['proposta']}-{numero_parcela}"
                
                url = f"{Config.API_BASE}/Clientes/{cpf}/informacoes-repique/{certificado}/0"
                params = {"numeroParcela": numero_parcela}
                full_url = f"{url}?numeroParcela={numero_parcela}"
                
                response = self._make_api_request('GET', full_url)
                
                if response and response.get('resultado', {}).get('dadosAdicionais'):
                    repiques_por_chave[chave] = response['resultado']['dadosAdicionais']
                
                # Rate limiting mais agressivo para repiques
                if contador % 3 == 0:
                    time.sleep(0.5)
                    
        return repiques_por_chave

    def processar_dados_pagamentos(self, clientes_pendentes: List[Dict], produtos_por_cliente: Dict) -> List[Dict]:
        """Processa dados dos pagamentos pendentes"""
        print("🔧 Processando dados de pagamentos...")
        
        pagamentos_processados = []
        
        for pendente in clientes_pendentes:
            try:
                cliente_id = pendente['cliente']['id']
                produtos = produtos_por_cliente.get(cliente_id, [])
                proposta = pendente['produto']['proposta']
                
                # Encontra produto correspondente
                produto = next((p for p in produtos if p['proposta'] == proposta), None)
                
                pagamento = {
                    'id': cliente_id,
                    'nome': pendente['cliente']['nome'],
                    'cpf': pendente['cliente'].get('cpf_formatado', ''),
                    'linha_negocio': pendente['produto']['linha_negocio'],
                    'produto': pendente['produto']['nome'],
                    'parcelas_em_aberto': pendente['produto']['qtde_parcelas_abertas'],
                    'forma_pagamento': pendente['produto'].get('forma_pagamento_formatada', ''),
                    'numero_proposta': pendente['produto']['proposta'],
                    'numero_certificado': pendente['produto']['certificado'],
                    'valor_contribuicao': pendente['produto']['valor_parcela'],
                }
                
                if produto:
                    pagamento.update({
                        'situacao_produto': self._format_product_status(produto),
                        'dia_vencimento': produto.get('diaVencimento'),
                        'ultimo_pagamento': self._format_date(produto.get('dataUltimoPagamento')),
                        'proximo_pagamento': self._format_date(produto.get('dataProximoPagamento')),
                        'quantidade_parcelas_pagas': produto.get('quantidadeParcelasPagas'),
                        'quantidade_parcelas_pendentes': produto.get('quantidadeParcelasPendentes'),
                        'periodicidade_pagamentos': produto.get('periodicidadePagamento'),
                        'dias_em_atraso': self._calculate_overdue_days(produto.get('dataProximoPagamento'))
                    })
                
                pagamentos_processados.append(pagamento)
                
            except Exception as e:
                print(f"❌ Erro processando pagamento {pendente.get('cliente', {}).get('id')}: {e}")
                
        return pagamentos_processados

    def processar_dados_parcelas(self, clientes_pendentes: List[Dict], parcelas_por_cliente: Dict, repiques_por_chave: Dict) -> List[Dict]:
        """Processa dados detalhados das parcelas"""
        print("🔧 Processando dados de parcelas...")
        
        parcelas_processadas = []
        
        for pendente in clientes_pendentes:
            try:
                cliente_id = pendente['cliente']['id']
                parcelas = parcelas_por_cliente.get(cliente_id, [])
                
                for parcela in parcelas:
                    chave_repique = f"{pendente['produto']['proposta']}-{parcela.get('parcela', '')}"
                    repiques = repiques_por_chave.get(chave_repique, [])
                    
                    parcela_base = {
                        'id': cliente_id,
                        'nome': pendente['cliente']['nome'],
                        'cpf': pendente['cliente'].get('cpf_formatado', ''),
                        'linha_negocio': pendente['produto']['linha_negocio'],
                        'produto': pendente['produto']['nome'],
                        'numero_parcela': parcela.get('parcela'),
                        'competencia': parcela.get('competencia'),
                        'vencimento_original': self._format_date(parcela.get('vencimentoOriginal')),
                        'vencimento_atual': self._format_date(parcela.get('vencimento')),
                        'contribuicao': parcela.get('valor'),
                    }
                    
                    # Se há repiques, cria uma linha para cada
                    if repiques:
                        for repique in repiques:
                            parcela_com_repique = parcela_base.copy()
                            parcela_com_repique.update({
                                'repique_data': repique.get('data'),
                                'repique_data_tentativa': repique.get('dataTentativa'),
                                'motivo': repique.get('motivo')
                            })
                            parcelas_processadas.append(parcela_com_repique)
                    else:
                        parcelas_processadas.append(parcela_base)
                        
            except Exception as e:
                print(f"❌ Erro processando parcelas {pendente.get('cliente', {}).get('id')}: {e}")
                
        return parcelas_processadas

    def _format_product_status(self, produto: Dict) -> str:
        """Formata status do produto"""
        linha_negocio = produto.get('linhaNegocio')
        
        if linha_negocio == 'PREV':
            situacao = produto.get('situacaoCertificado')
        elif linha_negocio == 'VIDA':
            situacao = produto.get('situacaoTitulo')
        else:
            return ''
            
        return 'Ativo' if situacao == 'A' else 'Cancelado' if situacao == 'C' else situacao

    def _format_date(self, date_str: str) -> str:
        """Formata data para UTC"""
        if not date_str:
            return ''
        try:
            date = datetime.fromisoformat(date_str.replace('Z', ''))
            return date.strftime('%d/%m/%Y')
        except:
            return date_str

    def _calculate_overdue_days(self, next_payment_str: str) -> int:
        """Calcula dias em atraso"""
        if not next_payment_str:
            return 0
            
        try:
            next_payment = datetime.fromisoformat(next_payment_str.replace('Z', ''))
            today = datetime.now()
            
            if next_payment.date() < today.date():
                return (today.date() - next_payment.date()).days
        except:
            pass
            
        return 0

    def salvar_dados_localmente(self, dados: Dict[str, List[Dict]], sufixo: str = "") -> str:
        """Salva dados localmente em Excel e JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_base = f"{self.config.nome.replace(' ', '_')}_{timestamp}{sufixo}"
        
        # Salva JSON
        path_json = os.path.join(Config.PASTA_DOWNLOAD, f"{nome_base}.json")
        with open(path_json, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, default=str)
        
        # Salva Excel
        path_excel = os.path.join(Config.PASTA_DOWNLOAD, f"{nome_base}.xlsx")
        with pd.ExcelWriter(path_excel, engine='openpyxl') as writer:
            for sheet_name, data in dados.items():
                if data:
                    df = pd.DataFrame(data)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"📁 Dados salvos:")
        print(f"   JSON: {path_json}")
        print(f"   Excel: {path_excel}")
        
        return path_excel

    def inserir_no_banco(self, dados: Dict[str, List[Dict]]):
        """Insere dados no banco PostgreSQL"""
        print("💾 Inserindo dados no banco...")
        
        try:
            conn = psycopg2.connect(Config.DB_URL)
            cur = conn.cursor()
            
            # Insere pagamentos pendentes
            if 'Pagamentos Pendentes' in dados:
                for row in dados['Pagamentos Pendentes']:
                    cur.execute("""
                        INSERT INTO defaulters (
                            broker_name, business_line, product_name, certificate_number,
                            client_name, client_cpf, proposal_number, installment_value,
                            product_status, due_day, last_payment, next_payment,
                            paid_installments, pending_installments, payment_frequency,
                            days_overdue, collection_method, open_installments
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (client_cpf, certificate_number) DO UPDATE SET
                            days_overdue = EXCLUDED.days_overdue,
                            next_payment = EXCLUDED.next_payment,
                            pending_installments = EXCLUDED.pending_installments,
                            open_installments = EXCLUDED.open_installments
                    """, (
                        self.config.nome,
                        row.get('linha_negocio', ''),
                        row.get('produto', ''),
                        row.get('numero_certificado', ''),
                        row.get('nome', ''),
                        row.get('cpf', ''),
                        row.get('numero_proposta', ''),
                        row.get('valor_contribuicao', 0),
                        row.get('situacao_produto', ''),
                        row.get('dia_vencimento', ''),
                        row.get('ultimo_pagamento', ''),
                        row.get('proximo_pagamento', ''),
                        row.get('quantidade_parcelas_pagas', 0),
                        row.get('quantidade_parcelas_pendentes', 0),
                        row.get('periodicidade_pagamentos', ''),
                        row.get('dias_em_atraso', 0),
                        row.get('forma_pagamento', ''),
                        row.get('parcelas_em_aberto', 0)
                    ))
            
            # Insere parcelas detalhadas
            if 'Parcelas Pendentes' in dados:
                for row in dados['Parcelas Pendentes']:
                    cur.execute("""
                        INSERT INTO defaulters_detailed (
                            broker_name, client_name, client_cpf, business_line,
                            product_name, installment_number, competency,
                            original_due_date, current_due_date, contribution_value,
                            retry_date, retry_attempt_date, rejection_reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (client_cpf, installment_number, competency) DO UPDATE SET
                            current_due_date = EXCLUDED.current_due_date,
                            retry_date = EXCLUDED.retry_date,
                            retry_attempt_date = EXCLUDED.retry_attempt_date,
                            rejection_reason = EXCLUDED.rejection_reason
                    """, (
                        self.config.nome,
                        row.get('nome', ''),
                        row.get('cpf', ''),
                        row.get('linha_negocio', ''),
                        row.get('produto', ''),
                        row.get('numero_parcela', ''),
                        row.get('competencia', ''),
                        row.get('vencimento_original', ''),
                        row.get('vencimento_atual', ''),
                        row.get('contribuicao', 0),
                        row.get('repique_data', ''),
                        row.get('repique_data_tentativa', ''),
                        row.get('motivo', '')
                    ))
            
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Dados inseridos no banco com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao inserir no banco: {e}")

    def executar_extracao_completa(self):
        """Executa o processo completo de extração"""
        print(f"🚀 Iniciando extração completa para: {self.config.nome}")
        
        status_atual = "Iniciando..."
        def update_status(status):
            nonlocal status_atual
            status_atual = status
            print(f"📊 Status: {status}")
        
        try:
            # 1. Setup browser e login
            self.setup_browser()
            self.login()
            
            # 2. Extração de dados
            clientes_pendentes = self.extrair_pagamentos_pendentes(update_status)
            
            if not clientes_pendentes:
                print("ℹ️ Nenhum cliente pendente encontrado")
                return
            
            produtos_por_cliente = self.extrair_detalhes_produtos(clientes_pendentes, update_status)
            parcelas_por_cliente = self.extrair_parcelas_detalhadas(clientes_pendentes, produtos_por_cliente, update_status)
            repiques_por_chave = self.extrair_repiques(clientes_pendentes, parcelas_por_cliente, update_status)
            
            # 3. Processamento
            pagamentos = self.processar_dados_pagamentos(clientes_pendentes, produtos_por_cliente)
            parcelas = self.processar_dados_parcelas(clientes_pendentes, parcelas_por_cliente, repiques_por_chave)
            
            dados_finais = {
                'Pagamentos Pendentes': pagamentos,
                'Parcelas Pendentes': parcelas
            }
            
            # 4. Salvamento e inserção
            self.salvar_dados_localmente(dados_finais, "_pendentes")
            self.inserir_no_banco(dados_finais)
            
            print(f"🎉 Extração completa finalizada!")
            print(f"   📊 {len(pagamentos)} pagamentos pendentes")
            print(f"   💳 {len(parcelas)} parcelas detalhadas")
            
        except Exception as e:
            print(f"❌ Erro na extração: {e}")
            raise
        finally:
            if self.context:
                self.context.close()
            if hasattr(self, 'playwright'):
                self.playwright.stop()

# === FUNÇÃO PARA MÚLTIPLAS CORRETORAS ===
def processar_multiplas_corretoras():
    """Processa todas as corretoras configuradas"""
    corretoras_processadas = []
    corretoras_com_erro = []
    
    for codigo, config in Config.CORRETORAS.items():
        print(f"\n{'='*60}")
        print(f"🏢 Processando: {config.nome} ({codigo})")
        print(f"{'='*60}")
        
        try:
            extractor = IcatuExtractor(config)
            extractor.executar_extracao_completa()
            corretoras_processadas.append(config.nome)
            print(f"✅ {config.nome} processada com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao processar {config.nome}: {e}")
            corretoras_com_erro.append((config.nome, str(e)))
            
        # Pausa entre corretoras
        if len(Config.CORRETORAS) > 1:
            print("⏳ Aguardando 10 segundos antes da próxima corretora...")
            time.sleep(10)
    
    # Relatório final
    print(f"\n{'='*60}")
    print("📋 RELATÓRIO FINAL")
    print(f"{'='*60}")
    print(f"✅ Processadas com sucesso: {len(corretoras_processadas)}")
    for nome in corretoras_processadas:
        print(f"   • {nome}")
        
    if corretoras_com_erro:
        print(f"\n❌ Com erro: {len(corretoras_com_erro)}")
        for nome, erro in corretoras_com_erro:
            print(f"   • {nome}: {erro}")

# === EXECUÇÃO PRINCIPAL ===
def main():
    """Função principal"""
    print("🏦 Sistema de Extração Icatu - 100% Python")
    print("=" * 50)
    
    # Cria diretório se não existir
    os.makedirs(Config.PASTA_DOWNLOAD, exist_ok=True)
    
    # Processa uma corretora ou todas
    if len(Config.CORRETORAS) == 1:
        config = list(Config.CORRETORAS.values())[0]
        extractor = IcatuExtractor(config)
        extractor.executar_extracao_completa()
    else:
        processar_multiplas_corretoras()

if __name__ == "__main__":
    main()