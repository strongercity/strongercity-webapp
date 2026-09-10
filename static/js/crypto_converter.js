(() => {
  const root = document.getElementById('crypto-converter');
  if (!root) return;

  const state = { prices: {}, assets: {}, staleSymbols: [] };
  const assetEl = document.getElementById('crypto-asset');
  const directionEl = document.getElementById('crypto-direction');
  const amountEl = document.getElementById('crypto-amount');
  const prefixEl = document.getElementById('crypto-input-prefix');
  const rateEl = document.getElementById('crypto-rate');
  const rateLabelEl = document.getElementById('crypto-rate-label');
  const statusEl = document.getElementById('crypto-status');
  const resultEl = document.getElementById('crypto-converted-value');
  const detailEl = document.getElementById('crypto-conversion-detail');
  const watermarkEl = document.getElementById('crypto-watermark');
  const gridEl = document.getElementById('crypto-rates-grid');

  const usd = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function formatCrypto(value, symbol) {
    if (!Number.isFinite(value)) return '--';
    const abs = Math.abs(value);
    const max = abs >= 1000 ? 2 : abs >= 1 ? 6 : 8;
    return `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: max }).format(value)} ${symbol}`;
  }

  function formatRate(value) {
    if (!Number.isFinite(value)) return 'US$ --';
    return usd.format(value);
  }

  function selectedPrice() {
    return Number(state.prices[assetEl.value]);
  }

  function convert() {
    const symbol = assetEl.value;
    const price = selectedPrice();
    const amount = Number(amountEl.value || 0);
    const cryptoToUsd = directionEl.value === 'crypto-usd';

    prefixEl.textContent = cryptoToUsd ? symbol : 'US$';
    rateLabelEl.textContent = `COTAÇÃO ATUAL • ${symbol}/USD`;
    watermarkEl.textContent = symbol;

    if (!Number.isFinite(price) || price <= 0) {
      resultEl.textContent = '--';
      detailEl.textContent = `Cotação de ${symbol} indisponível no momento.`;
      return;
    }

    rateEl.textContent = formatRate(price);
    if (!Number.isFinite(amount) || amount < 0) return;

    if (cryptoToUsd) {
      const out = amount * price;
      resultEl.textContent = usd.format(out);
      detailEl.textContent = `${formatCrypto(amount, symbol)} × ${usd.format(price)} = ${usd.format(out)}`;
    } else {
      const out = amount / price;
      resultEl.textContent = formatCrypto(out, symbol);
      detailEl.textContent = `${usd.format(amount)} ÷ ${usd.format(price)} = ${formatCrypto(out, symbol)}`;
    }
  }

  function renderRates() {
    gridEl.innerHTML = '';
    const symbols = Object.keys(state.assets);
    symbols.forEach((symbol) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'crypto-rate-card';
      if (symbol === assetEl.value) card.classList.add('is-active');
      card.addEventListener('click', () => {
        assetEl.value = symbol;
        renderRates();
        convert();
      });

      const top = document.createElement('span');
      top.className = 'crypto-rate-card-top';
      const code = document.createElement('strong');
      code.textContent = symbol;
      const name = document.createElement('small');
      name.textContent = state.assets[symbol]?.name || symbol;
      top.append(code, name);

      const price = document.createElement('b');
      price.textContent = Number.isFinite(Number(state.prices[symbol]))
        ? formatRate(Number(state.prices[symbol]))
        : '--';

      const stale = document.createElement('i');
      stale.textContent = state.staleSymbols.includes(symbol) ? 'última cotação válida' : 'USD';
      card.append(top, price, stale);
      gridEl.appendChild(card);
    });
  }

  async function loadPrices() {
    try {
      const response = await fetch('/api/crypto-prices', { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha');

      state.prices = { ...state.prices, ...(data.prices || {}) };
      state.assets = data.assets || state.assets;
      state.staleSymbols = data.stale_symbols || [];
      statusEl.textContent = state.staleSymbols.length
        ? 'Mercado online • algumas moedas usam a última cotação válida'
        : 'Cotações atualizadas automaticamente';
      renderRates();
      convert();
    } catch (error) {
      statusEl.textContent = Object.keys(state.prices).length
        ? 'Atualização temporariamente indisponível • mantendo últimas cotações'
        : 'Cotações indisponíveis no momento';
    }
  }

  assetEl.addEventListener('change', () => { renderRates(); convert(); });
  directionEl.addEventListener('change', convert);
  amountEl.addEventListener('input', convert);
  document.getElementById('crypto-convert-btn').addEventListener('click', convert);

  loadPrices();
  window.setInterval(loadPrices, 60000);
})();
