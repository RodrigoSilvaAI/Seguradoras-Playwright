async function getPendingPayments(originalRequest, originalPostData, token, updateStatusFuncion) {
    let pendingPaymentListCount = 1;
    let pendingPaymentsList = [];

    while (true) {
        let postData = JSON.parse(originalPostData);
        postData.Pagina = pendingPaymentListCount;

        updateStatusFuncion?.(pendingPaymentListCount + '/-');

        const responseData = await sendRequest(originalRequest, JSON.stringify(postData), token);
        if (responseData == null || responseData.clientesPendentes.length == 0)
            break;

        // let onlyOne = responseData.clientesPendentes.filter(cp => cp.cliente.id == 46461099);
        // Array.prototype.push.apply(pendingPaymentsList, onlyOne);

        Array.prototype.push.apply(pendingPaymentsList, responseData.clientesPendentes);

        // pendingPaymentsList.push(responseData.clientesPendentes[1]);
        // break;

        // if (pendingPaymentListCount == 1) {
        //     break;
        // }

        pendingPaymentListCount++;
    }

    let productsPromisses = [];
    pendingPaymentsList.forEach(pendingPayment => {
        const productsUrl = 'https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/RelacionamentoCliente/Tombamento/clientes/' + pendingPayment.cliente.id +
            '/produtos?documento=' + pendingPayment.cliente.cpf;
        const productsErrorMessage = 'erro ao consultar produtos pendente de pagamento (' + pendingPayment.cliente.id + '): ';
        const productsPromisse = createGetPromisse(pendingPayment.cliente.id, productsUrl, token, productsErrorMessage);
        productsPromisses.push(productsPromisse);
    });

    let productsList = [];
    let recursesCount = 1;
    const totaRecurses = pendingPaymentsList.length;
    const recurseProducts = () => {
        const makeRequestProducts = productsPromisses.shift();
        return !makeRequestProducts ? null : Promise.all([makeRequestProducts()])
            .then(result => {
                updateStatusFuncion?.(recursesCount + '/' + totaRecurses);

                if (typeof result[0] != 'undefined') {
                    productsList.push({ id: result[0].identifier, data: JSON.parse(result[0].data).produtosCliente.listarProdutos });
                }

                recursesCount++;
                return recurseProducts();
            });
    };

    await Promise.all(Array.from({ length: 10 }, recurseProducts));

    let installmentsPromisses = [];
    pendingPaymentsList.forEach(pendingPayment => {
        const product = (productsList.find(p => p.id == pendingPayment.cliente.id)).data
            .find(p => p.proposta == pendingPayment.produto.proposta);
        // console.log('product', product);

        const installmentsUrl = 'https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/cobranca/cobrancas/' +
            + product.certificadoOfuscado + '/' + product.certificadoOfuscado + '/' + product.linhaNegocio + '/' + pendingPayment.cliente.cpf;
        const installmentsErrorMessage = 'erro ao consultar parcelas pendente de pagamento (' + installmentsUrl + '): ';
        const installmentsPromisse = createGetPromisse(pendingPayment.cliente.id, installmentsUrl, token, installmentsErrorMessage);
        installmentsPromisses.push(installmentsPromisse);
    });
    
    let installmentsList = [];
    recursesCount = 1;
    const recurseInstallments = () => {
        const makeRequestInstallments = installmentsPromisses.shift();
        return !makeRequestInstallments ? null : Promise.all([makeRequestInstallments()])
            .then(result => {
                updateStatusFuncion?.(recursesCount + '/ -');

                if (typeof result[0] != 'undefined') {
                    installmentsList.push({ id: result[0].identifier, data: JSON.parse(result[0].data).result });
                }

                recursesCount++;
                return recurseInstallments();
            });
    };

    await Promise.all(Array.from({ length: 10 }, recurseInstallments));

    // console.log('pendingPaymentsList', pendingPaymentsList);
    // console.log('installmentsList', installmentsList);
    let repeatsPromisses = [];
    installmentsList.forEach(installmentsListItem => {
        if (installmentsListItem.data.length != 0) {
            const pendingPayment = pendingPaymentsList.find(pp => pp.cliente.id == installmentsListItem.id && pp.produto.certificado == installmentsListItem.data[0].certificado);

            installmentsListItem.data.forEach(installment => {
                const url = 'https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/Clientes/' +
                    pendingPayment.cliente.cpf + '/informacoes-repique/' + pendingPayment.produto.certificado + '/0?numeroParcela=' + installment.parcela;
                    
                // if (pendingPayment.produto.proposta == '202304943470') {
                //     console.log('pendingPayment', pendingPayment.produto.proposta + '-' + installment.parcela);
                // }
                
                const repeatsErrorMessage = 'erro ao consultar repiques pendente de pagamento (' + pendingPayment.produto.certificado + '): ';
                const repeatPromisse = createGetPromisse(pendingPayment.produto.proposta + '-' + installment.parcela, url, token, repeatsErrorMessage);
                repeatsPromisses.push(repeatPromisse);
            });
        }
    });

    // throw new Error('Parando execução!');

    let repeatsList = [];
    let repeatsCount = 0;
    const repeatsLength = repeatsPromisses.length;
    const recurseRepeats = () => {
        const makeRequestRepeats = repeatsPromisses.shift();
        return !makeRequestRepeats ? null : Promise.all([makeRequestRepeats()])
            .then(result => {
                updateStatusFuncion?.(repeatsCount + '/' + repeatsLength);

                if (typeof result[0] != 'undefined') {
                    repeatsList.push({ id: result[0].identifier, data: JSON.parse(result[0].data).resultado?.dadosAdicionais });
                }

                repeatsCount++;
                return recurseRepeats();
            });
    };

    await Promise.all(Array.from({ length: 10 }, recurseRepeats));
    
    let pendingPayments = [];
    let installments = [];
    pendingPaymentsList.forEach(pendingPaymentListItem => {
        const product = (productsList.find(p => p.id == pendingPaymentListItem.cliente.id)).data
            .find(p => p.proposta == pendingPaymentListItem.produto.proposta);

        const pendingPayment = parsePendingPayment(pendingPaymentListItem, product);
        pendingPayments.push(pendingPayment);

        const installmentsDetails = (installmentsList.find(i => i.id == pendingPaymentListItem.cliente.id))?.data;
        if (installmentsDetails != null && typeof (installmentsDetails) != 'undefined') {
            const installmentsInfo = parseInstallment(pendingPaymentListItem, product, installmentsDetails, repeatsList);
            Array.prototype.push.apply(installments, installmentsInfo);
        }
    });

    updateStatusFuncion?.('');

    return [
        { name: 'Pagamentos Pendentes', data: pendingPayments },
        { name: 'Parcelas Pendentes', data: installments }
    ];
}

function parsePendingPayment(pendingPaymentListItem, pendingPaymentProduct) {
    try {
        let pendingPayment = new Object();
        pendingPayment.id = pendingPaymentListItem.cliente.id;
        pendingPayment.nome = pendingPaymentListItem.cliente.nome;
        pendingPayment.cpf = pendingPaymentListItem.cliente.cpf_formatado;
        pendingPayment.linha_negocio = pendingPaymentListItem.produto.linha_negocio;
        pendingPayment.produto = pendingPaymentListItem.produto.nome;
        pendingPayment.parcelas_em_aberto = pendingPaymentListItem.produto.qtde_parcelas_abertas;
        pendingPayment.forma_pagamento = pendingPaymentListItem.produto.forma_pagamento_formatada;
        pendingPayment.parcelas_em_aberto = pendingPaymentListItem.produto.qtde_parcelas_abertas;
        pendingPayment.numero_proposta = pendingPaymentListItem.produto.proposta;
        pendingPayment.numero_certificado = pendingPaymentListItem.produto.certificado;
        pendingPayment.valor_contribuicao = pendingPaymentListItem.produto.valor_parcela;
        pendingPayment.situacao_produto = toProductStatus(pendingPaymentProduct);
        pendingPayment.dia_vencimento = pendingPaymentProduct.diaVencimento;
        pendingPayment.ultimo_pagamento = toUTCDate(pendingPaymentProduct.dataUltimoPagamento);
        pendingPayment.proximo_pagamento = toUTCDate(pendingPaymentProduct.dataProximoPagamento);
        pendingPayment.quantidade_parcelas_pagas = pendingPaymentProduct.quantidadeParcelasPagas;
        pendingPayment.quantidade_parcelas_pendentes = pendingPaymentProduct.quantidadeParcelasPendentes;
        pendingPayment.periodicidade_pagamentos = pendingPaymentProduct.periodicidadePagamento;
        
        const lastPayment = new Date(pendingPaymentProduct.dataUltimoPagamento);
        const nextPayment = new Date(pendingPaymentProduct.dataProximoPagamento);
        const today = new Date();
        
        nextPayment.setHours(0, 0, 0, 0);
        today.setHours(0, 0, 0, 0);
        
        const daysDiff = (today - nextPayment) / (1000 * 60 * 60 * 24);
        
        if (lastPayment < nextPayment && nextPayment < today) {
            pendingPayment.dias_em_atraso = daysDiff;
        }

        return pendingPayment;
    } catch (error) {
        logParsePendingPaymentError(pendingPaymentListItem, pendingPaymentProduct);
    }
}

function logParsePendingPaymentError(pendingPaymentListItem, pendingPaymentProduct) {
    console.error('Erro ao converter pendente de pagamento: ' + pendingPaymentListItem.cliente.id, error);
    console.error('pendingPaymentListItem', pendingPaymentListItem);
    console.error('pendingPaymentProduct', pendingPaymentProduct);
}

function parseInstallment(pendingPaymentListItem, product, installmentsDetails, repeatsList) {
    let installments = [];
    installmentsDetails.forEach(installmentDetails => {
        try {
            let installment = new Object();
            installment.id = pendingPaymentListItem.cliente.id;
            installment.nome = pendingPaymentListItem.cliente.nome;
            installment.cpf = pendingPaymentListItem.cliente.cpf_formatado;
            installment.linha_negocio = pendingPaymentListItem.produto.linha_negocio;
            installment.produto = pendingPaymentListItem.produto.nome;
            installment.numero_parcela = installmentDetails.parcela;
            installment.competencia = installmentDetails.competencia;
            installment.vencimento_original = toUTCDate(installmentDetails.vencimentoOriginal);
            installment.vencimento_atual = toUTCDate(installmentDetails.vencimento);
            installment.contribuicao = installmentDetails.valor;

            const repeats = repeatsList.filter(r => r.id == product.proposta + '-' + installmentDetails.parcela);
            const repeatsData = [];
            repeats.forEach(repeat => {
                if (repeat.data != null && typeof (repeat.data) != 'undefined' && repeat.data.length > 0) {
                    Array.prototype.push.apply(repeatsData, repeat.data);
                }
            });

            // if (pendingPaymentListItem.produto.proposta == '202304943470') {
            //     console.log('pendingPaymentListItem', pendingPaymentListItem);
            //     console.log('product', product);
            //     console.log('installmentsDetails', installmentsDetails);
            //     console.log('repeatsList', repeatsList);
            // }

            if (repeatsData.length > 0) {
                repeatsData.forEach(repeatData => {
                    let installmentCopy = cloneDeep(installment);
                    installmentCopy.repique_data = repeatData.data;
                    installmentCopy.repique_data_tentativa = repeatData.dataTentativa;
                    installmentCopy.motivo = repeatData.motivo;
                    installments.push(installmentCopy);
                });
            }
            else {
                installments.push(installment);
            }
        } catch (error) {
            logInstallmentError(pendingPaymentListItem, product, installmentsDetails, error);
        }
    });

    return installments;
}

function logInstallmentError(pendingPaymentListItem, product, installmentsDetails, error) {
    console.error('Erro ao converter parcela pendente de pagamento: ' + pendingPaymentListItem.cliente.id, error);
    console.error('product', product);
    console.error('pendingPaymentListItem', pendingPaymentListItem);
    console.error('installmentsDetails', installmentsDetails);
}