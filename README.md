# 💹 Bot de Arbitraje Multi-Exchange - Crypto Trading Bot

**Bot automatizado de arbitraje triangular que opera simultáneamente en múltiples exchanges de criptomonedas, detectando diferencias de precio y ejecutando operaciones para capturar ganancias.**

![Versión](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![CCXT](https://img.shields.io/badge/CCXT-4.x-orange)
![Licencia](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ Características

- 🔄 **Arbitraje multi-exchange** entre Binance, Kraken, KuCoin y BingX
- 📊 **Cálculo de ganancias netas** considerando comisiones de compra/venta
- 💰 **Tamaño dinámico de operaciones** basado en saldo disponible y liquidez
- 📱 **Notificaciones por Telegram** de operaciones ejecutadas
- 🔁 **Sistema de reintentos** con backoff exponencial para fallos de red
- ⚡ **Bucle continuo** con intervalo configurable
- 🛡️ **Manejo robusto de errores** y logging detallado
- 🌐 **Soporte nativo para Windows** con política de eventos asíncronos

---

## 🛡️ Advertencia Legal

**Este bot es una herramienta de trading automatizado. El trading de criptomonedas conlleva riesgos significativos.**

- ⚠️ **Riesgo de pérdida** - Puedes perder parte o la totalidad de tu capital
- 📜 **Términos de servicio** - Verifica que los exchanges permitan bots de arbitraje
- 🔧 **Responsabilidad** - El autor no se hace responsable de pérdidas financieras
- 🧪 **Prueba primero** - Recomendado usar en modo simulación o con montos pequeños

---

## 📋 Requisitos

- Python 3.8 o superior
- Cuentas en los exchanges (Binance, Kraken, KuCoin, BingX)
- API Keys con permisos de lectura y trading
- Telegram Bot Token (opcional, para notificaciones)

### Instalación de dependencias

```bash
pip install ccxt asyncio aiohttp colorama backoff requests
