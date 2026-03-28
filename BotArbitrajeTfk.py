import sys
import socket
import asyncio
import ccxt.async_support as ccxt
from colorama import init, Fore
import aiohttp
import logging
import requests
import os
import time
import backoff

# Configurar el bucle de eventos correcto en Windows para evitar problemas con aiodns y asyncio
if sys.platform.startswith('win') and sys.version_info >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

init(autoreset=True)

# Configuración para Telegram
TELEGRAM_API_TOKEN = os.getenv('')
TELEGRAM_CHAT_ID = os.getenv('')

# Configuración de logging
logging.basicConfig(filename='arbitrage_bot.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

# Configuración de exchanges con claves API almacenadas en variables de entorno
api_keys = {
    'binance': {
        'apiKey': os.getenv(''),
        'secret': os.getenv('')
    },
    'kraken': {
        'apiKey': os.getenv(''),
        'secret': os.getenv('')
    },
    'kucoin': {
        'apiKey': os.getenv(''),
        'secret': os.getenv('')
    },
    'bingx': {
        'apiKey': os.getenv(''),
        'secret': os.getenv('')
    }
}

# Crear un conector personalizado sin `aiodns`
def create_connector():
    return aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)

# Estrategia de backoff exponencial para reintentos
@backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=5)
async def fetch_with_timeout(session, url, params=None):
    async with session.get(url, params=params, timeout=10) as response:
        return await response.json()

# Inicializar exchanges
async def initialize_exchanges(session):
    exchanges = {}
    for exchange_id, creds in api_keys.items():
        try:
            exchange_class = getattr(ccxt, exchange_id)
            print(Fore.CYAN + f"Conectando al exchange: {exchange_id}...")
            exchange = exchange_class({
                'apiKey': creds['apiKey'],
                'secret': creds['secret'],
                'enableRateLimit': True,
                'session': session,
                'options': {'adjustForTimeDifference': True}
            })
            await exchange.load_markets()
            exchanges[exchange_id] = exchange
        except Exception as e:
            print(Fore.RED + f"Error al conectar con {exchange_id}: {e}")
            logging.error(f"Error al conectar con {exchange_id}: {e}")
    return exchanges

# Filtrar pares líquidos
async def get_liquid_symbols(exchanges):
    prioritized_symbols = ['BTC/USDT', 'ETH/USDT', 'ADA/USDT', 'SOL/USDT']
    markets = {}
    for exchange_id, exchange in exchanges.items():
        markets[exchange_id] = set(exchange.symbols)

    common_symbols = set.intersection(*markets.values()) | set(prioritized_symbols)
    return list(common_symbols)[:200]

# Enviar notificaciones por Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        logging.error(f"Error al enviar mensaje a Telegram: {e}")

# Obtener saldo disponible en un exchange
async def get_available_balance(exchange, currency):
    try:
        balance = await exchange.fetch_balance()
        available = balance['free'].get(currency, 0)
        logging.info(f"Saldo disponible en {exchange.id} para {currency}: {available}")
        return available
    except Exception as e:
        print(Fore.RED + f"Error al obtener el saldo en {exchange.id}: {e}")
        logging.error(f"Error al obtener el saldo en {exchange.id}: {e}")
        return 0

# Obtener precios bid/ask de un par en un exchange
async def fetch_prices(symbol, exchange):
    try:
        ticker = await exchange.fetch_ticker(symbol)
        bid = ticker['bid']
        ask = ticker['ask']
        print(Fore.CYAN + f"Precio en {exchange.id} para {symbol} -> Bid: {bid}, Ask: {ask}")
        logging.info(f"Precios obtenidos en {exchange.id} para {symbol}: Bid = {bid}, Ask = {ask}")
        return bid, ask
    except Exception as e:
        print(Fore.RED + f"Error al obtener precios para {symbol} en {exchange.id}: {e}")
        logging.error(f"Error al obtener precios para {symbol} en {exchange.id}: {e}")
        return None, None

# Calcular el beneficio neto después de comisiones
def calculate_profit_after_fees(buy_price, sell_price, buy_fee, sell_fee, amount):
    total_buy_cost = buy_price * amount + buy_fee * buy_price * amount
    total_sell_revenue = sell_price * amount - sell_fee * sell_price * amount
    net_profit = total_sell_revenue - total_buy_cost
    print(Fore.GREEN + f"Cálculo de arbitraje: compra a {buy_price}, vende a {sell_price}, neto después de comisiones: {net_profit}")
    logging.info(f"Cálculo de arbitraje: compra a {buy_price}, vende a {sell_price}, neto después de comisiones: {net_profit}")
    return net_profit

# Ajustar el tamaño de la operación basado en el saldo disponible y la liquidez
def calculate_dynamic_amount(buy_balance, buy_price, sell_balance, commission_factor=0.9):
    max_buy_amount = (buy_balance / buy_price) * commission_factor
    max_sell_amount = sell_balance * commission_factor
    amount = min(max_buy_amount, max_sell_amount)
    min_trade_size = 10 / buy_price
    if amount < min_trade_size:
        logging.info(f"El monto calculado {amount} es menor al mínimo permitido de {min_trade_size}. Operación no se ejecutará.")
        print(Fore.YELLOW + f"El monto calculado {amount} es menor al mínimo permitido de {min_trade_size}.")
        return 0
    logging.info(f"Tamaño dinámico de la operación calculado: {amount}")
    return amount

# Ejecutar órdenes de compra y venta en exchanges
async def execute_trades(buy_exchange, sell_exchange, symbol, amount, buy_price, sell_price):
    try:
        logging.info(f"Ejecutando compra en {buy_exchange.id} por {amount} de {symbol} a {buy_price}")
        print(Fore.BLUE + f"Ejecutando compra en {buy_exchange.id} por {amount} de {symbol} a {buy_price}")
        buy_order = await buy_exchange.create_order(
            symbol=symbol,
            type='limit',
            side='buy',
            amount=amount,
            price=buy_price
        )
        print(Fore.GREEN + f"Orden de compra ejecutada en {buy_exchange.id}: {buy_order}")

        logging.info(f"Ejecutando venta en {sell_exchange.id} por {amount} de {symbol} a {sell_price}")
        print(Fore.BLUE + f"Ejecutando venta en {sell_exchange.id} por {amount} de {symbol} a {sell_price}")
        sell_order = await sell_exchange.create_order(
            symbol=symbol,
            type='limit',
            side='sell',
            amount=amount,
            price=sell_price
        )
        print(Fore.GREEN + f"Orden de venta ejecutada en {sell_exchange.id}: {sell_order}")

        return True
    except Exception as e:
        print(Fore.RED + f"Error al ejecutar operaciones: {e}")
        logging.error(f"Error al ejecutar operaciones: {e}")
        return False

# Buscar oportunidades de arbitraje para un símbolo
async def find_arbitrage_for_symbol(symbol, exchanges):
    prices = {}
    tasks = [fetch_prices(symbol, exchange) for exchange in exchanges.values()]
    results = await asyncio.gather(*tasks)

    for exchange, result in zip(exchanges.keys(), results):
        bid, ask = result
        if bid is not None and ask is not None:
            prices[exchange] = {'bid': bid, 'ask': ask}

    if len(prices) < 2:
        logging.info(f"No se encontraron suficientes precios para {symbol}")
        print(Fore.MAGENTA + f"No se encontraron suficientes precios para {symbol}")
        return None

    best_ask_exchange = min(prices.items(), key=lambda x: x[1]['ask'])
    best_bid_exchange = max(prices.items(), key=lambda x: x[1]['bid'])

    buy_exchange = exchanges[best_ask_exchange[0]]
    sell_exchange = exchanges[best_bid_exchange[0]]

    best_ask = best_ask_exchange[1]['ask']
    best_bid = best_bid_exchange[1]['bid']

    if best_bid > best_ask:
        buy_fee = 0.001  # Comisiones estimadas para compra
        sell_fee = 0.001  # Comisiones estimadas para venta
        net_profit = calculate_profit_after_fees(best_ask, best_bid, buy_fee, sell_fee, 0.001)

        THRESHOLD_PROFIT = 0.3
        if net_profit > THRESHOLD_PROFIT:
            logging.info(f"Oportunidad rentable para {symbol}: Comprar en {buy_exchange.id} a {best_ask}, vender en {sell_exchange.id} a {best_bid}")
            print(Fore.CYAN + f"Oportunidad rentable para {symbol}: Comprar en {buy_exchange.id} a {best_ask}, vender en {sell_exchange.id} a {best_bid}")
            return {
                'symbol': symbol,
                'buy_exchange': buy_exchange,
                'sell_exchange': sell_exchange,
                'best_ask': best_ask,
                'best_bid': best_bid,
                'net_profit': net_profit
            }

    logging.info(f"No se encontró una oportunidad rentable para {symbol}")
    print(Fore.MAGENTA + f"No se encontró una oportunidad rentable para {symbol}")
    return None

# Ejecutar oportunidades de arbitraje
async def execute_opportunities(opportunities):
    tasks = []
    for opportunity in opportunities:
        symbol = opportunity['symbol']
        buy_exchange = opportunity['buy_exchange']
        sell_exchange = opportunity['sell_exchange']
        best_ask = opportunity['best_ask']
        best_bid = opportunity['best_bid']

        buy_balance = await get_available_balance(buy_exchange, 'USDT')
        sell_balance = await get_available_balance(sell_exchange, symbol.split('/')[0])

        amount = calculate_dynamic_amount(buy_balance, best_ask, sell_balance)

        if amount > 0 and buy_balance >= best_ask * amount and sell_balance >= amount:
            tasks.append(execute_trades(
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                symbol=symbol,
                amount=amount,
                buy_price=best_ask,
                sell_price=best_bid
            ))
        else:
            print(Fore.RED + f"Saldo insuficiente o monto demasiado bajo para operar en {symbol}\n")
            logging.info(f"Saldo insuficiente o monto demasiado bajo para operar en {symbol}")

    await asyncio.gather(*tasks)

# Buscar oportunidades de arbitraje
async def find_arbitrage_opportunities(exchanges, symbols):
    tasks = [find_arbitrage_for_symbol(symbol, exchanges) for symbol in symbols]
    opportunities = await asyncio.gather(*tasks)
    return [opportunity for opportunity in opportunities if opportunity]

# Función principal
async def main():
    session = aiohttp.ClientSession(connector=create_connector())
    exchanges = await initialize_exchanges(session)

    try:
        common_symbols = await get_liquid_symbols(exchanges)
        print(Fore.YELLOW + f"Analizando {len(common_symbols)} pares en busca de oportunidades...")

        while True:
            opportunities = await find_arbitrage_opportunities(exchanges, common_symbols)

            if opportunities:
                await execute_opportunities(opportunities)
            else:
                print(Fore.WHITE + "No se encontraron oportunidades de arbitraje en este ciclo.\n")

            await asyncio.sleep(30)

    except KeyboardInterrupt:
        print(Fore.RED + "\nBot detenido manualmente.")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
