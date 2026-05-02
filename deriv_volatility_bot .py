import requests
import time
import json
import signal
import sys
import os
import websocket
import threading
import statistics
from datetime import datetime

# Configuration Telegram
TELEGRAM_TOKEN = "8149409815:AAGgC9IWsyQh4m5TlAuGDTJtBcgLkTPr3ao"
TELEGRAM_CHAT_ID = "1028710661"

# Configuration Deriv API
DERIV_API_TOKEN = "lBTikfXnyMUDW8E"
DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Configuration Deriv Volatility Indices
VOLATILITY_INDICES = {
    'R_10':  {'name': 'Volatility 10 Index',  'symbol': 'R_10',  'type': 'volatility', 'tp_ticks': 15, 'sl_ticks': 10, 'timeframe': '1-5 min'},
    'R_25':  {'name': 'Volatility 25 Index',  'symbol': 'R_25',  'type': 'volatility', 'tp_ticks': 20, 'sl_ticks': 12, 'timeframe': '1-5 min'},
    'R_50':  {'name': 'Volatility 50 Index',  'symbol': 'R_50',  'type': 'volatility', 'tp_ticks': 25, 'sl_ticks': 15, 'timeframe': '1-5 min'},
    'R_75':  {'name': 'Volatility 75 Index',  'symbol': 'R_75',  'type': 'volatility', 'tp_ticks': 30, 'sl_ticks': 18, 'timeframe': '1-5 min'},
    'R_100': {'name': 'Volatility 100 Index', 'symbol': 'R_100', 'type': 'volatility', 'tp_ticks': 35, 'sl_ticks': 20, 'timeframe': '1-5 min'},
}

# Paires Forex
FOREX_PAIRS = {
    'frxEURUSD': {'name': 'EUR/USD', 'symbol': 'frxEURUSD', 'type': 'forex', 'tp_ticks': 0.0020, 'sl_ticks': 0.0012, 'timeframe': '5-15 min'},
    'frxGBPUSD': {'name': 'GBP/USD', 'symbol': 'frxGBPUSD', 'type': 'forex', 'tp_ticks': 0.0025, 'sl_ticks': 0.0015, 'timeframe': '5-15 min'},
    'frxUSDJPY': {'name': 'USD/JPY', 'symbol': 'frxUSDJPY', 'type': 'forex', 'tp_ticks': 0.25,   'sl_ticks': 0.15,   'timeframe': '5-15 min'},
    'frxGBPJPY': {'name': 'GBP/JPY', 'symbol': 'frxGBPJPY', 'type': 'forex', 'tp_ticks': 0.35,   'sl_ticks': 0.20,   'timeframe': '5-15 min'},
    'frxEURGBP': {'name': 'EUR/GBP', 'symbol': 'frxEURGBP', 'type': 'forex', 'tp_ticks': 0.0018, 'sl_ticks': 0.0010, 'timeframe': '5-15 min'},
}

# Crash/Boom/Jump Indices
CRASH_BOOM_INDICES = {
    'CRASH500':  {'name': 'Crash 500 Index',  'symbol': 'CRASH500',  'type': 'crash',  'tp_ticks': 500, 'sl_ticks': 300, 'timeframe': '1-3 min'},
    'CRASH1000': {'name': 'Crash 1000 Index', 'symbol': 'CRASH1000', 'type': 'crash',  'tp_ticks': 800, 'sl_ticks': 500, 'timeframe': '1-3 min'},
    'BOOM500':   {'name': 'Boom 500 Index',   'symbol': 'BOOM500',   'type': 'boom',   'tp_ticks': 500, 'sl_ticks': 300, 'timeframe': '1-3 min'},
    'BOOM1000':  {'name': 'Boom 1000 Index',  'symbol': 'BOOM1000',  'type': 'boom',   'tp_ticks': 800, 'sl_ticks': 500, 'timeframe': '1-3 min'},
    'JD10':      {'name': 'Jump 10 Index',    'symbol': 'JD10',      'type': 'jump',   'tp_ticks': 15,  'sl_ticks': 10,  'timeframe': '1-5 min'},
    'JD25':      {'name': 'Jump 25 Index',    'symbol': 'JD25',      'type': 'jump',   'tp_ticks': 20,  'sl_ticks': 12,  'timeframe': '1-5 min'},
    'JD50':      {'name': 'Jump 50 Index',    'symbol': 'JD50',      'type': 'jump',   'tp_ticks': 25,  'sl_ticks': 15,  'timeframe': '1-5 min'},
    'JD75':      {'name': 'Jump 75 Index',    'symbol': 'JD75',      'type': 'jump',   'tp_ticks': 30,  'sl_ticks': 18,  'timeframe': '1-5 min'},
    'JD100':     {'name': 'Jump 100 Index',   'symbol': 'JD100',     'type': 'jump',   'tp_ticks': 35,  'sl_ticks': 20,  'timeframe': '1-5 min'},
    'RDBEAR':    {'name': 'Bear Market Index','symbol': 'RDBEAR',    'type': 'bear',   'tp_ticks': 20,  'sl_ticks': 12,  'timeframe': '1-5 min'},
    'RDBULL':    {'name': 'Bull Market Index','symbol': 'RDBULL',    'type': 'bull',   'tp_ticks': 20,  'sl_ticks': 12,  'timeframe': '1-5 min'},
}

# Tous les instruments
ALL_INSTRUMENTS = {**VOLATILITY_INDICES, **FOREX_PAIRS, **CRASH_BOOM_INDICES}

CHECK_INTERVAL = 30

# Historique des prix
price_history  = {s: [] for s in ALL_INSTRUMENTS}
last_signals   = {s: None for s in ALL_INSTRUMENTS}
last_warnings  = {s: None for s in ALL_INSTRUMENTS}
current_prices = {s: None for s in ALL_INSTRUMENTS}

# Graceful shutdown
running = True

def handle_shutdown(signum, frame):
    global running
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    running = False

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def send_telegram_message(message):
    """Envoie un message sur Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.json().get('ok', False)
    except Exception as e:
        print(f"Erreur Telegram: {e}")
        return False

def send_telegram_file(file_path, caption=""):
    """Envoie un fichier sur Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data  = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
            response = requests.post(url, files=files, data=data, timeout=30)
        return response.json().get('ok', False)
    except Exception as e:
        print(f"Erreur envoi fichier Telegram: {e}")
        return False

# ---------------------------------------------------------------------------
# Mini graphique texte (barres Unicode U+2581..U+2588)
# ---------------------------------------------------------------------------

BAR_CHARS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']

def mini_chart(prices, n=10):
    """Retourne un mini graphique texte sur n derniers prix."""
    tail = prices[-n:] if len(prices) >= n else prices[:]
    if len(tail) < 2:
        return ''.join(['▄'] * len(tail)) if tail else ''
    lo, hi = min(tail), max(tail)
    span = hi - lo
    if span == 0:
        return ''.join(['▄'] * len(tail))
    bars = []
    for p in tail:
        idx = int((p - lo) / span * (len(BAR_CHARS) - 1))
        bars.append(BAR_CHARS[idx])
    return ''.join(bars)

# ---------------------------------------------------------------------------
# Indicateurs techniques
# ---------------------------------------------------------------------------

def calculate_indicators(prices):
    """Calcule RSI, MA7, MA14 et volatilite."""
    if len(prices) < 15:
        val = prices[-1] if prices else 0
        return {'rsi': 50, 'ma7': val, 'ma14': val, 'trend': 'UP', 'volatility': 0.0}

    gains, losses = [], []
    for i in range(-14, 0):
        if len(prices) >= abs(i) + 1:
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))

    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    rs  = avg_gain / avg_loss if avg_loss > 0 else 0
    rsi = 100 - (100 / (1 + rs)) if rs > 0 else 50

    ma7  = sum(prices[-7:])  / 7  if len(prices) >= 7  else prices[-1]
    ma14 = sum(prices[-14:]) / 14 if len(prices) >= 14 else prices[-1]

    vol_window = prices[-14:]
    volatility = statistics.stdev(vol_window) if len(vol_window) >= 2 else 0.0

    return {
        'rsi':        rsi,
        'ma7':        ma7,
        'ma14':       ma14,
        'trend':      'UP' if ma7 > ma14 else 'DOWN',
        'volatility': volatility,
    }

def signal_strength(rsi, trend, ma7, ma14):
    """Evalue la force du signal: Faible / Moyen / Fort."""
    ma_diff_pct = abs(ma7 - ma14) / ma14 * 100 if ma14 else 0
    if (rsi < 25 or rsi > 75) and ma_diff_pct > 0.5:
        return 'Fort'
    elif (rsi < 35 or rsi > 65) and ma_diff_pct > 0.1:
        return 'Moyen'
    return 'Faible'

# ---------------------------------------------------------------------------
# Explication du signal
# ---------------------------------------------------------------------------

def build_why(signal_type, rsi, ma7, ma14, trend):
    """Construit la phrase explicative POURQUOI."""
    if signal_type in ('BUY', 'BUY_STRONG'):
        cross = 'MA7 croise au-dessus MA14 = retournement haussier.' if ma7 > ma14 else 'MA7 proche de MA14.'
        return f'Le RSI a {rsi:.0f} = marche survendu (trop de vendeurs). {cross}'
    elif signal_type in ('SELL', 'SELL_STRONG'):
        cross = 'MA7 < MA14 = tendance baissiere confirmee.' if ma7 < ma14 else 'MA7 proche de MA14.'
        return f'Le RSI a {rsi:.0f} = marche surachete. {cross}'
    return ''

# ---------------------------------------------------------------------------
# Prix Deriv (WebSocket)
# ---------------------------------------------------------------------------

def get_deriv_prices():
    """Recupere les prix reels depuis l'API WebSocket Deriv (ticks publics)."""
    global current_prices
    prices_received = {}

    try:
        import ssl
        ws = websocket.create_connection(
            DERIV_WS_URL, timeout=20,
            sslopt={"cert_reqs": ssl.CERT_NONE}
        )
        print("  Connecte a Deriv API")

        for symbol in ALL_INSTRUMENTS:
            ws.send(json.dumps({"ticks": symbol}))

        received = 0
        max_attempts = len(ALL_INSTRUMENTS) * 3
        attempts = 0
        while received < len(ALL_INSTRUMENTS) and attempts < max_attempts:
            attempts += 1
            try:
                response = json.loads(ws.recv())
                if 'tick' in response:
                    sym   = response['tick']['symbol']
                    price = float(response['tick']['quote'])
                    current_prices[sym] = price
                    prices_received[sym] = price
                    received += 1
                elif 'error' in response:
                    print(f"  Erreur {response.get('echo_req', {}).get('ticks','?')}: {response['error']['message']}")
                    received += 1
            except Exception:
                break

        ws.close()

        print(f"  Prix recus: {len(prices_received)}/{len(ALL_INSTRUMENTS)}")
        return len(prices_received) > 0

    except Exception as e:
        print(f"  Erreur connexion Deriv: {e}")
        return False

# ---------------------------------------------------------------------------
# Analyse et generation de signal
# ---------------------------------------------------------------------------

def analyze_instrument(symbol, info, price, indicators, prices):
    """Analyse un instrument et genere un signal enrichi."""
    global last_signals, last_warnings

    rsi   = indicators['rsi']
    trend = indicators['trend']
    ma7   = indicators['ma7']
    ma14  = indicators['ma14']
    vola  = indicators['volatility']
    tp    = info['tp_ticks']
    sl    = info['sl_ticks']
    name  = info['name']
    tf    = info['timeframe']

    chart  = mini_chart(prices, 10)
    force  = signal_strength(rsi, trend, ma7, ma14)
    decimals = 5 if info['type'] == 'forex' and 'JPY' not in name else (3 if 'JPY' in name else 2)
    fmt = f"{{:.{decimals}f}}"

    # --- Alertes preliminaires ---
    warning = None
    if 30 <= rsi < 35 and trend == 'UP':
        warning = ('WATCH_BUY',  '🟡', 'ATTENTION',   'approche zone d\'achat', 'HAUSSIERE')
    elif 65 < rsi <= 70 and trend == 'DOWN':
        warning = ('WATCH_SELL', '🟡', 'ATTENTION',   'approche zone de vente', 'BAISSIERE')
    elif 25 <= rsi < 30 and trend == 'UP':
        warning = ('READY_BUY',  '🟠', 'PREPARE-TOI', 'tres proche achat', 'HAUSSIERE')
    elif 70 < rsi <= 75 and trend == 'DOWN':
        warning = ('READY_SELL', '🟠', 'PREPARE-TOI', 'tres proche vente', 'BAISSIERE')

    if warning and warning[0] != last_warnings.get(symbol):
        last_warnings[symbol] = warning[0]
        wtype, emoji, titre, zone, tendance = warning
        msg = (f"{emoji} {titre} - {name}\n\n"
               f"<b>ALERTE PRELIMINAIRE</b>\n\n"
               f"• RSI: {rsi:.0f} ({zone})\n"
               f"• Tendance: {tendance}\n"
               f"• Prix: {fmt.format(price)}\n"
               f"• Graphique: {chart}\n\n"
               f"<b>PREPARE-TOI!</b> Signal imminent.")
        return {'type': wtype, 'title': f"{emoji} {titre} - {name}", 'message': msg}

    # --- Signaux de trading ---
    sig_type = None
    if rsi < 25 and trend == 'UP':
        sig_type = 'BUY_STRONG'
    elif rsi < 35 and trend == 'UP':
        sig_type = 'BUY'
    elif rsi > 75 and trend == 'DOWN':
        sig_type = 'SELL_STRONG'
    elif rsi > 65 and trend == 'DOWN':
        sig_type = 'SELL'
    else:
        sig_type = 'HOLD'

    if sig_type == 'HOLD':
        last_signals[symbol] = 'HOLD'
        last_warnings[symbol] = None
        return None  # Ne pas envoyer de message ATTENDRE

    # Signal actif
    if sig_type == last_signals.get(symbol):
        return None

    last_signals[symbol]  = sig_type
    last_warnings[symbol] = None

    why = build_why(sig_type, rsi, ma7, ma14, trend)

    is_buy  = sig_type in ('BUY', 'BUY_STRONG')
    is_sell = sig_type in ('SELL', 'SELL_STRONG')

    if is_buy:
        tp_price = price + tp
        sl_price = price - sl
        emoji_sig = '🟢🟢' if sig_type == 'BUY_STRONG' else '🟢'
        action_lbl = 'ACHETER FORT' if sig_type == 'BUY_STRONG' else 'ACHETER'
        action_btn = 'RISE (Hausse)'
        rsi_lbl    = 'SURVENDU' if rsi < 25 else "Zone d'achat"
    else:
        tp_price = price - tp
        sl_price = price + sl
        emoji_sig = '🔴🔴' if sig_type == 'SELL_STRONG' else '🔴'
        action_lbl = 'VENDRE FORT' if sig_type == 'SELL_STRONG' else 'VENDRE'
        action_btn = 'FALL (Baisse)'
        rsi_lbl    = 'SURACHETE' if rsi > 75 else 'Zone de vente'

    msg = (
        f"{emoji_sig} SIGNAL {action_lbl} - {name}\n\n"
        f"<b>POURQUOI?</b> {why}\n\n"
        f"<b>INDICATEURS:</b>\n"
        f"• RSI: {rsi:.0f} ({rsi_lbl})\n"
        f"• MA7: {fmt.format(ma7)} | MA14: {fmt.format(ma14)}\n"
        f"• Tendance: {trend}\n\n"
        f"<b>GRAPHIQUE (10 prix):</b> {chart}\n\n"
        f"<b>STATS:</b>\n"
        f"• Volatilite (std-14): {vola:.5g}\n"
        f"• Force du signal: {force}\n"
        f"• Timeframe recommande: {tf}\n\n"
        f"<b>TRADE:</b>\n"
        f"• Entree:      {fmt.format(price)}\n"
        f"• Take Profit: {fmt.format(tp_price)}\n"
        f"• Stop Loss:   {fmt.format(sl_price)}\n\n"
        f"<b>ACTION:</b> Clique sur {action_btn}!\n\n"
        f"RAPPEL: Trade uniquement en compte demo!"
    )
    return {'type': sig_type, 'title': f"{emoji_sig} SIGNAL {action_lbl} - {name}", 'message': msg}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    print("Deriv Trading Bot - Volatility Indices + Forex")
    print("=" * 55)
    print("Instruments: Vol 10/25/50/75/100 + EUR/USD GBP/USD USD/JPY GBP/JPY EUR/GBP")
    print("Intervalle: 30 secondes")
    print("Appuyez sur Ctrl+C pour arreter\n")

    send_telegram_message(
        "🤖 <b>Deriv Trading Bot demarre!</b>\n\n"
        "<b>MODE: PRIX REELS DERIV API</b>\n\n"
        "<b>Volatility Indices:</b>\n"
        "• Volatility 10 / 25 / 50 / 75 / 100\n\n"
        "<b>Forex:</b>\n"
        "• EUR/USD | GBP/USD | USD/JPY\n"
        "• GBP/JPY | EUR/GBP\n\n"
        "Analyse toutes les 30 secondes\n"
        "Signaux avec explications + mini graphique\n\n"
        "RAPPEL: Trade en demo d'abord!"
    )

    try:
        while running:
            now = datetime.now().strftime('%H:%M:%S')
            print(f"\n{now} - Connexion Deriv API...")

            success = get_deriv_prices()

            if not success:
                print("  Echec connexion - retry dans 30s")
                time.sleep(CHECK_INTERVAL)
                continue

            for symbol, info in ALL_INSTRUMENTS.items():
                price = current_prices.get(symbol)
                if price is None:
                    print(f"  {info['name']}: pas de prix")
                    continue

                price_history[symbol].append(price)
                if len(price_history[symbol]) > 60:
                    price_history[symbol].pop(0)

                indicators   = calculate_indicators(price_history[symbol])
                signal_data  = analyze_instrument(symbol, info, price, indicators, price_history[symbol])

                if signal_data:
                    send_telegram_message(signal_data['message'])
                    print(f"  Signal: {signal_data['title']}")
                else:
                    fmt = '.5f' if info['type'] == 'forex' else '.2f'
                    print(f"  {info['name']}: {price:{fmt}} (RSI: {indicators['rsi']:.0f})")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        print("\nBot arrete")
        send_telegram_message("Bot arrete. A bientot!")

if __name__ == "__main__":
    main()
