let injectScripts = [
  'scripts/xlsx.full.min.js',
  'scripts/filesaver.min.js',
  'scripts/common.js',
  'scripts/inject.js',
  'scripts/customers.js',
  'scripts/pendingPayments.js',
  'scripts/proposalStatus.js'
]

injectScripts.forEach(injectScript => {
  let inject = document.createElement('script');
  inject.src = chrome.runtime.getURL(injectScript);
  inject.onload = function () {
    this.remove();
  };
  (document.head || document.documentElement).appendChild(inject);
});