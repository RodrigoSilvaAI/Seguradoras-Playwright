const customHeaderName = 'customHeader';

function isCustomRequest(request) {
    return request._requestHeaders[customHeaderName] != undefined;
}

function toUTCDate(stringDate) {
    if (stringDate == null || typeof (stringDate) == 'undefined' || stringDate == '')
        return null;

    let date = new Date(stringDate);
    return new Date(date.getTime() + date.getTimezoneOffset() * 60000).toLocaleDateString();
}

// function exportToExcel(fileName, data) {
//     const worksheet = XLSX.utils.json_to_sheet(data);
//     const workbook = {
//         Sheets: {
//             'data': worksheet
//         },
//         SheetNames: ['data']
//     };
//     const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
//     const blobData = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;charset=UTF-8' });
//     saveAs(blobData, fileName);
// }

function exportToExcel(fileName, sheetsData) {
    const workbook = {
        Sheets: {},
        SheetNames: []
    };

    sheetsData.forEach(sheet => {
        if (sheet.data && sheet.data.length > 0) {
            const worksheet = XLSX.utils.json_to_sheet(sheet.data);
            workbook.Sheets[sheet.name] = worksheet;
            workbook.SheetNames.push(sheet.name);
        }
    });

    if (workbook.SheetNames.length === 0) {
        console.log('No data to export.');
        return;
    }

    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
    const blobData = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;charset=UTF-8' });
    saveAs(blobData, fileName);
}

function createGetRequest(url, token) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.setRequestHeader("Authorization", token);
    xhr.setRequestHeader(customHeaderName, '');

    return xhr;
}

async function sendRequest(originalRequest, postData, token) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(originalRequest._method, originalRequest._url, true);

        xhr.setRequestHeader("Authorization", token);
        xhr.setRequestHeader(customHeaderName, '');

        xhr.onload = function () {
            if (xhr.status >= 200 && xhr.status < 300) {
                if (xhr.responseText != '')
                    resolve(JSON.parse(xhr.responseText));
                else
                    resolve(null);

            } else {
                reject(new Error(`Erro na requisição: ${xhr.status} - ${xhr.statusText}`));
            }
        };

        xhr.onerror = function () {
            reject(new Error('Erro de rede ao fazer requisição.'));
        };

        if (originalRequest._method == 'POST' && postData != null && typeof (postData) != 'undefined') {
            xhr.setRequestHeader("Content-type", "application/json");
            xhr.send(postData);
        }
        else
            xhr.send();
    });
}

function createGetPromisse(identifier, url, token, errorMessage) {
    return () => new Promise((resolve, reject) => {
        try {
            var request = createGetRequest(url, token);
            request.send();
            request.onreadystatechange = function () {
                if (request.readyState == 4 && request.status == 200) {
                    resolve({ identifier: identifier, data: request.responseText });
                }

                if (request.readyState == 4 && request.status != 200) {
                    reject(request.status);
                }
            }
        } catch (error) {
            reject(error);
        }
    }).catch(function (error) {
        console.log(errorMessage, error);
    })
}

function joinArray(arr, delimiter, property) {
    if (arr && Array.isArray(arr)) {
        const values = arr.map(item => item[property]);
        return values.join(delimiter);
    } else {
        return '';
    }
}

function toFormattedLineOfBusiness(value) {
    switch (value) {
        case 'PREV':
            return 'Previdência';
        case 'VIDA':
            return 'Vida';
        default:
            return value
    }
}

function toProductStatus(customerProduct) {
    let value = '';
    switch (customerProduct.linhaNegocio) {
        case 'PREV':
            value = customerProduct.situacaoCertificado;
            break;
        case 'VIDA':
            value = customerProduct.situacaoTitulo
        default:
            break;
    }

    switch (value) {
        case 'A':
            return 'Ativo';
        case 'C':
            return 'Cancelado';
        default:
            return value
    }
}

function cloneDeep(obj) {
    if (obj === null || typeof obj !== 'object') {
      return obj;
    }
  
    if (Array.isArray(obj)) {
      return obj.map(item => cloneDeep(item));
    }
  
    const copy = {};
    for (let key in obj) {
      if (obj.hasOwnProperty(key)) {
        copy[key] = cloneDeep(obj[key]);
      }
    }
  
    return copy;
  }