import requests
import json
import os

# Arquivo onde o token é salvo
TOKEN_FILE = "token.txt"
API_URL = "https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/RelacionamentoCliente/Tombamento/clientes"

def read_token():
    """Lê o token do arquivo."""
    if not os.path.exists(TOKEN_FILE):
        print(f"❌ Arquivo '{TOKEN_FILE}' não encontrado.")
        print("Por favor, execute o script 'run_icatu_extraction.py' primeiro para gerar o token.")
        return None
    with open(TOKEN_FILE, 'r') as f:
        token = f.read().strip()
    if not token.startswith("Bearer "):
        print("❌ Token inválido encontrado no arquivo.")
        return None
    return token

def fetch_all_clients(token):
    """Busca todos os clientes da API, página por página."""
    headers = {"Authorization": token, "Content-Type": "application/json"}
    all_clients = []
    pagina = 1
    quantidade_por_pagina = 50

    print(f"🚀 Chamando a API em: {API_URL}")
    while True:
        payload = {"pagina": pagina, "quantidade": quantidade_por_pagina}
        print(f"Buscando página {pagina}...")
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                clientes_na_pagina = data.get("clientes", [])
                if not clientes_na_pagina:
                    print("Fim da lista de clientes.")
                    break
                all_clients.extend(clientes_na_pagina)
                pagina += 1
            else:
                print(f"❌ Erro na API na página {pagina}. Status: {response.status_code}")
                print(response.text)
                return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Ocorreu um erro de conexão com a API: {e}")
            return None
    return all_clients

def main():
    """Função principal para ler o token e buscar os clientes."""
    token = read_token()
    if token:
        clients = fetch_all_clients(token)
        if clients is not None:
            print("\n" + "="*60)
            print(f"✅ Extração finalizada com sucesso! Total de {len(clients)} clientes encontrados.")
            print("="*60)
            
            output_filename = "lista_clientes_icatu.json"
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(clients, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Dados dos clientes salvos em '{output_filename}'")

if __name__ == "__main__":
    main()
