import os
import sys
import psycopg2
from datetime import datetime
import pandas as pd
import json
from typing import List, Dict, Optional
import subprocess

# === CLASSE DE SETUP E UTILITÁRIOS ===
class IcatuSetup:
    def __init__(self, db_url: str):
        self.db_url = db_url
        
    def setup_database(self):
        """Executa o setup completo do banco de dados"""
        print("🗄️ Configurando banco de dados...")
        
        try:
            # Lê o arquivo SQL
            sql_file = os.path.join(os.path.dirname(__file__), 'setup_database.sql')
            if not os.path.exists(sql_file):
                print("❌ Arquivo setup_database.sql não encontrado!")
                return False
                
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Executa no banco
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            # Separa comandos SQL
            commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
            
            for command in commands:
                if command.upper().startswith(('CREATE', 'ALTER', 'INSERT', 'COMMENT')):
                    try:
                        cur.execute(command)
                        print(f"✅ Executado: {command[:50]}...")
                    except Exception as e:
                        print(f"⚠️ Aviso: {command[:50]}... - {e}")
            
            conn.commit()
            cur.close()
            conn.close()
            
            print("✅ Banco de dados configurado com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro no setup do banco: {e}")
            return False
    
    def test_connection(self):
        """Testa conexão com o banco"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()
            cur.close()
            conn.close()
            print(f"✅ Conexão OK: {version[0][:50]}...")
            return True
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
            return False
    
    def check_tables(self):
        """Verifica se as tabelas foram criadas"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('defaulters', 'defaulters_detailed', 'extraction_logs')
                ORDER BY tablename;
            """)
            
            tables = cur.fetchall()
            cur.close()
            conn.close()
            
            expected_tables = ['defaulters', 'defaulters_detailed', 'extraction_logs']
            found_tables = [t[0] for t in tables]
            
            print("📋 Tabelas encontradas:")
            for table in expected_tables:
                status = "✅" if table in found_tables else "❌"
                print(f"   {status} {table}")
            
            return len(found_tables) == len(expected_tables)
            
        except Exception as e:
            print(f"❌ Erro verificando tabelas: {e}")
            return False

class IcatuAnalytics:
    """Classe para análises e relatórios"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
    
    def generate_summary_report(self, output_path: str = None) -> pd.DataFrame:
        """Gera relatório resumo das inadimplências"""
        try:
            conn = psycopg2.connect(self.db_url)
            
            query = """
                SELECT 
                    broker_name as corretora,
                    business_line as linha_negocio,
                    COUNT(*) as total_clientes,
                    SUM(installment_value) as valor_total,
                    AVG(days_overdue) as media_dias_atraso,
                    MAX(days_overdue) as max_dias_atraso,
                    COUNT(CASE WHEN days_overdue BETWEEN 1 AND 30 THEN 1 END) as atraso_1_30,
                    COUNT(CASE WHEN days_overdue BETWEEN 31 AND 60 THEN 1 END) as atraso_31_60,
                    COUNT(CASE WHEN days_overdue BETWEEN 61 AND 90 THEN 1 END) as atraso_61_90,
                    COUNT(CASE WHEN days_overdue > 90 THEN 1 END) as atraso_90_plus,
                    MAX(updated_at) as ultima_atualizacao
                FROM defaulters 
                WHERE days_overdue > 0
                GROUP BY broker_name, business_line
                ORDER BY valor_total DESC;
            """
            
            df = pd.read_sql(query, conn)
            conn.close()
            
            # Formatação
            df['valor_total'] = df['valor_total'].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "R$ 0,00")
            df['media_dias_atraso'] = df['media_dias_atraso'].round(1)
            
            if output_path:
                df.to_excel(output_path, index=False)
                print(f"📊 Relatório salvo em: {output_path}")
            
            return df
            
        except Exception as e:
            print(f"❌ Erro gerando relatório: {e}")
            return pd.DataFrame()
    
    def get_broker_details(self, broker_name: str) -> Dict:
        """Obtém detalhes específicos de uma corretora"""
        try:
            conn = psycopg2.connect(self.db_url)
            
            # Dados gerais
            query_summary = """
                SELECT 
                    COUNT(*) as total_clients,
                    SUM(installment_value) as total_value,
                    AVG(days_overdue) as avg_overdue,
                    MAX(days_overdue) as max_overdue,
                    MIN(created_at) as first_record,
                    MAX(updated_at) as last_update
                FROM defaulters 
                WHERE broker_name = %s AND days_overdue > 0;
            """
            
            summary = pd.read_sql(query_summary, conn, params=[broker_name])
            
            # Por linha de negócio
            query_by_line = """
                SELECT 
                    business_line,
                    COUNT(*) as clients,
                    SUM(installment_value) as value
                FROM defaulters 
                WHERE broker_name = %s AND days_overdue > 0
                GROUP BY business_line
                ORDER BY value DESC;
            """
            
            by_line = pd.read_sql(query_by_line, conn, params=[broker_name])
            
            # Top inadimplentes
            query_top = """
                SELECT 
                    client_name,
                    client_cpf,
                    business_line,
                    installment_value,
                    days_overdue
                FROM defaulters 
                WHERE broker_name = %s AND days_overdue > 0
                ORDER BY days_overdue DESC, installment_value DESC
                LIMIT 20;
            """
            
            top_defaulters = pd.read_sql(query_top, conn, params=[broker_name])
            
            conn.close()
            
            return {
                'summary': summary.to_dict('records')[0] if not summary.empty else {},
                'by_business_line': by_line.to_dict('records'),
                'top_defaulters': top_defaulters.to_dict('records')
            }
            
        except Exception as e:
            print(f"❌ Erro obtendo detalhes da corretora: {e}")
            return {}
    
    def export_for_crm(self, broker_name: str, output_path: str):
        """Exporta dados formatados para CRM"""
        try:
            conn = psycopg2.connect(self.db_url)
            
            query = """
                SELECT 
                    client_name as "Nome Cliente",
                    client_cpf as "CPF",
                    phone1 as "Telefone 1",
                    phone2 as "Telefone 2", 
                    email as "Email",
                    business_line as "Linha Negócio",
                    product_name as "Produto",
                    installment_value as "Valor Parcela",
                    days_overdue as "Dias Atraso",
                    next_payment as "Próximo Vencimento",
                    open_installments as "Parcelas Abertas",
                    collection_method as "Forma Cobrança"
                FROM defaulters 
                WHERE broker_name = %s AND days_overdue > 0
                ORDER BY days_overdue DESC, installment_value DESC;
            """
            
            df = pd.read_sql(query, conn, params=[broker_name])
            conn.close()
            
            # Salva em Excel formatado
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Inadimplentes', index=False)
                
                # Formatação básica
                worksheet = writer.sheets['Inadimplentes']
                
                # Auto-ajusta largura das colunas
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            print(f"📊 Dados para CRM exportados: {output_path}")
            
        except Exception as e:
            print(f"❌ Erro exportando para CRM: {e}")

class IcatuMaintenance:
    """Classe para manutenção e limpeza"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
    
    def clean_old_records(self, days_to_keep: int = 90) -> int:
        """Remove registros antigos"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            # Remove logs antigos
            cur.execute("""
                DELETE FROM extraction_logs 
                WHERE started_at < CURRENT_DATE - INTERVAL '%s days'
            """, (days_to_keep,))
            
            deleted_logs = cur.rowcount
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"🧹 Removidos {deleted_logs} logs antigos (>{days_to_keep} dias)")
            return deleted_logs
            
        except Exception as e:
            print(f"❌ Erro na limpeza: {e}")
            return 0
    
    def optimize_database(self):
        """Otimiza o banco de dados"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            tables = ['defaulters', 'defaulters_detailed', 'extraction_logs']
            
            for table in tables:
                cur.execute(f"VACUUM ANALYZE {table};")
                print(f"✅ Otimizada tabela: {table}")
            
            conn.commit()
            cur.close()
            conn.close()
            
            print("🚀 Otimização concluída!")
            
        except Exception as e:
            print(f"❌ Erro na otimização: {e}")
    
    def backup_data(self, output_dir: str):
        """Faz backup dos dados"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            conn = psycopg2.connect(self.db_url)
            
            tables = ['defaulters', 'defaulters_detailed', 'extraction_logs']
            
            for table in tables:
                df = pd.read_sql(f"SELECT * FROM {table}", conn)
                output_path = os.path.join(output_dir, f"{table}_{timestamp}.csv")
                df.to_csv(output_path, index=False)
                print(f"💾 Backup salvo: {output_path}")
            
            conn.close()
            print("✅ Backup concluído!")
            
        except Exception as e:
            print(f"❌ Erro no backup: {e}")

# === FUNÇÃO DE SETUP INICIAL ===
def setup_inicial(db_url: str, extension_path: str = None, download_path: str = None):
    """Setup inicial completo do sistema"""
    print("🚀 SETUP INICIAL DO SISTEMA ICATU")
    print("=" * 50)
    
    # 1. Verificar dependências
    print("\n📦 Verificando dependências...")
    required_packages = ['playwright', 'pandas', 'psycopg2', 'requests', 'openpyxl']
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - Execute: pip install {package}")
    
    # 2. Setup do banco
    print("\n🗄️ Configurando banco de dados...")
    setup = IcatuSetup(db_url)
    
    if setup.test_connection():
        if setup.setup_database():
            setup.check_tables()
        else:
            print("❌ Falha no setup do banco!")
            return False
    else:
        print("❌ Falha na conexão com banco!")
        return False
    
    # 3. Verificar diretórios
    print("\n📁 Verificando diretórios...")
    if download_path:
        os.makedirs(download_path, exist_ok=True)
        print(f"   ✅ Downloads: {download_path}")
    
    # 4. Instalar Playwright browsers
    print("\n🌐 Instalando browsers Playwright...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                      check=True, capture_output=True)
        print("   ✅ Chromium instalado")
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ Erro instalando browsers: {e}")
    
    print("\n✅ Setup inicial concluído!")
    print("\nPróximos passos:")
    print("1. Configure as credenciais no arquivo principal")
    print("2. Execute o script: python icatu_complete_python.py")
    print("3. Monitore os logs de execução")
    
    return True

# === EXECUÇÃO DIRETA ===
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Utilitários do Sistema Icatu')
    parser.add_argument('--action', choices=['setup', 'test', 'report', 'clean'], 
                       required=True, help='Ação a executar')
    parser.add_argument('--db-url', required=True, help='URL do banco PostgreSQL')
    parser.add_argument('--broker', help='Nome da corretora (para relatórios)')
    parser.add_argument('--output', help='Arquivo de saída')
    parser.add_argument('--days', type=int, default=90, help='Dias para manter (limpeza)')
    
    args = parser.parse_args()
    
    if args.action == 'setup':
        setup_inicial(args.db_url)
    
    elif args.action == 'test':
        setup = IcatuSetup(args.db_url)
        setup.test_connection()
        setup.check_tables()
    
    elif args.action == 'report':
        analytics = IcatuAnalytics(args.db_url)
        if args.broker:
            details = analytics.get_broker_details(args.broker)
            print(json.dumps(details, indent=2, default=str))
        else:
            df = analytics.generate_summary_report(args.output)
            print(df.to_string())
    
    elif args.action == 'clean':
        maintenance = IcatuMaintenance(args.db_url)
        maintenance.clean_old_records(args.days)
        maintenance.optimize_database()
