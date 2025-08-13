(function (xhr) {
  const downloadSvg = '<svg width="60px" height="60px" viewBox="2 2 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="#000000" stroke-width="0.00024000000000000003"><circle cx="12" cy="12" r="10" fill="#FFFFFF"/><g id="SVGRepo_bgCarrier" stroke-width="0"></g><g id="SVGRepo_tracerCarrier" stroke-linecap="round" stroke-linejoin="round" stroke="#CCCCCC" stroke-width="0.048"></g><g id="SVGRepo_iconCarrier"> <path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM15.1743 11.4444L14.5457 10.8159L12.476 12.8856V7H11.5871V12.8856L9.51744 10.8159L8.8889 11.4444L12.0316 14.5871L15.1743 11.4444ZM8 16.3333V15.4444H16V16.3333H8Z" fill="#1cb025"></path> </g></svg>'
  const downloadButtonId = 'downloadButton1234';
  const downloadStatusId = 'downloadStats';
  const beamerSelectorId = 'beamerSelector';
  const downloadLocations = ['/portal', '/meus-clientes', '/meus-clientes/pendentes', '/venda/status-proposta', '/relatorios/relatorio-produtividade'];

  // Intercept fetch
  const originalFetch = fetch;
  window.fetch = function (url, options) {
    return originalFetch(url, options).then(response => {
      // console.log('Intercept fetch', url);
      return response;
    });
  };

  var XHR = XMLHttpRequest.prototype;
  var open = XHR.open;
  var send = XHR.send;
  var setRequestHeader = XHR.setRequestHeader;
  XHR.open = function (method, url) {
    this._method = method;
    this._url = url;
    this._requestHeaders = {};
    this._startTime = (new Date()).toISOString();
    return open.apply(this, arguments);
  };

  XHR.setRequestHeader = function (header, value) {
    this._requestHeaders[header] = value;
    return setRequestHeader.apply(this, arguments);
  };

  XHR.send = function (postData) {
    this.addEventListener('load', function () {
      // console.log('Intercept XHR', this._url);

      if (isInDownloadLocation() && !isCustomRequest(this)) {
        const statusDiv = document.getElementById(downloadStatusId);

        switch (true) {
          // case this._url.endsWith('/api/Comissao/resumo'):
          //   createDownloadButton(this, postData, downloadFullInformation)
          //   break;
          case this._url.endsWith('/api/RelacionamentoCliente/Tombamento/clientes'):
            createDownloadButton(this, postData, downloadCustomers);
            break;
          // case this._url.endsWith('/api/clientes/pendentes'):
          case this._url.endsWith('/api/RelacionamentoCliente/Tombamento/pendentes'):
            createDownloadButton(this, postData, downloadPendingPayment);
            break;
          case this._url.endsWith('/api/relatorio/consulta/status/v2'):
            createDownloadButton(this, postData, downloadProposalStatus);
            break;
          case this._url.includes('/api/Relatorio/produtividade-vida/Tabela/v2'):
            createDownloadButton(this, postData, downloadProductivityReport);
            break;
          default:
            break;
        }
      }

      if (!isInDownloadLocation())
        removeAllDownloadButtons();

    });

    return send.apply(this, arguments);
  };

  function isInDownloadLocation() {
    return downloadLocations.some(v => window.location.pathname.endsWith(v));
  }

  function removeAllDownloadButtons() {
    // console.log('removeAllDownloadButtons');
    let ids = [downloadButtonId];
    ids.forEach(id => {
      let existingButton = document.getElementById(id);
      if (existingButton != null) {
        existingButton.remove();
      }
    });
  }

  async function downloadCustomers(originalRequest, originalPostData, token, updateStatus) {
    console.log('downloadCustomers');

    const customers = await getCustomers(originalRequest, originalPostData, token, updateStatus);
    console.log('customers', customers);

    exportToExcel('clientes', customers);
  }

  async function downloadPendingPayment(originalRequest, originalPostData, token, updateStatus) {
    console.log('downloadPendingPayment');

    const pendingPayments = await getPendingPayments(originalRequest, originalPostData, token, updateStatus);
    console.log('pendingPayments', pendingPayments);

    exportToExcel('clientes_pendentes', pendingPayments);
  }

  async function downloadProposalStatus(originalRequest, originalPostData, token, updateStatus) {
    console.log('downloadProposalStatus');

    const proposalStatusList = await getProposalStatusList(originalRequest, originalPostData, token, updateStatus);
    console.log('proposalStatusList', proposalStatusList);

    const sheets = createSheetsFor('Status Propostas', proposalStatusList);
    exportToExcel('status_propostas', sheets);
  }

  async function downloadProductivityReport(originalRequest, originalPostData, token, updateStatus) {
    console.log('downloadProductivityReport');
  }

  async function downloadFullInformation(originalRequest, originalPostData, token, updateStatus) {
    console.log('downloadFullInformation');
    const statusDiv = document.getElementById(downloadStatusId);

  }

  function createDownloadButton(originalRequest, originalPostData, downloadAction) {
    // console.log('createDownloadButton');
    removeAllDownloadButtons();

    let downloadDiv = document.createElement("div");
    downloadDiv.id = downloadButtonId;
    downloadDiv.innerHTML = downloadSvg;
    downloadDiv.firstChild.style.cursor = 'hand';
    downloadDiv.style.position = 'fixed';
    downloadDiv.style.bottom = '120px';
    downloadDiv.style.right = '20px';
    downloadDiv.style.display = 'flex';
    downloadDiv.style.flexDirection = 'column';
    downloadDiv.style.alignItems = 'flex-end';
    downloadDiv.style.zIndex = '1000';

    let statsDiv = document.createElement("div");
    statsDiv.id = downloadStatusId;
    statsDiv.style.fontWeight = 500;
    statsDiv.style.alignSelf = 'center';
    statsDiv.style.color = '#158454';
    downloadDiv.appendChild(statsDiv);

    let updateStatus = (text) => {
      statsDiv.innerText = text;
    }

    downloadDiv.firstChild.addEventListener("click", async function () {
      downloadDiv.style.pointerEvents = 'none';
      downloadDiv.style.opacity = '0.5';

      try {
        let token = originalRequest._requestHeaders['Authorization'];
        await downloadAction(originalRequest, originalPostData, token, updateStatus);
      } catch (error) {
        console.error('Erro ao realizar ação de download:', error);
      } finally {
        downloadDiv.style.pointerEvents = 'auto';
        downloadDiv.style.opacity = '1';
      }

      this.disabled = false;
    });

    let beamerSelector = document.getElementById(beamerSelectorId);
    document.body.insertBefore(downloadDiv, beamerSelector);
  }

  function createVidaPrevSheetsFor(result) {
    return [
      { name: 'Vida', data: result.vida },
      { name: 'Previdência', data: result.prev }
    ];
  }

  function createSheetsFor(sheetName, data) {
    return [
      { name: sheetName, data }
    ];
  }

})(XMLHttpRequest);