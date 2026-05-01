import requests
import time
import json
import signal
import sys
import os
import websocket
import threading
from datetime import datetime

# Configuration Telegram
TELEGRAM_TOKEN = "8149409815:AAGgC9IWsyQh4m5TlAuGDTJtBcgLkTPr3ao"
TELEGRAM_CHAT_ID = "1028710661"

# Configuration Deriv API
DERIV_API_TOKEN = "lBTikfXnyMUDW8E"
DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Configuration Deriv Volatility Indices
VOLATILITY_INDICES = {
    'R_10': {'name': 'Volatility 10 Index', 'symbol': 'R_10'},
    'R_25': {'name': 'Volatility 25 Index', 'symbol': 'R_25'},
    'R_50': {'name': 'Volatility 50 Index', 'symbol': 'R_50'},
    'R_75': {'name': 'Volatility 75 Index', 'symbol': 'R_75'},
    'R_100': {'name': 'Volatility 100 Index', 'symbol': 'R_100'},
}

CHECK_INTERVAL = 30

# Historique des prix
price_history = {symbol: [] for symbol in VOLATILITY_INDICES}
last_signals = {symbol: None for symbol in VOLATILITY_INDICES}
last_warnings = {symbol: None for symbol in VOLATILITY_INDICES}
current_prices = {symbol: None for symbol in VOLATILITY_INDICES}

# Graceful shutdown handling
running = True

def handle_shutdown(signum, frame):
    global running
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    running = False

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

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

def get_deriv_prices():
    """Recupere les prix reels depuis l'API WebSocket Deriv (pas besoin d'auth)"""
    global current_prices
    prices_received = {}
    
    try:
        import ssl
        ws = websocket.create_connection(DERIV_WS_URL, timeout=15, 
                                          sslopt={"cert_reqs": ssl.CERT_NONE})
        
        print("  Connecte a Deriv API")
        
        # Demander le prix de chaque indice (pas besoin d'auth pour les ticks)
        for symbol in VOLATILITY_INDICES:
            ws.send(json.dumps({"ticks": symbol}))
        
        # Recevoir toutes les reponses et mapper par symbole
        received = 0
        while received < len(VOLATILITY_INDICES):
            response = json.loads(ws.recv())
            if 'tick' in response:
                sym = response['tick']['symbol']
                price = float(response['tick']['quote'])
                current_prices[sym] = price
                prices_received[sym] = price
                received += 1
            elif 'error' in response:
                print(f"  Erreur: {response['error']['message']}")
                received += 1
        
        ws.close()
        
        if prices_received:
            print(f"  Prix recus: {len(prices_received)}/{len(VOLATILITY_INDICES)}")
            return True
        else:
            print("  Aucun prix recu")
            return False
            
    except Exception as e:
        print(f"  Erreur connexion Deriv: {e}")
        return False

def calculate_indicators(prices):
    """Calcule les indicateurs techniques"""
    if len(prices) < 15:
        ma7 = prices[-1] if len(prices) >= 7 else (prices[-1] if prices else 0)
        ma14 = prices[-1] if prices else 0
        return {'rsi': 50, 'ma7': ma7, 'ma14': ma14, 'trend': 'UP'}
    
    gains = []
    losses = []
    for i in range(-14, 0):
        if len(prices) >= abs(i) + 1:
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
    
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    rs = avg_gain / avg_loss if avg_loss > 0 else 0
    rsi = 100 - (100 / (1 + rs)) if rs > 0 else 50
    
    ma7 = sum(prices[-7:]) / 7 if len(prices) >= 7 else (prices[-1] if prices else 0)
    ma14 = sum(prices[-14:]) / 14 if len(prices) >= 14 else (prices[-1] if prices else 0)
    
    return {
        'rsi': rsi,
        'ma7': ma7,
        'ma14': ma14,
        'trend': 'UP' if ma7 > ma14 else 'DOWN'
    }

def analyze_volatility_index(symbol, name, price, indicators):
    """Analyse un Volatility Index et genere un signal avec alertes preliminaires"""
    global last_signals, last_warnings
    
    rsi = indicators['rsi']
    trend = indicators['trend']
    ma7 = indicators['ma7']
    ma14 = indicators['ma14']
    
    take_profit_ticks = 15
    stop_loss_ticks = 10
    
    warning = None
    
    if 30 <= rsi < 35 and trend == 'UP':
        warning = {
            'type': 'WATCH_BUY',
            'emoji': '🟡',
            'title': f'👀 ATTENTION - {name}',
            'message': f'''<b>ALERTE PRELIMINAIRE</b>

• RSI: {rsi:.0f} (approche zone d'achat)
• Tendance: HAUSSIERE
• Prix: {price:.2f}

<b>⚠️ PREPARE-TOI!</b>
Le signal d'achat peut arriver bientot.
Ouvre Deriv et sois pret!'''
        }
    elif 65 < rsi <= 70 and trend == 'DOWN':
        warning = {
            'type': 'WATCH_SELL',
            'emoji': '🟡',
            'title': f'👀 ATTENTION - {name}',
            'message': f'''<b>ALERTE PRELIMINAIRE</b>

• RSI: {rsi:.0f} (approche zone de vente)
• Tendance: BAISSIERE
• Prix: {price:.2f}

<b>⚠️ PREPARE-TOI!</b>
Le signal de vente peut arriver bientot.
Ouvre Deriv et sois pret!'''
        }
    
    if 25 <= rsi < 30 and trend == 'UP':
        warning = {
            'type': 'READY_BUY',
            'emoji': '🟠',
            'title': f'⏰ PREPARE-TOI - {name}',
            'message': f'''<b>ALERTE AVANCEE</b>

• RSI: {rsi:.0f} (tres proche achat)
• Tendance: HAUSSIERE
• Prix: {price:.2f}

<b>🚨 SOIS PRET!</b>
Signal d'achat imminent!
Positionne-toi sur Deriv!'''
        }
    elif 70 < rsi <= 75 and trend == 'DOWN':
        warning = {
            'type': 'READY_SELL',
            'emoji': '🟠',
            'title': f'⏰ PREPARE-TOI - {name}',
            'message': f'''<b>ALERTE AVANCEE</b>

• RSI: {rsi:.0f} (tres proche vente)
• Tendance: BAISSIERE
• Prix: {price:.2f}

<b>🚨 SOIS PRET!</b>
Signal de vente imminent!
Positionne-toi sur Deriv!'''
        }
    
    if warning and warning['type'] != last_warnings.get(symbol):
        last_warnings[symbol] = warning['type']
        return warning
    
    signal = None
    
    if rsi < 25 and trend == 'UP':
        signal = {
            'type': 'BUY_STRONG',
            'emoji': '🟢🟢',
            'title': f'🚨 SIGNAL ACHETER FORT - {name}',
            'message': f'''<b>🎯 SIGNAL CONFIRME!</b>

• RSI: {rsi:.0f} (SURVENDU)
• Tendance: HAUSSIERE
• Prix: {price:.2f}

<b>💰 TRADE MAINTENANT!</b>

<b>PRIX D'ENTREE:</b> {price:.2f}
<b>TAKE PROFIT:</b> {price + take_profit_ticks:.2f}
<b>STOP LOSS:</b> {price - stop_loss_ticks:.2f}

<b>👉 ACTION:</b> Clique sur RISE (Hausse) maintenant!'''
        }
    elif rsi < 35 and trend == 'UP':
        signal = {
            'type': 'BUY',
            'emoji': '🟢',
            'title': f'✅ SIGNAL ACHETER - {name}',
            'message': f'''<b>🎯 SIGNAL CONFIRME!</b>

• RSI: {rsi:.0f} (Zone d'achat)
• Tendance: HAUSSIERE
• Prix: {price:.2f}

<b>💰 TRADE MAINTENANT!</b>

<b>PRIX D'ENTREE:</b> {price:.2f}
<b>TAKE PROFIT:</b> {price + 10:.2f}
<b>STOP LOSS:</b> {price - 7:.2f}

<b>👉 ACTION:</b> Clique sur RISE (Hausse)!'''
        }
    elif rsi > 75 and trend == 'DOWN':
        signal = {
            'type': 'SELL_STRONG',
            'emoji': '🔴🔴',
            'title': f'🚨 SIGNAL VENDRE FORT - {name}',
            'message': f'''<b>🎯 SIGNAL CONFIRME!</b>

• RSI: {rsi:.0f} (SURACHETE)
• Tendance: BAISSIERE
• Prix: {price:.2f}

<b>💰 TRADE MAINTENANT!</b>

<b>PRIX D'ENTREE:</b> {price:.2f}
<b>TAKE PROFIT:</b> {price - take_profit_ticks:.2f}
<b>STOP LOSS:</b> {price + stop_loss_ticks:.2f}

<b>👉 ACTION:</b> Clique sur FALL (Baisse) maintenant!'''
        }
    elif rsi > 65 and trend == 'DOWN':
        signal = {
            'type': 'SELL',
            'emoji': '🔴',
            'title': f'✅ SIGNAL VENDRE - {name}',
            'message': f'''<b>🎯 SIGNAL CONFIRME!</b>

• RSI: {rsi:.0f} (Zone de vente)
• Tendance: BAISSIERE
• Prix: {price:.2f}

<b>💰 TRADE MAINTENANT!</b>

<b>PRIX D'ENTREE:</b> {price:.2f}
<b>TAKE PROFIT:</b> {price - 10:.2f}
<b>STOP LOSS:</b> {price + 7:.2f}

<b>👉 ACTION:</b> Clique sur FALL (Baisse)!'''
        }
    else:
        signal = {
            'type': 'HOLD',
            'emoji': '🟡',
            'title': f'⏳ ATTENDRE - {name}',
            'message': f'''<b>ANALYSE:</b>
• RSI: {rsi:.0f} (Neutre)
• Tendance: {trend}
• Prix: {price:.2f}

<b>SIGNAL: ATTENDRE</b>

Pas de signal clair, reste en dehors du marche.'''
        }
    
    if signal['type'] != 'HOLD':
        last_warnings[symbol] = None
        if signal['type'] != last_signals.get(symbol):
            last_signals[symbol] = signal['type']
            return signal
    elif signal['type'] == 'HOLD' and last_signals.get(symbol) != 'HOLD':
        last_signals[symbol] = 'HOLD'
        last_warnings[symbol] = None
        return signal
    
    return None

def main():
    """Boucle principale"""
    print("Deriv Volatility Indices Trading Bot")
    print("=" * 50)
    print("MODE: PRIX REELS DERIV API")
    print("Analyse: Vol 10, 25, 50, 75, 100")
    print("Intervalle: 30 secondes")
    print("Appuyez sur Ctrl+C pour arreter\n")
    
    send_telegram_message("🤖 Deriv Volatility Bot demarre!\n\n<b>MODE: PRIX REELS</b>\n\nSurveillance:\n• Volatility 10\n• Volatility 25\n• Volatility 50\n• Volatility 75\n• Volatility 100\n\nAnalyse toutes les 30 secondes\nConnexion API Deriv active!\n\nRAPPEL: Trade en demo d'abord!")
    
    try:
        while running:
            now = datetime.now().strftime('%H:%M:%S')
            print(f"\n{now} - Connexion Deriv API...")
            
            # Recuperer les vrais prix
            success = get_deriv_prices()
            
            if not success:
                print("  Echec connexion - retry dans 30s")
                time.sleep(CHECK_INTERVAL)
                continue
            
            for symbol, info in VOLATILITY_INDICES.items():
                price = current_prices.get(symbol)
                if price is None:
                    continue
                
                price_history[symbol].append(price)
                if len(price_history[symbol]) > 60:
                    price_history[symbol].pop(0)
                
                indicators = calculate_indicators(price_history[symbol])
                signal_data = analyze_volatility_index(symbol, info['name'], price, indicators)
                
                if signal_data:
                    message = f"""{signal_data['title']}

{signal_data['message']}

{now}

RAPPEL: Trade uniquement en compte demo!"""
                    send_telegram_message(message)
                    print(f"  Signal envoye: {signal_data['title']}")
                else:
                    print(f"  {info['name']}: {price:.2f} (RSI: {indicators['rsi']:.0f})")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        pass
    finally:
        print("\nBot arrete")
        send_telegram_message("Bot arrete\nA bientot!")

if __name__ == "__main__":
    main()
