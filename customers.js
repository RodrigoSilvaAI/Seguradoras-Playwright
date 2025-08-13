async function getCustomers(originalRequest, originalPostData, token, updateStatusFuncion) {
    let customerListCount = 1;
    let customersList = [];

    while (true) {
        let postData = JSON.parse(originalPostData);
        postData.Pagina = customerListCount;

        updateStatusFuncion?.(customerListCount + '/-');

        const responseData = await sendRequest(originalRequest, JSON.stringify(postData), token);
        if (responseData == null || responseData.clientes.length == 0)
            break;

        Array.prototype.push.apply(customersList, responseData.clientes);

        // customersList.push(responseData.clientes[1]);
        // break; 

        // if (customerListCount == 1) {
        //     break; 
        // }

        customerListCount++;
    }

    let customerPromisses = [];
    let customerProductsPromisses = [];
    customersList.forEach(customer => {
        const detailsUrl = 'https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/RelacionamentoCliente/Tombamento/clientes/' + customer.codigoBaseAgrupada;
        const detailsErrorMessage = 'erro ao consultar cliente (' + customer.codigoBaseAgrupada + '): ';
        const detailsPromisse = createGetPromisse(customer.codigoBaseAgrupada, detailsUrl, token, detailsErrorMessage);
        customerPromisses.push(detailsPromisse);

        const productsUrl = 'https://portalcorretor.icatuseguros.com.br/casadocorretorgateway/api/RelacionamentoCliente/Tombamento/clientes/' +
            customer.codigoBaseAgrupada + '/produtos?documento=' + customer.cpfCnpj;

        const productsErrorMessage = 'erro ao consultar produtos do cliente (' + customer.codigoBaseAgrupada + '): ';
        const productsPromisse = createGetPromisse(customer.codigoBaseAgrupada, productsUrl, token, productsErrorMessage);
        customerProductsPromisses.push(productsPromisse);
    });

    let customerDetailsList = [];
    let recursesCount = 1;
    const totaRecurses = customersList.length * 2;
    const recurseDetails = () => {
        const makeRequestDetails = customerPromisses.shift();
        return !makeRequestDetails ? null : Promise.all([makeRequestDetails()])
            .then(result => {

                updateStatusFuncion?.(recursesCount + '/' + totaRecurses);

                if (typeof result[0] != 'undefined') {
                    customerDetailsList.push({ id: result[0].identifier, data: JSON.parse(result[0].data).detalhesCliente.clientes[0] });
                }
                recursesCount++;
                return recurseDetails();
            });
    };

    await Promise.all(Array.from({ length: 10 }, recurseDetails));

    let customerProductsList = [];
    const recurseProducts = () => {
        const makeRequestProducts = customerProductsPromisses.shift();
        return !makeRequestProducts ? null : Promise.all([makeRequestProducts()])
            .then(result => {

                updateStatusFuncion?.(recursesCount + '/' + totaRecurses);

                if (typeof result[0] != 'undefined') {
                    customerProductsList.push({ id: result[0].identifier, data: JSON.parse(result[0].data).produtosCliente.listarProdutos });
                }
                recursesCount++;
                return recurseProducts();
            });
    };

    await Promise.all(Array.from({ length: 10 }, recurseProducts));

    let customerPortfolio = [];
    let prevCustomers = [];
    let vidaCustomers = [];
    customersList.forEach(customerListItem => {
        const customerDetails = (customerDetailsList.find(c => c.id == customerListItem.codigoBaseAgrupada)).data;
        const customerProducts = (customerProductsList.find(c => c.id == customerListItem.codigoBaseAgrupada)).data;
        customerProducts.forEach(customerProduct => {

            if (customerProduct.linhaNegocio == 'PREV') {
                const prevCustomerInfos = parsePrevCustomer(customerListItem, customerDetails, customerProduct);
                Array.prototype.push.apply(prevCustomers, prevCustomerInfos);
            }

            if (customerProduct.linhaNegocio == 'VIDA') {
                const vidaCustomerInfos = parseVidaCustomer(customerListItem, customerDetails, customerProduct);
                Array.prototype.push.apply(vidaCustomers, vidaCustomerInfos);
            }

            const customerWithoutProduct = parseCustomerWithoutProduct(customerListItem, customerDetails, customerProduct);
            customerPortfolio.push(customerWithoutProduct);
        });
    });

    updateStatusFuncion?.('');

    return [
        { name: 'Vida', data: vidaCustomers },
        { name: 'Previdência', data: prevCustomers },
        { name: 'Carteira de clientes', data: customerPortfolio }
    ];
}

function parseCustomer(customerListItem, customerDetails, customerProduct) {
    try {
        let customer = new Object();
        customer.id = customerDetails.codigoBaseAgrupada;
        customer.nome = customerDetails.nome;
        customer.documento = customerListItem.documento.tipo + ': ' + customerListItem.documento.numeroFormatado;
        customer.titular_cpf = customerDetails.titularCPF;
        customer.sexo = customerDetails.sexo;
        customer.data_nascimento = customerDetails.dataNascimentoFormatada;
        customer.estado_civil = customerDetails.estadoCivilFormatado;
        customer.tipo_documento = customerDetails.identidade?.[0]?.tipoDocumento;
        customer.numero_documento = customerDetails.identidade?.[0]?.documento;
        customer.orgao_expedidor = customerDetails.identidade?.[0]?.orgaoExpedidor
        customer.renda_patrimonio = customerDetails.rendaResumidaFormatada
        customer.profissao = customerDetails.profissao;
        customer.telefone = joinArray(customerDetails.telefone, ';', 'numeroTelefone');
        customer.email = customerDetails.emails?.[0]?.email;
        customer.endereco = customerDetails.endereco?.[0]?.descricaoEndereco;
        customer.numero = customerDetails.endereco?.[0]?.numero;
        customer.complemento = customerDetails.endereco?.[0]?.complemento;
        customer.bairro = customerDetails.endereco?.[0]?.bairro;
        customer.cidade = customerDetails.endereco?.[0]?.municipio;
        customer.uf = customerDetails.endereco?.[0]?.uf;
        customer.cep = customerDetails.endereco?.[0]?.cepFormatado;
        customer.linha_negocio = toFormattedLineOfBusiness(customerProduct.linhaNegocio);
        customer.tipo = customerProduct.nomeProduto;
        customer.numero_proposta = customerProduct.proposta;
        customer.numero_certificado = customerProduct.certificado;
        customer.valor_contribuicao = customerProduct.valorPagamento;
        customer.situacao_produto = toProductStatus(customerProduct);
        customer.numero_processo_susep = customerProduct.numeroProcessoSusep;

        return customer;
    } catch (error) {
        logParseError(customerListItem, customerDetails, customerProduct, error);
    }
}

function parseCustomerWithoutProduct(customerListItem, customerDetails, customerProduct) {
    try {
        let customer = parseCustomer(customerListItem, customerDetails, customerProduct);
        customer.dia_vencimento = customerProduct.diaVencimento;
        customer.ultimo_pagamento = toUTCDate(customerProduct.dataUltimoPagamento);
        customer.proximo_pagamento = toUTCDate(customerProduct.dataProximoPagamento);
        customer.quantidade_parcelas_pagas = customerProduct.quantidadeParcelasPagas;
        customer.quantidade_parcelas_pendentes = customerProduct.quantidadeParcelasPendentes;
        customer.periodicidade_pagamentos = customerProduct.periodicidadePagamento;
        customer.forma_pagamento = customerProduct.formaPagamento;

        return customer;
    } catch (error) {
        logParseError(customerListItem, customerDetails, customerProduct, error);
    }
}

function parsePrevCustomer(customerListItem, customerDetails, customerProduct) {
    let customers = [];
    // customerProduct.prev.beneficios.forEach(benefit => {


    try {
        let customer = parseCustomer(customerListItem, customerDetails, customerProduct);
        if (customerProduct.prev.acumulacao != null && typeof (customerProduct.prev.acumulacao) != 'undefined') {
            customer.nome_fundo = customerProduct.prev.acumulacao.fundo;
            customer.cnpj_fundo = customerProduct.prev.acumulacao.cnpjFundo;
            customer.regime_tributario = customerProduct.prev.acumulacao.regimeTribCertAcumulacao;
            customer.indexador_plano = customerProduct.prev.acumulacao.indexadorCertificadoAcumulacao;
        }
        customer.dia_vencimento = customerProduct.diaVencimento;
        customer.ultimo_pagamento = toUTCDate(customerProduct.dataUltimoPagamento);
        customer.proximo_pagamento = toUTCDate(customerProduct.dataProximoPagamento);
        customer.quantidade_parcelas_pagas = customerProduct.quantidadeParcelasPagas;
        customer.quantidade_parcelas_pendentes = customerProduct.quantidadeParcelasPendentes;
        customer.periodicidade_pagamentos = customerProduct.periodicidadePagamento;
        customer.forma_pagamento = customerProduct.formaPagamento;

        customers.push(customer);
    } catch (error) {
        logParseError(customerListItem, customerDetails, customerProduct, error);
    }

    // });

    return customers;
}

function parseVidaCustomer(customerListItem, customerDetails, customerProduct) {
    let customers = [];
    customerProduct.vida.beneficios.forEach(benefit => {
        try {
            let customer = parseCustomer(customerListItem, customerDetails, customerProduct);
            customer.nome_cobertura = benefit.nomeBeneficio;
            customer.capital_segurado = benefit.capitalBeneficioSegurado;
            customer.periodo_pagamento = benefit.prazoPagamento;
            customer.dia_vencimento = customerProduct.diaVencimento;
            customer.ultimo_pagamento = toUTCDate(customerProduct.dataUltimoPagamento);
            customer.proximo_pagamento = toUTCDate(customerProduct.dataProximoPagamento);
            customer.quantidade_parcelas_pagas = customerProduct.quantidadeParcelasPagas;
            customer.quantidade_parcelas_pendentes = customerProduct.quantidadeParcelasPendentes;
            customer.periodicidade_pagamentos = customerProduct.periodicidadePagamento;

            customers.push(customer);
        } catch (error) {
            logParseError(customerListItem, customerDetails, customerProduct, error);
        }
    });

    return customers;
}

function logParseError(customerListItem, customerDetails, customerProduct, error) {
    console.error('Erro ao converter cliente: ' + customerListItem.codigoBaseAgrupada, error);
    console.error('customerListItem', customerListItem);
    console.error('customerDetails', customerDetails);
    console.error('customerProduct', customerProduct);
}