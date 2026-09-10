(() => {
    const root = document.getElementById('calculator-app');
    if (!root) return;

    const countInput = document.getElementById('table-count');
    const stopInput = document.getElementById('stop-points');
    const deskInputs = document.getElementById('desk-inputs');
    const results = document.getElementById('calculator-results');
    const stopSummary = document.getElementById('stop-summary');
    const resultStopSummary = document.getElementById('result-stop-summary');
    const msgOne = document.getElementById('step-one-message');
    const msgTwo = document.getElementById('step-two-message');

    const state = { count: 0, stop: 0 };

    function parseNumber(value) {
        let clean = String(value ?? '').trim().replace(/\s/g, '');
        if (!clean) return NaN;
        if (clean.includes(',') && clean.includes('.')) {
            if (clean.lastIndexOf(',') > clean.lastIndexOf('.')) {
                clean = clean.replace(/\./g, '').replace(',', '.');
            } else {
                clean = clean.replace(/,/g, '');
            }
        } else if (clean.includes(',')) {
            clean = clean.replace(',', '.');
        }
        return Number(clean);
    }

    function formatNumber(value) {
        return new Intl.NumberFormat('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value);
    }

    function setStep(step) {
        root.querySelectorAll('[data-step]').forEach((section) => {
            section.classList.toggle('is-hidden', Number(section.dataset.step) !== step);
        });
        root.querySelectorAll('[data-step-dot]').forEach((dot) => {
            const n = Number(dot.dataset.stepDot);
            dot.classList.toggle('is-active', n <= step);
            dot.classList.toggle('is-current', n === step);
        });
        root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function buildDeskInputs() {
        deskInputs.innerHTML = '';
        for (let i = 1; i <= state.count; i += 1) {
            const label = document.createElement('label');
            label.className = 'field-card desk-field';
            label.innerHTML = `
                <span>Mesa ${String(i).padStart(2, '0')}</span>
                <div class="input-prefix-wrap"><b>US$</b><input data-desk-value="${i}" inputmode="decimal" type="text" placeholder="Valor de risco"></div>
            `;
            deskInputs.appendChild(label);
        }
    }

    document.getElementById('calculator-next').addEventListener('click', () => {
        msgOne.textContent = '';
        const count = Number.parseInt(countInput.value, 10);
        const stop = parseNumber(stopInput.value);

        if (!Number.isInteger(count) || count < 1 || count > 10) {
            msgOne.textContent = 'Digite uma quantidade de mesas entre 1 e 10.';
            return;
        }
        if (!Number.isFinite(stop) || stop <= 0) {
            msgOne.textContent = 'Digite uma quantidade válida de pontos de stop.';
            return;
        }

        state.count = count;
        state.stop = stop;
        stopSummary.textContent = `Stop da operação: ${formatNumber(stop)} pontos`;
        buildDeskInputs();
        setStep(2);
    });

    document.getElementById('calculator-back').addEventListener('click', () => setStep(1));

    document.getElementById('calculator-calc').addEventListener('click', () => {
        msgTwo.textContent = '';
        const inputs = [...deskInputs.querySelectorAll('[data-desk-value]')];
        const values = [];

        for (const input of inputs) {
            const value = parseNumber(input.value);
            if (!Number.isFinite(value) || value <= 0) {
                msgTwo.textContent = `Preencha corretamente o valor da Mesa ${input.dataset.deskValue}.`;
                input.focus();
                return;
            }
            values.push(value);
        }

        results.innerHTML = '';
        values.forEach((risk, index) => {
            const entry = risk / state.stop;
            const card = document.createElement('article');
            card.className = 'result-card';
            card.innerHTML = `
                <span>MESA ${String(index + 1).padStart(2, '0')}</span>
                <p>Para <strong>US$ ${formatNumber(risk)}</strong></p>
                <div class="result-number">${formatNumber(entry)}</div>
                <small>valor calculado para entrada</small>
            `;
            results.appendChild(card);
        });
        resultStopSummary.textContent = `Stop considerado: ${formatNumber(state.stop)} pontos`;
        setStep(3);
    });

    document.getElementById('calculator-reset').addEventListener('click', () => {
        state.count = 0;
        state.stop = 0;
        countInput.value = '';
        stopInput.value = '';
        deskInputs.innerHTML = '';
        results.innerHTML = '';
        msgOne.textContent = '';
        msgTwo.textContent = '';
        setStep(1);
    });

    setStep(1);
})();
