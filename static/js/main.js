(() => {
  const numberFormat = new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function setQuoteValue(id, value) {
    const el = document.getElementById(id);
    if (!el || value == null || !Number.isFinite(Number(value))) return false;
    el.textContent = numberFormat.format(Number(value));
    el.classList.add('is-live');
    return true;
  }

  async function fetchJson(url, timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha na atualização');
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  async function updateQuotes() {
    const status = document.getElementById('quote-status-text');
    const dot = document.getElementById('quote-dot');
    if (!status) return;

    try {
      const data = await fetchJson('/api/quotes');
      const updated = [
        setQuoteValue('quote-xau', data.xauusd),
        setQuoteValue('quote-btc', data.btc),
        setQuoteValue('quote-usdbrl', data.usdbrl),
      ].some(Boolean);

      const stale = data.stale && Object.values(data.stale).some(Boolean);
      if (updated || stale) {
        status.textContent = stale
          ? 'Mercado online • exibindo última cotação válida em uma das fontes'
          : 'Cotações atualizadas • dados de mercado podem ter atraso';
        dot?.classList.add('live');
      }
    } catch (error) {
      // Nunca apaga valores que já estavam válidos na tela.
      status.textContent = 'Atualização temporariamente indisponível • mantendo última cotação';
      dot?.classList.remove('live');
    }
  }

  function setupMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    const backdrop = document.getElementById('mobile-menu-backdrop');
    const toggles = [...document.querySelectorAll('.mobile-menu-toggle')];
    const closeButton = document.querySelector('.mobile-menu-close');
    if (!menu || !backdrop || !toggles.length) return;

    const setOpen = (open) => {
      document.body.classList.toggle('mobile-menu-open', open);
      menu.classList.toggle('is-open', open);
      menu.setAttribute('aria-hidden', String(!open));
      backdrop.hidden = !open;
      requestAnimationFrame(() => backdrop.classList.toggle('is-open', open));
      toggles.forEach((button) => button.setAttribute('aria-expanded', String(open)));
      if (open) closeButton?.focus({ preventScroll: true });
    };

    toggles.forEach((button) => button.addEventListener('click', () => setOpen(true)));
    closeButton?.addEventListener('click', () => setOpen(false));
    backdrop.addEventListener('click', () => setOpen(false));
    menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setOpen(false)));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && menu.classList.contains('is-open')) setOpen(false);
    });
  }

  setupMobileMenu();
  updateQuotes();
  window.setInterval(updateQuotes, 45000);
})();
