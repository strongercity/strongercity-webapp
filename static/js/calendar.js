(() => {
  const root = document.getElementById('economic-calendar');
  if (!root) return;

  const state = { events: [], view: 'today', source: '', stale: false };
  const listEl = document.getElementById('calendar-list');
  const currencyEl = document.getElementById('calendar-currency');
  const impactEl = document.getElementById('calendar-impact');
  const statusEl = document.getElementById('calendar-status');
  const liveDotEl = document.getElementById('calendar-live-dot');
  const refreshEl = document.getElementById('calendar-refresh');

  function brasiliaDateKey() {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(new Date());
    const map = Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
    return `${map.year}-${map.month}-${map.day}`;
  }

  function impactKey(value) {
    const text = String(value || '').toLowerCase();
    if (text.includes('high')) return 'high';
    if (text.includes('medium') || text.includes('med')) return 'medium';
    if (text.includes('low')) return 'low';
    if (text.includes('holiday')) return 'holiday';
    return 'other';
  }

  function impactLabel(value) {
    const key = impactKey(value);
    return ({ high: 'Alto', medium: 'Médio', low: 'Baixo', holiday: 'Feriado', other: 'Informativo' })[key];
  }

  function valueBox(label, value) {
    const box = document.createElement('div');
    box.className = 'calendar-value';
    const small = document.createElement('small');
    small.textContent = label;
    const strong = document.createElement('strong');
    strong.textContent = value || '—';
    box.append(small, strong);
    return box;
  }

  function eventCard(event) {
    const card = document.createElement('article');
    const impact = impactKey(event.impact);
    card.className = `calendar-event impact-${impact}`;

    const time = document.createElement('div');
    time.className = 'calendar-event-time';
    const timeStrong = document.createElement('strong');
    timeStrong.textContent = event.time || '--:--';
    const currency = document.createElement('span');
    currency.textContent = event.country || 'ALL';
    time.append(timeStrong, currency);

    const content = document.createElement('div');
    content.className = 'calendar-event-content';
    const meta = document.createElement('div');
    meta.className = 'calendar-event-meta';
    const badge = document.createElement('span');
    badge.className = `impact-badge impact-${impact}`;
    badge.textContent = impactLabel(event.impact);
    const date = document.createElement('small');
    date.textContent = event.date_label || '';
    meta.append(badge, date);
    const title = document.createElement('h3');
    title.textContent = event.title;
    content.append(meta, title);

    const values = document.createElement('div');
    values.className = 'calendar-event-values';
    values.append(
      valueBox('ATUAL', event.actual),
      valueBox('PREVISÃO', event.forecast),
      valueBox('ANTERIOR', event.previous),
    );

    card.append(time, content, values);
    return card;
  }

  function render() {
    const today = brasiliaDateKey();
    const currency = currencyEl.value;
    const impact = impactEl.value;
    const filtered = state.events.filter((event) => {
      if (state.view === 'today' && event.date_key !== today) return false;
      if (currency !== 'all' && event.country !== currency) return false;
      if (impact !== 'all' && impactKey(event.impact) !== impact) return false;
      return true;
    });

    listEl.innerHTML = '';
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'calendar-empty';
      empty.innerHTML = '<strong>Nenhum evento encontrado.</strong><span>Tente visualizar a semana ou alterar os filtros.</span>';
      listEl.appendChild(empty);
      return;
    }

    let lastDate = '';
    filtered.forEach((event) => {
      if (state.view === 'week' && event.date_key !== lastDate) {
        const divider = document.createElement('div');
        divider.className = 'calendar-day-divider';
        divider.textContent = event.date_label;
        listEl.appendChild(divider);
        lastDate = event.date_key;
      }
      listEl.appendChild(eventCard(event));
    });
  }

  function fillCurrencies(currencies) {
    const selected = currencyEl.value;
    currencyEl.innerHTML = '<option value="all">Todas</option>';
    currencies.forEach((currency) => {
      const option = document.createElement('option');
      option.value = currency;
      option.textContent = currency;
      currencyEl.appendChild(option);
    });
    if ([...currencyEl.options].some((option) => option.value === selected)) currencyEl.value = selected;
  }

  async function loadCalendar() {
    refreshEl.disabled = true;
    refreshEl.classList.add('is-loading');
    try {
      const response = await fetch('/api/economic-calendar', { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha');

      state.events = data.events || [];
      state.source = data.source || '';
      state.stale = Boolean(data.stale);
      fillCurrencies(data.currencies || []);
      statusEl.textContent = state.stale
        ? 'Exibindo o último calendário disponível'
        : `Calendário atualizado${state.source ? ` • ${state.source}` : ''}`;
      liveDotEl.classList.toggle('is-live', !state.stale);
      render();
    } catch (error) {
      statusEl.textContent = state.events.length
        ? 'Atualização indisponível • mantendo último calendário'
        : 'Não foi possível carregar o calendário agora';
      liveDotEl.classList.remove('is-live');
      if (!state.events.length) {
        listEl.innerHTML = '<div class="calendar-empty"><strong>Calendário temporariamente indisponível.</strong><span>Tente atualizar novamente em alguns instantes.</span></div>';
      }
    } finally {
      refreshEl.disabled = false;
      refreshEl.classList.remove('is-loading');
    }
  }

  document.querySelectorAll('[data-calendar-view]').forEach((button) => {
    button.addEventListener('click', () => {
      state.view = button.dataset.calendarView;
      document.querySelectorAll('[data-calendar-view]').forEach((item) => item.classList.toggle('is-active', item === button));
      render();
    });
  });
  currencyEl.addEventListener('change', render);
  impactEl.addEventListener('change', render);
  refreshEl.addEventListener('click', loadCalendar);

  loadCalendar();
  window.setInterval(loadCalendar, 15 * 60 * 1000);
})();
