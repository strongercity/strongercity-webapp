from flask import Flask, render_template, jsonify
import json
import math
import time
from urllib.request import Request, urlopen

try:
    import yfinance as yf
except Exception:
    # O site continua abrindo mesmo se a biblioteca de cotações não estiver disponível.
    yf = None

app = Flask(__name__)

# Cache simples para evitar chamadas excessivas ao Yahoo Finance.
QUOTE_CACHE = {"data": None, "timestamp": 0}
CACHE_SECONDS = 30


def _last_price(symbols):
    """Retorna o primeiro preço válido encontrado entre os símbolos informados."""
    if yf is None:
        return None, None
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            price = None
            try:
                price = ticker.fast_info.get("last_price")
            except Exception:
                pass
            if price is None or not math.isfinite(float(price)):
                hist = ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    price = float(hist["Close"].dropna().iloc[-1])
            if price is not None and math.isfinite(float(price)):
                return float(price), symbol
        except Exception as exc:
            # Mantém o site funcionando, mas registra a falha no log da Railway.
            app.logger.warning("Falha ao consultar %s no Yahoo Finance: %s", symbol, exc)
            continue
    return None, None


def _json_from_url(url, timeout=8):
    """Busca JSON por HTTP usando apenas a biblioteca padrão do Python."""
    request = Request(
        url,
        headers={
            "User-Agent": "StrongerCity/1.0 (+https://strongercity.com.br)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _usdbrl_fallback():
    """
    Fallback do USD/BRL quando o Yahoo Finance falhar.

    1) Frankfurter filtrado pelo Banco Central do Brasil (PTAX).
    2) Frankfurter com taxa combinada de provedores.

    Nenhuma das duas opções exige chave de API.
    """
    sources = [
        (
            "https://api.frankfurter.dev/v2/rate/USD/BRL?providers=BCB",
            "BCB/PTAX via Frankfurter",
        ),
        (
            "https://api.frankfurter.dev/v2/rate/USD/BRL",
            "Frankfurter",
        ),
    ]

    for url, source in sources:
        try:
            payload = _json_from_url(url)
            price = payload.get("rate")
            if price is not None and math.isfinite(float(price)) and float(price) > 0:
                return float(price), source
        except Exception as exc:
            app.logger.warning("Falha no fallback USD/BRL (%s): %s", source, exc)

    return None, None


def _usdbrl_price():
    """Tenta Yahoo primeiro e troca automaticamente para uma fonte reserva."""
    price, source = _last_price(["BRL=X"])
    if price is not None:
        return price, source
    return _usdbrl_fallback()


def fetch_quotes():
    now = time.time()
    if QUOTE_CACHE["data"] and now - QUOTE_CACHE["timestamp"] < CACHE_SECONDS:
        return QUOTE_CACHE["data"]

    # Tenta spot do ouro primeiro e usa futuro do ouro como fallback.
    gold, gold_symbol = _last_price(["XAUUSD=X", "GC=F"])
    btc, btc_symbol = _last_price(["BTC-USD"])
    usdbrl, usdbrl_symbol = _usdbrl_price()

    data = {
        "xauusd": round(gold, 2) if gold is not None else None,
        "btc": round(btc, 2) if btc is not None else None,
        "usdbrl": round(usdbrl, 2) if usdbrl is not None else None,
        "sources": {
            "xauusd": gold_symbol,
            "btc": btc_symbol,
            "usdbrl": usdbrl_symbol,
        },
        "updated_at": int(now),
    }
    QUOTE_CACHE["data"] = data
    QUOTE_CACHE["timestamp"] = now
    return data


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/forex-sessions")
def forex_sessions():
    return render_template("forex_sessions.html")


@app.route("/dolar-hoje")
def dolar_hoje():
    return render_template("dolar_hoje.html")


@app.route("/quem-somos")
def quem_somos():
    return render_template("quem_somos.html")


@app.route("/calculadora-forex")
def calculadora_forex():
    return render_template("calculadora_forex.html")


@app.route("/api/quotes")
def api_quotes():
    try:
        return jsonify({"ok": True, **fetch_quotes()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


if __name__ == "__main__":
    # Abra http://127.0.0.1:5000 no navegador.
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
