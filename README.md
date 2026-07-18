# OKX Signal Daemon

Фоновый Python-демон: берёт свечи OKX по списку монет из конфига, считает MACD / RSI / EMA / дивергенции и шлёт сигналы в Telegram.

В Telegram можно написать `ping` (или `/ping`) — демон ответит `pong` (проверка связи). Остального управления нет.

Важно: в `.env` должны быть **твой** `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` (не примеры). Узнать chat_id: напиши боту любое сообщение, открой `https://api.telegram.org/bot<TOKEN>/getUpdates` и возьми `message.chat.id`.

## Возможности

- Проверка связи: `ping` → `pong` в Telegram
- Сигнал по порогу цены (`above` / `below`) с re-arm после обратного пересечения
- Пересечение MACD вверх / вниз
- RSI перекупленность / перепроданность
- EMA 20/100/200: пересечение fast/slow и пробой slow (swing)
- Regular-дивергенции по RSI и/или MACD
- Combo-сигналы: совпадение нескольких условий в окне свечей
- Несколько инструментов одновременно, у каждого свой таймфрейм
- OKX WebSocket (одна сессия, multi-subscribe) + REST только для прогрева истории

## Установка (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy config.example.yaml config.yaml
copy .env.example .env
```

Тесты:

```bash
pytest
```

В `.env` укажите токен бота и chat_id:

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=123456789
```

В `config.yaml` укажите список `watches`.

## Запуск

Из корня репозитория:

```bash
python -m traderhelper
```

или:

```bash
traderhelper
```

Опции:

```bash
python -m traderhelper --config config.yaml --env .env -v
```

`-v` / `--verbose` включает debug-логи и печать ответов OKX REST/WS и Telegram в консоль.

Остановка: `Ctrl+C`.


## Конфиг

Пример: [`config.example.yaml`](config.example.yaml)

| Поле | Описание |
|------|----------|
| `watches[].inst_id` | Инструмент OKX, например `BTC-USDT` |
| `watches[].timeframe` | Таймфрейм OKX: `1m`, `5m`, `15m`, `30m`, `1H`, `4H`, `1D`, … |
| `watches[].price_alerts` | Пороги цены `above` / `below` |
| `watches[].macd_cross` | Сигналы пересечения MACD |
| `watches[].rsi` | Пороги RSI (`period`, `overbought`, `oversold`) |
| `watches[].ema` | EMA (`fast`/`mid`/`slow`, `cross`) — mid только для контекста в алерте |
| `watches[].divergence` | Дивергенции RSI/MACD (`lookback`, `pivot_left`, `pivot_right`) |
| `watches[].combo` | Правила совпадения условий в окне свечей |

Опционально для MACD: `macd_fast`, `macd_slow`, `macd_signal` (по умолчанию 12/26/9).

### EMA swing

При `ema.cross: true` на закрытой свече:

- **bullish** — `EMA(fast)` пересекает `EMA(slow)` снизу вверх
- **bearish** — обратное пересечение, либо close пробивает `EMA(slow)` против текущей структуры

### Combo

Отдельный тип алерта. Одиночные сигналы продолжают слаться, если включены в watch.

Каждое условие из `require` должно **активироваться внутри окна** `window` свечей и оставаться **валидным** на текущей свече:

| `kind` | `direction` | Активация | Валидность |
|--------|-------------|-----------|------------|
| `rsi` | `bullish` / `bearish` | oversold / overbought | не вышел из зоны |
| `ema_cross` | `bullish` / `bearish` | пересечение fast/slow | fast остаётся выше/ниже slow |
| `macd_cross` | `bullish` / `bearish` | пересечение MACD/signal | знак diff сохраняется |
| `divergence` | `bullish` / `bearish` | confirmed div | «незакрытый»: close не пробил newer pivot |

Пример:

```yaml
combo:
  - name: bull confluence
    window: 10
    require:
      - kind: divergence
        direction: bullish
      - kind: ema_cross
        direction: bullish
      - kind: rsi
        direction: bullish
```

## Как получить chat_id

1. Создайте бота у [@BotFather](https://t.me/BotFather), скопируйте token в `.env`
2. Напишите боту любое сообщение
3. Откройте `https://api.telegram.org/bot<TOKEN>/getUpdates` и возьмите `chat.id`
4. Запишите его в `.env` как `TELEGRAM_CHAT_ID`

## Поведение

1. При старте REST прогревает ~300 закрытых свечей на каждый watch
2. Дальше работает WebSocket `wss://ws.okx.com:8443/ws/v5/business`
3. MACD / RSI / EMA / дивергенции / combo считаются только на закрытой свече (`confirm=1`)
4. Price-алерты реагируют на обновления last price, в том числе незакрытой свечи
5. После reconnect — REST gap-fill с пагинацией, догоняющая отправка сигналов по закрытым свечам, затем продолжение стрима

API-ключ OKX не нужен (публичные market-данные).
