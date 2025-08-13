async function getProposalStatusList(originalRequest, originalPostData, token, updateStatusFuncion) {
    let proposalStatusListCount = 1;
    let proposalStatusList = [];

    while (true) {
        let postData = JSON.parse(originalPostData);
        postData.Pagina = proposalStatusListCount;

        updateStatusFuncion?.(proposalStatusListCount + '/-');

        const responseData = await sendRequest(originalRequest, JSON.stringify(postData), token);
        if (responseData == null || responseData.listaPropostas.length == 0)
            break;

        Array.prototype.push.apply(proposalStatusList, responseData.listaPropostas);

        // proposalStatusList.push(responseData.listaPropostas[1]);
        // break;

        proposalStatusListCount++;
    }

    let proposalStatusDetailsCount = 1;
    let proposalStatusPromisses = [];
    proposalStatusList.forEach(proposalStatus => {
        const url = 'https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/Clientes/' + proposalStatus.cpfProponente + '/primeira-parcela/' + proposalStatus.numeroProposta + '/0';
        const errorMessage = 'erro ao consultar primeira parcela status proposta (' + proposalStatus.numeroProposta + '): ';
        const promisse = createGetPromisse(proposalStatus.numeroProposta, url, token, errorMessage);
        proposalStatusPromisses.push(promisse);
    });

    let propostalStatusResult = [];
    const recursePropostalStatus = () => {
        const makeRequestPropostalStatus = proposalStatusPromisses.shift();
        return !makeRequestPropostalStatus ? null : Promise.all([makeRequestPropostalStatus()])
            .then(result => {
                updateStatusFuncion?.(proposalStatusDetailsCount + '/' + proposalStatusList.length);

                const proposalStatusListItem = proposalStatusList.find(p => p.numeroProposta == result[0].identifier);
                const firstInstallment = JSON.parse(result[0].data).resultado;
                const proposalStatus = parseProposalStatus(proposalStatusListItem, firstInstallment);
                propostalStatusResult.push(proposalStatus);

                proposalStatusDetailsCount++;
                return recursePropostalStatus();
            });
    };

    await Promise.all(Array.from({ length: 10 }, recursePropostalStatus));

    updateStatusFuncion?.('');

    return propostalStatusResult;
}

function parseProposalStatus(proposalStatusListItem, firstInstallment) {
    try {
        let proposalStatus = new Object();
        proposalStatus.nome = proposalStatusListItem.nomeProponente;
        proposalStatus.cpf = proposalStatusListItem.cpfProponente;
        proposalStatus.produto = proposalStatusListItem.nomeProduto;
        proposalStatus.linha_negocio = proposalStatusListItem.linhaNegocio;
        proposalStatus.proposta = proposalStatusListItem.numeroProposta;
        proposalStatus.criada_em = proposalStatusListItem.dataProtocolo;
        proposalStatus.status_proposta = proposalStatusListItem.statusFase;
        proposalStatus.data = proposalStatusListItem.dataStatus;
        proposalStatus.forma_pagamento = proposalStatusListItem.formaPagamento;
        proposalStatus.valor = firstInstallment.valor;
        proposalStatus.vencimento = firstInstallment.agendamentoDebito;
        proposalStatus.competencia = firstInstallment.competencia;
        proposalStatus.status_pagamento = proposalStatusListItem.statusPagamento;
        proposalStatus.motivo_pendencia = proposalStatusListItem.motivoPendencia;

        return proposalStatus;
    } catch (error) {
        logParseError(proposalStatusListItem, firstInstallment, error);
    }
}

function logParseError(proposalStatusListItem, firstInstallment, error){
    console.error('Erro ao converter pendente de pagamento: ' + proposalStatusListItem.numeroProposta, error);
    console.error('proposalStatusListItem', proposalStatusListItem);
    console.error('firstInstallment', firstInstallment);
}