from flask import Flask, render_template, jsonify, request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import json
import math
import threading
import time

try:
    import yfinance as yf
except Exception:
    # O site continua funcionando mesmo se o yfinance estiver temporariamente indisponível.
    yf = None

app = Flask(__name__)

# Evita que HTML/API antigos fiquem presos no navegador/CDN após deploys.
# Arquivos estáticos usam versionamento (?v=...) nos templates.
@app.after_request
def stronger_no_cache_headers(response):
    path = request.path
    if path.startswith('/api/') or not path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# -----------------------------------------------------------------------------
# Configuração de dados externos e cache
# -----------------------------------------------------------------------------
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
HTTP_TIMEOUT = 5
QUOTE_CACHE_SECONDS = 45
CRYPTO_CACHE_SECONDS = 60
CALENDAR_CACHE_SECONDS = 15 * 60

QUOTE_CACHE = {"data": None, "timestamp": 0.0}
CRYPTO_CACHE = {"data": None, "timestamp": 0.0}
CALENDAR_CACHE = {"data": None, "timestamp": 0.0}

QUOTE_LOCK = threading.Lock()
CRYPTO_LOCK = threading.Lock()
CALENDAR_LOCK = threading.Lock()

CRYPTO_ASSETS = {
    "BTC": {"name": "Bitcoin", "coingecko": "bitcoin", "yahoo": "BTC-USD"},
    "ETH": {"name": "Ethereum", "coingecko": "ethereum", "yahoo": "ETH-USD"},
    "XRP": {"name": "XRP", "coingecko": "ripple", "yahoo": "XRP-USD"},
    "BNB": {"name": "BNB", "coingecko": "binancecoin", "yahoo": "BNB-USD"},
    "SOL": {"name": "Solana", "coingecko": "solana", "yahoo": "SOL-USD"},
    "LTC": {"name": "Litecoin", "coingecko": "litecoin", "yahoo": "LTC-USD"},
    "XLM": {"name": "Stellar", "coingecko": "stellar", "yahoo": "XLM-USD"},
    "HBAR": {"name": "Hedera", "coingecko": "hedera-hashgraph", "yahoo": "HBAR-USD"},
    "LINK": {"name": "Chainlink", "coingecko": "chainlink", "yahoo": "LINK-USD"},
    "ONDO": {"name": "Ondo", "coingecko": "ondo-finance", "yahoo": "ONDO-USD"},
}

WEEKDAYS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _positive_number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _json_from_url(url, timeout=HTTP_TIMEOUT):
    """Busca JSON com timeout curto e cabeçalhos compatíveis com APIs públicas."""
    request = Request(
        url,
        headers={
            "User-Agent": "StrongerCity/2.0 (+https://strongercity.com.br)",
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _yahoo_chart_price(symbol):
    """Fallback leve do Yahoo Chart, sem depender do objeto Ticker do yfinance."""
    try:
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(symbol, safe='')}?interval=1m&range=1d"
        )
        payload = _json_from_url(url)
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return None
        meta = result[0].get("meta") or {}
        for field in ("regularMarketPrice", "previousClose", "chartPreviousClose"):
            price = _positive_number(meta.get(field))
            if price is not None:
                return price
        closes = (((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
        for value in reversed(closes):
            price = _positive_number(value)
            if price is not None:
                return price
    except Exception as exc:
        app.logger.warning("Falha Yahoo Chart %s: %s", symbol, exc)
    return None


def _yfinance_price(symbol):
    if yf is None:
        return None
    try:
        ticker = yf.Ticker(symbol)
        try:
            price = _positive_number(ticker.fast_info.get("last_price"))
            if price is not None:
                return price
        except Exception:
            pass
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            return _positive_number(hist["Close"].dropna().iloc[-1])
    except Exception as exc:
        app.logger.warning("Falha yfinance %s: %s", symbol, exc)
    return None


def _gold_price():
    # 1) Fonte dedicada de ouro; 2) spot Yahoo; 3) futuro GC; 4) yfinance.
    try:
        payload = _json_from_url("https://api.gold-api.com/price/XAU")
        price = _positive_number(payload.get("price"))
        if price is not None:
            return price, "Gold API"
    except Exception as exc:
        app.logger.warning("Falha Gold API: %s", exc)

    for symbol, label in (("XAUUSD=X", "Yahoo XAU/USD"), ("GC=F", "Yahoo Gold Futures")):
        price = _yahoo_chart_price(symbol)
        if price is not None:
            return price, label

    for symbol, label in (("XAUUSD=X", "yfinance XAU/USD"), ("GC=F", "yfinance Gold Futures")):
        price = _yfinance_price(symbol)
        if price is not None:
            return price, label
    return None, None


def _awesome_usdbrl():
    try:
        payload = _json_from_url("https://economia.awesomeapi.com.br/json/last/USD-BRL")
        item = payload.get("USDBRL") or {}
        bid = _positive_number(item.get("bid"))
        ask = _positive_number(item.get("ask"))
        if bid is not None and ask is not None:
            return (bid + ask) / 2, "AwesomeAPI"
        price = bid or ask
        if price is not None:
            return price, "AwesomeAPI"
    except Exception as exc:
        app.logger.warning("Falha AwesomeAPI USD/BRL: %s", exc)
    return None, None


def _frankfurter_usdbrl():
    sources = (
        ("https://api.frankfurter.dev/v2/rate/USD/BRL?providers=BCB", "BCB/PTAX via Frankfurter"),
        ("https://api.frankfurter.dev/v2/rate/USD/BRL", "Frankfurter"),
    )
    for url, label in sources:
        try:
            payload = _json_from_url(url)
            price = _positive_number(payload.get("rate"))
            if price is not None:
                return price, label
        except Exception as exc:
            app.logger.warning("Falha %s: %s", label, exc)
    return None, None


def _usdbrl_price():
    price, source = _awesome_usdbrl()
    if price is not None:
        return price, source

    price = _yahoo_chart_price("BRL=X")
    if price is not None:
        return price, "Yahoo USD/BRL"

    price, source = _frankfurter_usdbrl()
    if price is not None:
        return price, source

    price = _yfinance_price("BRL=X")
    if price is not None:
        return price, "yfinance USD/BRL"
    return None, None


def _coingecko_prices(symbols=None):
    symbols = list(symbols or CRYPTO_ASSETS.keys())
    ids = ",".join(CRYPTO_ASSETS[symbol]["coingecko"] for symbol in symbols)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    payload = _json_from_url(url)
    prices = {}
    for symbol in symbols:
        asset = CRYPTO_ASSETS[symbol]
        item = payload.get(asset["coingecko"]) or {}
        price = _positive_number(item.get("usd"))
        if price is not None:
            prices[symbol] = price
    return prices


def fetch_crypto_prices(force=False):
    now = time.time()
    cached = CRYPTO_CACHE.get("data")
    if not force and cached and now - CRYPTO_CACHE["timestamp"] < CRYPTO_CACHE_SECONDS:
        return cached

    with CRYPTO_LOCK:
        now = time.time()
        cached = CRYPTO_CACHE.get("data")
        if not force and cached and now - CRYPTO_CACHE["timestamp"] < CRYPTO_CACHE_SECONDS:
            return cached

        prices = {}
        sources = {}
        fresh_symbols = set()

        try:
            cg_prices = _coingecko_prices()
            for symbol, price in cg_prices.items():
                prices[symbol] = price
                sources[symbol] = "CoinGecko"
                fresh_symbols.add(symbol)
        except Exception as exc:
            app.logger.warning("Falha CoinGecko: %s", exc)

        # Fallback em paralelo apenas para moedas ausentes, evitando atrasar a página.
        missing = [symbol for symbol in CRYPTO_ASSETS if symbol not in prices]
        if missing:
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {
                    symbol: pool.submit(_yahoo_chart_price, CRYPTO_ASSETS[symbol]["yahoo"])
                    for symbol in missing
                }
                for symbol, future in futures.items():
                    price = future.result()
                    if price is not None:
                        prices[symbol] = price
                        sources[symbol] = "Yahoo"
                        fresh_symbols.add(symbol)

        # Se uma fonte falhar momentaneamente, preserva o último preço válido em memória.
        previous_prices = (cached or {}).get("prices") or {}
        previous_sources = (cached or {}).get("sources") or {}
        stale_symbols = []
        for symbol in CRYPTO_ASSETS:
            if symbol not in prices and symbol in previous_prices:
                prices[symbol] = previous_prices[symbol]
                sources[symbol] = previous_sources.get(symbol, "cache")
                stale_symbols.append(symbol)

        data = {
            "prices": {symbol: round(price, 8) for symbol, price in prices.items()},
            "sources": sources,
            "assets": {
                symbol: {"symbol": symbol, "name": asset["name"]}
                for symbol, asset in CRYPTO_ASSETS.items()
            },
            "stale_symbols": stale_symbols,
            "updated_at": int(now),
        }

        # Guarda cache mesmo parcial; ele é melhor do que voltar a "--" em falhas transitórias.
        if prices:
            CRYPTO_CACHE["data"] = data
            CRYPTO_CACHE["timestamp"] = now
        elif cached:
            return cached
        return data


def _btc_price():
    # Reaproveita o cache do conversor quando disponível e recente.
    cached = CRYPTO_CACHE.get("data")
    if cached and time.time() - CRYPTO_CACHE["timestamp"] < CRYPTO_CACHE_SECONDS:
        price = _positive_number((cached.get("prices") or {}).get("BTC"))
        if price is not None:
            source = (cached.get("sources") or {}).get("BTC", "Crypto cache")
            return price, source, "BTC" in (cached.get("stale_symbols") or [])

    try:
        price = _positive_number(_coingecko_prices(["BTC"]).get("BTC"))
        if price is not None:
            return price, "CoinGecko", False
    except Exception as exc:
        app.logger.warning("Falha CoinGecko BTC: %s", exc)

    price = _yahoo_chart_price("BTC-USD")
    if price is not None:
        return price, "Yahoo BTC/USD", False

    price = _yfinance_price("BTC-USD")
    if price is not None:
        return price, "yfinance BTC/USD", False
    return None, None, False


def fetch_quotes(force=False):
    now = time.time()
    cached = QUOTE_CACHE.get("data")
    if not force and cached and now - QUOTE_CACHE["timestamp"] < QUOTE_CACHE_SECONDS:
        return cached

    with QUOTE_LOCK:
        now = time.time()
        cached = QUOTE_CACHE.get("data")
        if not force and cached and now - QUOTE_CACHE["timestamp"] < QUOTE_CACHE_SECONDS:
            return cached

        with ThreadPoolExecutor(max_workers=3) as pool:
            gold_future = pool.submit(_gold_price)
            btc_future = pool.submit(_btc_price)
            usdbrl_future = pool.submit(_usdbrl_price)
            gold, gold_source = gold_future.result()
            btc, btc_source, btc_stale = btc_future.result()
            usdbrl, usdbrl_source = usdbrl_future.result()

        previous = cached or {}
        stale = {"xauusd": False, "btc": btc_stale, "usdbrl": False}

        if gold is None and previous.get("xauusd") is not None:
            gold = previous["xauusd"]
            gold_source = (previous.get("sources") or {}).get("xauusd", "cache")
            stale["xauusd"] = True
        if btc is None and previous.get("btc") is not None:
            btc = previous["btc"]
            btc_source = (previous.get("sources") or {}).get("btc", "cache")
            stale["btc"] = True
        if usdbrl is None and previous.get("usdbrl") is not None:
            usdbrl = previous["usdbrl"]
            usdbrl_source = (previous.get("sources") or {}).get("usdbrl", "cache")
            stale["usdbrl"] = True

        data = {
            "xauusd": round(gold, 2) if gold is not None else None,
            "btc": round(btc, 2) if btc is not None else None,
            "usdbrl": round(usdbrl, 4) if usdbrl is not None else None,
            "sources": {
                "xauusd": gold_source,
                "btc": btc_source,
                "usdbrl": usdbrl_source,
            },
            "stale": stale,
            "updated_at": int(now),
        }

        if any(data[key] is not None for key in ("xauusd", "btc", "usdbrl")):
            QUOTE_CACHE["data"] = data
            QUOTE_CACHE["timestamp"] = now
        elif cached:
            return cached
        return data


def _parse_calendar_event(raw):
    date_raw = str(raw.get("date") or "").strip()
    if not date_raw:
        return None

    try:
        dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(BRASILIA_TZ)
    except ValueError:
        return None

    impact = str(raw.get("impact") or "").strip() or "Unknown"
    country = str(raw.get("country") or "").strip().upper() or "ALL"
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    return {
        "title": title,
        "country": country,
        "impact": impact,
        "forecast": str(raw.get("forecast") or "").strip(),
        "previous": str(raw.get("previous") or "").strip(),
        "actual": str(raw.get("actual") or "").strip(),
        "timestamp": int(local.timestamp()),
        "iso_brasilia": local.isoformat(),
        "date_key": local.strftime("%Y-%m-%d"),
        "time": local.strftime("%H:%M"),
        "date_label": f"{WEEKDAYS_PT[local.weekday()]}, {local.day} de {MONTHS_PT[local.month - 1]}",
    }


def _fetch_calendar_feed():
    urls = (
        ("https://nfs.faireconomy.media/ff_calendar_thisweek.json", "Fair Economy / Forex Factory"),
        ("https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json", "Fair Economy CDN / Forex Factory"),
    )
    last_error = None
    for url, source in urls:
        try:
            payload = _json_from_url(url, timeout=7)
            if isinstance(payload, list):
                return payload, source
        except Exception as exc:
            last_error = exc
            app.logger.warning("Falha calendário %s: %s", source, exc)
    if last_error:
        raise last_error
    raise RuntimeError("Feed de calendário indisponível")


def fetch_economic_calendar(force=False):
    now = time.time()
    cached = CALENDAR_CACHE.get("data")
    if not force and cached and now - CALENDAR_CACHE["timestamp"] < CALENDAR_CACHE_SECONDS:
        return cached

    with CALENDAR_LOCK:
        now = time.time()
        cached = CALENDAR_CACHE.get("data")
        if not force and cached and now - CALENDAR_CACHE["timestamp"] < CALENDAR_CACHE_SECONDS:
            return cached

        try:
            raw_events, source = _fetch_calendar_feed()
            events = [event for event in (_parse_calendar_event(item) for item in raw_events) if event]
            events.sort(key=lambda event: event["timestamp"])
            currencies = sorted({event["country"] for event in events if event["country"]})
            data = {
                "events": events,
                "currencies": currencies,
                "source": source,
                "timezone": "America/Sao_Paulo",
                "stale": False,
                "updated_at": int(now),
            }
            CALENDAR_CACHE["data"] = data
            CALENDAR_CACHE["timestamp"] = now
            return data
        except Exception as exc:
            if cached:
                stale_data = dict(cached)
                stale_data["stale"] = True
                stale_data["error"] = str(exc)
                return stale_data
            raise


# -----------------------------------------------------------------------------
# Páginas
# -----------------------------------------------------------------------------
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


@app.route("/calendario-economico")
def calendario_economico():
    return render_template("calendario_economico.html")


@app.route("/conversor-cripto")
def conversor_cripto():
    return render_template("conversor_cripto.html", assets=CRYPTO_ASSETS)


# -----------------------------------------------------------------------------
# APIs internas consumidas pelo front-end
# -----------------------------------------------------------------------------
@app.route("/api/quotes")
def api_quotes():
    try:
        data = fetch_quotes()
        ok = any(data.get(key) is not None for key in ("xauusd", "btc", "usdbrl"))
        return jsonify({"ok": ok, **data}), (200 if ok else 503)
    except Exception as exc:
        app.logger.exception("Falha geral ao atualizar cotações")
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.route("/api/crypto-prices")
def api_crypto_prices():
    try:
        data = fetch_crypto_prices()
        ok = bool(data.get("prices"))
        return jsonify({"ok": ok, **data}), (200 if ok else 503)
    except Exception as exc:
        app.logger.exception("Falha geral ao atualizar criptomoedas")
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.route("/api/economic-calendar")
def api_economic_calendar():
    try:
        data = fetch_economic_calendar()
        return jsonify({"ok": True, **data})
    except Exception as exc:
        app.logger.exception("Falha geral ao atualizar calendário")
        return jsonify({"ok": False, "error": str(exc), "events": []}), 503


if __name__ == "__main__":
    # Abra http://127.0.0.1:5000 no navegador.
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
