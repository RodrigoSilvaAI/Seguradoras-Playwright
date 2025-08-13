#!/bin/bash

# --- Script para automatizar o upload de arquivos grandes com Git LFS ---

# Encerra o script imediatamente se um comando falhar
set -e

# Cores para a saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Sem Cor

echo -e "${GREEN}--- Assistente de Upload com Git LFS ---${NC}"

# --- Verificações Iniciais ---

# 1. Verifica se o Git está instalado
if ! command -v git &> /dev/null; then
    echo -e "${RED}ERRO: O Git não foi encontrado. Por favor, instale o Git primeiro.${NC}"
    exit 1
fi

# 2. Verifica se o Git LFS está instalado
if ! command -v git-lfs &> /dev/null; then
    echo -e "${RED}ERRO: O Git LFS não foi encontrado.${NC}"
    echo -e "${YELLOW}Por favor, instale-o a partir de: https://git-lfs.com${NC}"
    exit 1
fi

# 3. Verifica se estamos dentro de um repositório Git
if ! git rev-parse --is-inside-work-tree &> /dev/null; then
    echo -e "${RED}ERRO: Este não é um repositório Git. Execute este script na pasta raiz do seu projeto.${NC}"
    exit 1
fi

echo -e "${GREEN}Verificações iniciais concluídas com sucesso.${NC}\n"

# --- Coleta de Informações ---

read -p "Por favor, arraste o arquivo grande para o terminal ou digite o caminho dele e pressione Enter: " FILE_PATH

# Limpa o caminho do arquivo (remove aspas extras que alguns terminais adicionam)
FILE_PATH=$(echo "$FILE_PATH" | sed -e "s/'//g" -e 's/"//g' -e 's/\\ / /g')


# Verifica se o arquivo existe
if [ ! -f "$FILE_PATH" ]; then
    echo -e "\n${RED}ERRO: Arquivo não encontrado em '$FILE_PATH'. Verifique o caminho e tente novamente.${NC}"
    exit 1
fi

# --- Execução dos Comandos ---

echo -e "\n${GREEN}Iniciando o processo...${NC}"

# Passo 1: Inicializa o Git LFS (é seguro rodar múltiplas vezes)
echo "1/5: Inicializando o Git LFS no repositório..."
git lfs install

# Passo 2: Rastreia o arquivo com LFS
echo "2/5: Rastreando o arquivo com o Git LFS..."
git lfs track "$FILE_PATH"
echo -e "O arquivo ${YELLOW}$(basename "$FILE_PATH")${NC} agora está sendo rastreado pelo LFS."

# Passo 3: Adiciona os arquivos para o commit (staging)
echo "3/5: Adicionando arquivos para o próximo commit..."
git add .gitattributes
git add "$FILE_PATH"
echo "O arquivo .gitattributes e seu arquivo grande foram adicionados."

# Passo 4: Realiza o commit
echo -e "4/5: Preparando o commit..."
read -p "Digite a mensagem de commit e pressione Enter: " COMMIT_MSG

# Usa uma mensagem padrão se o usuário não digitar nada
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="Adiciona $(basename "$FILE_PATH") via Git LFS"
    echo "Usando mensagem de commit padrão: $COMMIT_MSG"
fi

git commit -m "$COMMIT_MSG"

# Passo 5: Envia para o repositório remoto
echo "5/5: Enviando para o repositório remoto..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
REMOTE_NAME=$(git remote | head -n 1) # Pega o primeiro nome de remoto (geralmente 'origin')

echo -e "Enviando para o branch ${YELLOW}${CURRENT_BRANCH}${NC} no remoto ${YELLOW}${REMOTE_NAME}${NC}."
git push $REMOTE_NAME $CURRENT_BRANCH

echo -e "\n${GREEN}✅ Processo concluído com sucesso!${NC}"
echo "Seu arquivo foi enviado usando o Git LFS."
