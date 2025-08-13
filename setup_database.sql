-- ============================================
-- SETUP DO BANCO DE DADOS ICATU
-- ============================================

-- Extensão para UUID (se necessário)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela principal de inadimplentes
CREATE TABLE IF NOT EXISTS defaulters (
    id SERIAL PRIMARY KEY,
    broker_name VARCHAR(255) NOT NULL,
    business_line VARCHAR(50),
    product_name VARCHAR(255),
    certificate_number VARCHAR(100),
    client_name VARCHAR(255),
    client_cpf VARCHAR(20) NOT NULL,
    proposal_number VARCHAR(100),
    installment_value DECIMAL(10,2) DEFAULT 0,
    product_status VARCHAR(50),
    due_day INTEGER,
    last_payment VARCHAR(20),
    next_payment VARCHAR(20),
    paid_installments INTEGER DEFAULT 0,
    pending_installments INTEGER DEFAULT 0,
    payment_frequency VARCHAR(50),
    days_overdue INTEGER DEFAULT 0,
    collection_method VARCHAR(100),
    open_installments INTEGER DEFAULT 0,
    phone1 VARCHAR(20),
    phone2 VARCHAR(20),
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Índices únicos para evitar duplicatas
    UNIQUE(client_cpf, certificate_number)
);

-- Tabela detalhada de parcelas
CREATE TABLE IF NOT EXISTS defaulters_detailed (
    id SERIAL PRIMARY KEY,
    broker_name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255),
    client_cpf VARCHAR(20) NOT NULL,
    business_line VARCHAR(50),
    product_name VARCHAR(255),
    installment_number VARCHAR(20),
    competency VARCHAR(20),
    original_due_date VARCHAR(20),
    current_due_date VARCHAR(20),
    contribution_value DECIMAL(10,2) DEFAULT 0,
    retry_date VARCHAR(20),
    retry_attempt_date VARCHAR(20),
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Índice único para evitar duplicatas
    UNIQUE(client_cpf, installment_number, competency)
);

-- Tabela de log de execuções
CREATE TABLE IF NOT EXISTS extraction_logs (
    id SERIAL PRIMARY KEY,
    broker_name VARCHAR(255) NOT NULL,
    extraction_type VARCHAR(50) NOT NULL, -- 'pending_payments', 'customers', 'proposals'
    total_records INTEGER DEFAULT 0,
    success_records INTEGER DEFAULT 0,
    error_records INTEGER DEFAULT 0,
    execution_time_seconds INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running', -- 'running', 'success', 'error'
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_defaulters_broker ON defaulters(broker_name);
CREATE INDEX IF NOT EXISTS idx_defaulters_cpf ON defaulters(client_cpf);
CREATE INDEX IF NOT EXISTS idx_defaulters_overdue ON defaulters(days_overdue);
CREATE INDEX IF NOT EXISTS idx_defaulters_created ON defaulters(created_at);

CREATE INDEX IF NOT EXISTS idx_detailed_broker ON defaulters_detailed(broker_name);
CREATE INDEX IF NOT EXISTS idx_detailed_cpf ON defaulters_detailed(client_cpf);
CREATE INDEX IF NOT EXISTS idx_detailed_created ON defaulters_detailed(created_at);

CREATE INDEX IF NOT EXISTS idx_logs_broker ON extraction_logs(broker_name);
CREATE INDEX IF NOT EXISTS idx_logs_started ON extraction_logs(started_at);

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$ language 'plpgsql';

CREATE TRIGGER update_defaulters_updated_at 
    BEFORE UPDATE ON defaulters 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_defaulters_detailed_updated_at 
    BEFORE UPDATE ON defaulters_detailed 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views úteis para análise
CREATE OR REPLACE VIEW v_defaulters_summary AS
SELECT 
    broker_name,
    business_line,
    COUNT(*) as total_clients,
    SUM(installment_value) as total_value,
    AVG(days_overdue) as avg_days_overdue,
    MAX(days_overdue) as max_days_overdue,
    COUNT(CASE WHEN days_overdue > 30 THEN 1 END) as overdue_30_plus,
    COUNT(CASE WHEN days_overdue > 60 THEN 1 END) as overdue_60_plus,
    COUNT(CASE WHEN days_overdue > 90 THEN 1 END) as overdue_90_plus
FROM defaulters 
WHERE days_overdue > 0
GROUP BY broker_name, business_line
ORDER BY broker_name, business_line;

CREATE OR REPLACE VIEW v_latest_extraction AS
SELECT 
    broker_name,
    extraction_type,
    total_records,
    success_records,
    error_records,
    execution_time_seconds,
    status,
    started_at,
    finished_at,
    ROW_NUMBER() OVER (PARTITION BY broker_name, extraction_type ORDER BY started_at DESC) as rn
FROM extraction_logs;

-- Função para limpar dados antigos (executar manualmente se necessário)
CREATE OR REPLACE FUNCTION clean_old_data(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Remove registros antigos da tabela de logs
    DELETE FROM extraction_logs 
    WHERE started_at < CURRENT_DATE - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$ LANGUAGE plpgsql;

-- Comentários nas tabelas
COMMENT ON TABLE defaulters IS 'Tabela principal de clientes inadimplentes';
COMMENT ON TABLE defaulters_detailed IS 'Tabela detalhada de parcelas pendentes';
COMMENT ON TABLE extraction_logs IS 'Log de execuções do sistema de extração';

COMMENT ON COLUMN defaulters.days_overdue IS 'Dias em atraso calculados automaticamente';
COMMENT ON COLUMN defaulters.open_installments IS 'Quantidade de parcelas em aberto';
COMMENT ON COLUMN defaulters_detailed.retry_date IS 'Data da última tentativa de cobrança';
COMMENT ON COLUMN defaulters_detailed.rejection_reason IS 'Motivo da rejeição do pagamento';

-- Grants para usuário da aplicação (ajustar conforme necessário)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON defaulters TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON defaulters_detailed TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON extraction_logs TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Dados de exemplo para teste (remover em produção)
/*
INSERT INTO defaulters (
    broker_name, business_line, product_name, certificate_number,
    client_name, client_cpf, proposal_number, installment_value,
    days_overdue, open_installments
) VALUES (
    'TESTE CORRETORA',
    'VIDA',
    'PRODUTO TESTE',
    '12345',
    'CLIENTE TESTE',
    '12345678901',
    'PROP123',
    150.00,
    45,
    3
);
*/

-- Query útil para verificar status das extrações
/*
SELECT 
    broker_name,
    extraction_type,
    total_records,
    success_records,
    execution_time_seconds,
    status,
    started_at
FROM v_latest_extraction 
WHERE rn = 1
ORDER BY started_at DESC;
*/
