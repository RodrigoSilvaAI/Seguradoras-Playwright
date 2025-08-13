// This script is designed to be injected and executed by Playwright.
// It fetches all necessary data from the Icatu portal's internal APIs
// and returns it as a single JSON object.

async function fetchAllPendingData(token, apiBaseUrl) {
    console.log('Starting data fetch inside the browser...');

    const statusLog = (message) => console.log(`[Fetcher.js] ${message}`);

    // Helper to make authenticated API calls
    const fetchApi = async (url, method = 'GET', body = null) => {
        const headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        };
        const options = { method, headers };
        if (body) {
            options.body = JSON.stringify(body);
        }
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`API request failed: ${response.status} ${response.statusText} for ${url}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API Fetch Error:', error);
            return null;
        }
    };

    // 1. Fetch all pending clients
    const getPendingClients = async () => {
        let page = 1;
        const allClients = [];
        statusLog('Fetching pending clients...');

        while (true) {
            statusLog(`Fetching page ${page}...`);
            const postData = {
                "Pagina": page,
                "ItensPorPagina": 100,
                "Ordenacao": "NomeCliente",
                "Crescente": true
            };
            const url = `${apiBaseUrl}/RelacionamentoCliente/Tombamento/pendentes`;
            const response = await fetchApi(url, 'POST', postData);

            if (!response || !response.clientesPendentes || response.clientesPendentes.length === 0) {
                break;
            }
            allClients.push(...response.clientesPendentes);
            page++;
        }
        statusLog(`Found ${allClients.length} total pending clients.`);
        return allClients;
    };

    // 2. Fetch product details for each client
    const getProductDetails = async (clients) => {
        statusLog('Fetching product details...');
        const productsByClient = {};
        for (let i = 0; i < clients.length; i++) {
            const client = clients[i];
            const clientId = client.cliente.id;
            const cpf = client.cliente.cpf;
            const url = `${apiBaseUrl}/RelacionamentoCliente/Tombamento/clientes/${clientId}/produtos?documento=${cpf}`;
            const response = await fetchApi(url);
            if (response && response.produtosCliente) {
                productsByClient[clientId] = response.produtosCliente.listarProdutos;
            }
            if ((i + 1) % 10 === 0) {
                statusLog(`  - Products: ${i + 1}/${clients.length}`);
                await new Promise(resolve => setTimeout(resolve, 500)); // Rate limit
            }
        }
        return productsByClient;
    };

    // 3. Fetch detailed installments for each client/product
    const getInstallmentDetails = async (clients, productsByClient) => {
        statusLog('Fetching installment details...');
        const installmentsByClient = {};
        for (let i = 0; i < clients.length; i++) {
            const client = clients[i];
            const clientId = client.cliente.id;
            const cpf = client.cliente.cpf;
            const proposal = client.produto.proposta;

            const products = productsByClient[clientId] || [];
            const product = products.find(p => p.proposta === proposal);

            if (!product) continue;

            const certificate = product.certificadoOfuscado || '';
            const businessLine = product.linhaNegocio || '';
            const url = `${apiBaseUrl}/cobranca/cobrancas/${certificate}/${certificate}/${businessLine}/${cpf}`;
            const response = await fetchApi(url);

            if (response && response.result) {
                installmentsByClient[clientId] = response.result;
            }
             if ((i + 1) % 5 === 0) {
                statusLog(`  - Installments: ${i + 1}/${clients.length}`);
                await new Promise(resolve => setTimeout(resolve, 300)); // Rate limit
            }
        }
        return installmentsByClient;
    };

    // 4. Fetch repiques (reprocessing attempts)
    const getRepiques = async (clients, installmentsByClient) => {
        statusLog('Fetching repique details...');
        const repiquesBykey = {};
        let counter = 0;
        for (const client of clients) {
            const clientId = client.cliente.id;
            const cpf = client.cliente.cpf;
            const certificate = client.produto.certificado;
            const installments = installmentsByClient[clientId] || [];

            for (const installment of installments) {
                counter++;
                const installmentNumber = installment.parcela || '';
                const key = `${client.produto.proposta}-${installmentNumber}`;
                const url = `${apiBaseUrl}/Clientes/${cpf}/informacoes-repique/${certificate}/0?numeroParcela=${installmentNumber}`;
                const response = await fetchApi(url);

                if (response && response.resultado && response.resultado.dadosAdicionais) {
                    repiquesBykey[key] = response.resultado.dadosAdicionais;
                }
                if (counter % 3 === 0) {
                     await new Promise(resolve => setTimeout(resolve, 500)); // Rate limit
                }
            }
        }
        statusLog(`Found repique info for ${Object.keys(repiquesBykey).length} keys.`);
        return repiquesBykey;
    };


    // --- Main Execution ---
    try {
        const clientesPendentes = await getPendingClients();
        if (clientesPendentes.length === 0) {
            return { status: 'No pending clients found.' };
        }

        const produtosPorCliente = await getProductDetails(clientesPendentes);
        const parcelasPorCliente = await getInstallmentDetails(clientesPendentes, produtosPorCliente);
        const repiquesPorChave = await getRepiques(clientesPendentes, parcelasPorCliente);

        statusLog('All data fetched successfully.');

        // Return data in the same structure the Python script uses
        return {
            clientesPendentes,
            produtosPorCliente,
            parcelasPorCliente,
            repiquesPorChave
        };
    } catch (error) {
        console.error('An error occurred during the fetch process:', error);
        return { error: error.message, stack: error.stack };
    }
}