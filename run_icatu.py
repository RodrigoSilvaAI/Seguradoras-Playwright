#!/usr/bin/env python3
"""
Script de Execução Simplificado - Sistema Icatu
Execute: python run_icatu.py
"""

import os
import sys
from datetime import datetime

# Adiciona o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from icatu_complete_python import IcatuExtractor, Config, CorretoraConfig
    from utils import setup_inicial, IcatuSetup, IcatuAnalytics
except ImportError as e:
    print(f"❌ Erro importando módulos: {e}")
    print("Certifique-se de que todos os arquivos estão no mesmo diretório")
    sys.exit(1)

# === CONFIGURAÇÕES RÁPIDAS ===
# Edite aqui suas configurações
CONFIGURACOES = {
    'DB_URL': "postgresql://neondb_owner:npg_qbP7KJZnjT6e@ep-shy-bar-aevh6icr.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require",
    'PASTA_DOWNLOAD': "/Users/rodrigosilva/Seguradoras_Playwright",
    'CORRETORAS': {
        'WLG': {
            'nome': "WLG CORRETORA DE SEGUROS EIREL",
            'usuario': "BACKOFFICE_ICATU", 
            'senha': "TTXWQJPB"
        },
        # Adicione mais corretoras aqui conforme necessário
        # 'OUTRA': {
        #     'nome': "NOME DA OUTRA CORRETORA",
        #     'usuario': "USUARIO",
        #     'senha': "SENHA"
        # }
    }
}

def verificar_primeiro_uso():
    """Verifica se é a primeira execução e faz setup"""
    setup_flag = os.path.join(os.path.dirname(__file__), '.setup_done')
    
    if not os.path.exists(setup_flag):
        print("🎉 Primeira execução detectada!")
        print("Executando setup inicial...")
        
        sucesso = setup_inicial(
            db_url=CONFIGURACOES['DB_URL'],
            download_path=CONFIGURACOES['PASTA_DOWNLOAD']
        )
        
        if sucesso:
            # Marca setup como concluído
            with open(setup_flag, 'w') as f:
                f.write(f"Setup concluído em: {datetime.now().isoformat()}")
            print("✅ Setup inicial concluído!")
        else:
            print("❌ Setup falhou! Corrija os erros e tente novamente.")
            return False
    else:
        print("✅ Setup já foi executado anteriormente")
    
    return True

def mostrar_menu():
    """Mostra menu de opções"""
    print("\n" + "="*50)
    print("🏦 SISTEMA DE EXTRAÇÃO ICATU")
    print("="*50)
    print("1. 🚀 Extrair dados de pagamentos pendentes")
    print("2. 📊 Gerar relatório resumo")
    print("3. 🔍 Analisar corretora específica")
    print("4. 🧹 Limpar dados antigos")
    print("5. ⚙️  Testar conexão banco")
    print("6. 🔧 Reconfigurar sistema")
    print("0. ❌ Sair")
    print("="*50)
    
    return input("Escolha uma opção: ").strip()

def executar_extracao():
    """Executa extração para todas as corretoras configuradas"""
    print("🚀 Iniciando extração de dados...")
    
    for codigo, dados in CONFIGURACOES['CORRETORAS'].items():
        config = CorretoraConfig(
            nome=dados['nome'],
            usuario=dados['usuario'],
            senha=dados['senha']
        )
        
        print(f"\n📋 Processando: {config.nome}")
        
        try:
            extractor = IcatuExtractor(config)
            extractor.executar_extracao_completa()
            print(f"✅ {config.nome} concluída com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro processando {config.nome}: {e}")
            continue
        
        # Pausa entre corretoras se houver múltiplas
        if len(CONFIGURACOES['CORRETORAS']) > 1:
            print("⏳ Aguardando 10 segundos antes da próxima corretora...")
            import time
            time.sleep(10)
    
    print("\n🎉 Extração concluída para todas as corretoras!")

def gerar_relatorio():
    """Gera relatório resumo"""
    print("📊 Gerando relatório resumo...")
    
    try:
        analytics = IcatuAnalytics(CONFIGURACOES['DB_URL'])
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(CONFIGURACOES['PASTA_DOWNLOAD'], f"relatorio_resumo_{timestamp}.xlsx")
        
        df = analytics.generate_summary_report(output_path)
        
        if not df.empty:
            print("\n📋 RESUMO GERAL:")
            print(df.to_string(index=False))
            print(f"\n💾 Relatório completo salvo em: {output_path}")
        else:
            print("❌ Nenhum dado encontrado para o relatório")
            
    except Exception as e:
        print(f"❌ Erro gerando relatório: {e}")

def analisar_corretora():
    """Analisa uma corretora específica"""
    print("🔍 Análise de corretora específica")
    
    # Lista corretoras disponíveis
    print("\nCorretoras configuradas:")
    for i, (codigo, dados) in enumerate(CONFIGURACOES['CORRETORAS'].items(), 1):
        print(f"{i}. {dados['nome']} ({codigo})")
    
    try:
        escolha = input("\nEscolha o número da corretora (ou digite o nome): ").strip()
        
        # Tenta converter para número
        try:
            idx = int(escolha) - 1
            if 0 <= idx < len(CONFIGURACOES['CORRETORAS']):
                corretora_nome = list(CONFIGURACOES['CORRETORAS'].values())[idx]['nome']
            else:
                raise ValueError("Número inválido")
        except ValueError:
            # Assume que foi digitado o nome
            corretora_nome = escolha
        
        analytics = IcatuAnalytics(CONFIGURACOES['DB_URL'])
        detalhes = analytics.get_broker_details(corretora_nome)
        
        if detalhes.get('summary'):
            print(f"\n📊 ANÁLISE: {corretora_nome}")
            print("="*50)
            
            summary = detalhes['summary']
            print(f"Total de clientes: {summary.get('total_clients', 0)}")
            print(f"Valor total: R$ {summary.get('total_value', 0):,.2f}")
            print(f"Média dias atraso: {summary.get('avg_overdue', 0):.1f}")
            print(f"Máximo dias atraso: {summary.get('max_overdue', 0)}")
            print(f"Última atualização: {summary.get('last_update', 'N/A')}")
            
            # Por linha de negócio
            if detalhes.get('by_business_line'):
                print(f"\n📈 Por linha de negócio:")
                for linha in detalhes['by_business_line']:
                    print(f"  {linha['business_line']}: {linha['clients']} clientes, R$ {linha['value']:,.2f}")
            
            # Exportar para CRM?
            export = input("\n💾 Exportar dados desta corretora para CRM? (s/n): ").strip().lower()
            if export in ['s', 'sim', 'y', 'yes']:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = os.path.join(CONFIGURACOES['PASTA_DOWNLOAD'], 
                                         f"crm_{corretora_nome.replace(' ', '_')}_{timestamp}.xlsx")
                analytics.export_for_crm(corretora_nome, output_path)
        else:
            print(f"❌ Nenhum dado encontrado para: {corretora_nome}")
            
    except Exception as e:
        print(f"❌ Erro na análise: {e}")

def limpar_dados_antigos():
    """Limpa dados antigos do sistema"""
    print("🧹 Limpeza de dados antigos")
    
    try:
        dias = input("Quantos dias manter? (padrão 90): ").strip()
        dias = int(dias) if dias else 90
        
        from utils import IcatuMaintenance
        maintenance = IcatuMaintenance(CONFIGURACOES['DB_URL'])
        
        deleted = maintenance.clean_old_records(dias)
        maintenance.optimize_database()
        
        print(f"✅ Limpeza concluída! {deleted} registros removidos.")
        
    except Exception as e:
        print(f"❌ Erro na limpeza: {e}")

def testar_conexao():
    """Testa conexão com banco de dados"""
    print("🔧 Testando conexão com banco de dados...")
    
    try:
        setup = IcatuSetup(CONFIGURACOES['DB_URL'])
        if setup.test_connection():
            setup.check_tables()
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")

def reconfigurar_sistema():
    """Refaz configuração do sistema"""
    print("🔧 Reconfigurando sistema...")
    
    # Remove flag de setup
    setup_flag = os.path.join(os.path.dirname(__file__), '.setup_done')
    if os.path.exists(setup_flag):
        os.remove(setup_flag)
        print("✅ Flag de setup removida")
    
    # Executa setup novamente
    verificar_primeiro_uso()

def main():
    """Função principal"""
    print("🏦 Sistema de Extração Icatu - Versão 2.0")
    
    # Verifica primeiro uso
    if not verificar_primeiro_uso():
        sys.exit(1)
    
    # Cria diretório de download se não existir
    os.makedirs(CONFIGURACOES['PASTA_DOWNLOAD'], exist_ok=True)
    
    # Loop principal
    while True:
        try:
            opcao = mostrar_menu()
            
            if opcao == '0':
                print("👋 Encerrando sistema...")
                break
                
            elif opcao == '1':
                executar_extracao()
                
            elif opcao == '2':
                gerar_relatorio()
                
            elif opcao == '3':
                analisar_corretora()
                
            elif opcao == '4':
                limpar_dados_antigos()
                
            elif opcao == '5':
                testar_conexao()
                
            elif opcao == '6':
                reconfigurar_sistema()
                
            else:
                print("❌ Opção inválida! Tente novamente.")
            
            # Pausa antes de mostrar menu novamente
            input("\n⏸️  Pressione Enter para continuar...")
            
        except KeyboardInterrupt:
            print("\n\n👋 Encerrando sistema...")
            break
            
        except Exception as e:
            print(f"\n❌ Erro inesperado: {e}")
            input("⏸️  Pressione Enter para continuar...")

# === EXECUÇÃO RÁPIDA ===
def execucao_rapida():
    """Execução rápida sem menu (para automação)"""
    print("🚀 EXECUÇÃO RÁPIDA - Extraindo todos os dados...")
    
    if not verificar_primeiro_uso():
        sys.exit(1)
    
    executar_extracao()
    gerar_relatorio()
    
    print("✅ Execução rápida concluída!")

if __name__ == "__main__":
    # Verifica se foi chamado com argumento --quick
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        execucao_rapida()
    else:
        main()
