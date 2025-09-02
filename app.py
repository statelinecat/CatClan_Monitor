import os
import logging
import traceback
from flask import Flask, jsonify, request
from dash import Dash, dcc, html, callback_context, Input, Output, State
from dash import dash_table  # на случай, если понадобится
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta

# Ваши модули
from utils.binance_api import BinanceAPI
from utils.data_storage import BalanceStorage
from config import Config

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Проверка конфигурации
Config.validate_config()

# Инициализация Flask
server = Flask(__name__)
server.secret_key = Config.SECRET_KEY

# Инициализация API и хранилища
binance_api = BinanceAPI()
balance_storage = BalanceStorage()

# Инициализация Dash с Bootstrap (тёмная тема)
app = Dash(
    __name__,
    server=server,
    url_base_pathname='/',
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True
)

# =============
# Глобальные стили
# =============
style_h2 = {
    'color': '#f5f5dc',
    'marginBottom': '8px',
    'fontSize': '16px',
    'fontWeight': 'bold'
}

style_value = {
    'fontSize': '20px',
    'fontWeight': 'bold'
}

# =============
# Макет приложения
# =============
app.layout = html.Div([
    # Метатеги для мобильных
    dcc.Location(id='url'),
    html.Meta(name='viewport', content='width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'),

    # Основной контейнер
    dbc.Container([
        # Заголовок
        dbc.Row([
            dbc.Col(
                html.H1("📊 Binance Futures", className="text-center my-3", style={
                    'color': '#f5f5dc',
                    'fontSize': '24px',
                    'fontWeight': 'bold'
                }),
                width=12
            )
        ]),

        # График баланса
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='balance-graph', style={'height': '300px'}),
                # Кнопки периода
                html.Div([
                    dbc.Button("30d", id='btn-30', color="secondary", size="sm", className="mx-1"),
                    dbc.Button("90d", id='btn-90', color="secondary", size="sm", className="mx-1"),
                    dbc.Button("All", id='btn-all', color="secondary", size="sm", className="mx-1"),
                ], className="text-center my-2")
            ])
        ], className="mb-3"),

        # Интервал автообновления
        dcc.Interval(id='interval-component', interval=5 * 60 * 1000, n_intervals=0),

        # Блок статистики: Total, PnL, Size
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Balance", className="card-subtitle mb-1", style=style_h2),
                        html.P(id='futures-total', style={**style_value, 'color': '#f5f5dc'}),
                        html.Small(id='last-update', className="text-muted")
                    ])
                ], color="dark", outline=True, style={'height': '100%'})
            ], width=12, sm=6, md=4, className="mb-2"),

            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Unrealized PnL", className="card-subtitle mb-1", style=style_h2),
                        html.P(id='total-pnl', style={'fontSize': '14px'})
                    ])
                ], color="dark", outline=True, style={'height': '100%'})
            ], width=12, sm=6, md=4, className="mb-2"),

            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Size", className="card-subtitle mb-1", style=style_h2),
                        html.P(id='total-size', style={'fontSize': '16px', 'fontWeight': 'bold'}),
                        html.Small(id='total-size-percent')
                    ])
                ], color="dark", outline=True, style={'height': '100%'})
            ], width=12, sm=6, md=4, className="mb-2"),
        ], className="mb-3"),

        # Заголовок с количеством позиций
        dbc.Row([
            dbc.Col([
                html.H5([
                    html.Span("🟢", style={'marginRight': '6px'}),
                    "Open Positions: ",
                    html.Strong(id='positions-count')
                ], style={'color': '#f5f5dc', 'textAlign': 'center'})
            ], width=12, className="my-3")
        ]),

        # Список позиций (в виде карточек)
        dbc.Row([
            dbc.Col([
                html.Div(id='positions-container', style={'marginTop': '10px'})
            ], width=12)
        ], className="mb-3")

    ], fluid=True, style={'padding': '10px'}),

    # Фон
], style={'backgroundColor': '#121212', 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'})


# =============
# Функция получения данных фьючерсов
# =============
def get_futures_data():
    try:
        logger.info("Fetching futures data from Binance API...")

        # Баланс
        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(
            float(b['balance']) for b in futures_balances
            if isinstance(b, dict) and 'balance' in b
        ) if futures_balances else 0.0

        # Позиции
        raw_positions = binance_api.get_futures_positions()
        positions = raw_positions.get('positions', []) if isinstance(raw_positions, dict) else raw_positions or []

        # Преобразуем в DataFrame
        df_positions = pd.DataFrame(positions)
        if not df_positions.empty:
            df_positions['size_usdt'] = df_positions['usdtValue'].round(2)
            df_positions['leverage_x'] = df_positions['leverage'].astype(str) + 'x'
            df_positions['contracts_abs'] = df_positions['positionAmt'].abs()
            df_positions['entryPrice'] = df_positions['entryPrice'].round(6)
            df_positions['markPrice'] = df_positions['markPrice'].round(6)
            df_positions['unRealizedProfit'] = df_positions['unRealizedProfit'].round(2)
            df_positions['roe'] = df_positions['roe'].round(2)

            # Оставляем только нужные колонки
            df_positions = df_positions[[
                'symbol', 'positionSide', 'size_usdt', 'leverage_x', 'contracts_abs',
                'entryPrice', 'markPrice', 'unRealizedProfit', 'roe'
            ]]

            positions_data = df_positions.to_dict('records')
        else:
            positions_data = []

        # Сохраняем баланс
        balance_storage.save_balance(0, futures_total)

        return {
            'futures_total': round(futures_total, 2),
            'positions': positions_data,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        logger.error(f"Error in get_futures_data: {e}")
        logger.error(traceback.format_exc())
        return {'error': str(e)}


# =============
# Callback: Обновление графика
# =============
@app.callback(
    Output('balance-graph', 'figure'),
    [Input('btn-30', 'n_clicks'),
     Input('btn-90', 'n_clicks'),
     Input('btn-all', 'n_clicks'),
     Input('interval-component', 'n_intervals')]
)
def update_graph(btn30, btn90, btn_all, n_intervals):
    ctx = callback_context
    button_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else 'btn-30'

    period_map = {'btn-30': 30, 'btn-90': 90, 'btn-all': None}
    period_days = period_map.get(button_id, 30)

    try:
        df = balance_storage.get_balance_history(period_days or 9999)
        if df.empty:
            fig = go.Figure()
            fig.update_layout(title="No data", template="plotly_dark", height=300)
            return fig

        df['date'] = pd.to_datetime(df['date'])
        start_date = datetime(2025, 8, 1)
        df = df[df['date'] >= start_date]
        df = df.sort_values('date')

        df['date_only'] = df['date'].dt.date
        df_filtered = df[df['futures_balance'] > 0] if not df[df['futures_balance'] > 0].empty else df
        df_daily = df_filtered.groupby('date_only').agg(
            min_balance=('futures_balance', 'min'),
            max_balance=('futures_balance', 'max'),
            last_balance=('futures_balance', 'last')
        ).reset_index()
        df_daily['date'] = pd.to_datetime(df_daily['date_only'])
        df_daily = df_daily.sort_values('date')

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_daily['date'], y=df_daily['min_balance'], mode='lines', name='Min',
                                 line=dict(dash='dot', color='#ea3943'), showlegend=False))
        fig.add_trace(go.Scatter(x=df_daily['date'], y=df_daily['max_balance'], mode='lines', name='Max',
                                 line=dict(dash='dot', color='#16c784'), showlegend=False))
        fig.add_trace(go.Scatter(x=df_daily['date'], y=df_daily['last_balance'], mode='lines+markers', name='Close',
                                 line=dict(color='#f6465d'), marker=dict(size=4)))

        fig.update_layout(
            title=f"Balance — {period_days}d" if period_days else "All Time",
            xaxis_title="Date",
            yaxis_title="USDT",
            template="plotly_dark",
            height=300,
            margin=dict(l=40, r=40, t=50, b=40),
            hovermode='x unified',
            font=dict(size=10)
        )
        return fig

    except Exception as e:
        logger.error(f"Graph update error: {e}")
        fig = go.Figure()
        fig.update_layout(title="Error", template="plotly_dark", height=300)
        return fig


# =============
# Callback: Обновление всех данных
# =============
@app.callback(
    [Output('futures-total', 'children'),
     Output('last-update', 'children'),
     Output('total-pnl', 'children'),
     Output('total-size', 'children'),
     Output('total-size-percent', 'children'),
     Output('positions-container', 'children'),
     Output('positions-count', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_data(n_intervals):
    try:
        data = get_futures_data()
        if 'error' in data:
            logger.error(f"Data fetch error: {data['error']}")
            return "–", "", "Error", "–", "", html.P("Failed to load data", style={'textAlign': 'center'}), "–"

        futures_total = data['futures_total']
        positions = data['positions']
        timestamp = data['timestamp']

        # PnL
        total_pnl = sum(float(p['unRealizedProfit']) for p in positions) if positions else 0.0
        pnl_percentage = (total_pnl / futures_total * 100) if futures_total > 0 else 0
        pnl_color = '#16c784' if total_pnl >= 0 else '#ea3943'

        # Total Size
        total_size = sum(float(p['size_usdt']) for p in positions) if positions else 0.0
        size_percent = (total_size / (20 * futures_total) * 100) if futures_total > 0 else 0
        size_color = '#ea3943' if total_size > (10 * futures_total) else '#16c784'

        # Карточки позиций
        position_cards = [
            dbc.Card([
                dbc.Row([
                    dbc.Col([
                        html.Div(p['symbol'], style={'fontWeight': 'bold', 'fontSize': '14px'}),
                        html.Small(p['positionSide'], className="text-muted", style={'fontSize': '12px'})
                    ], width=7),
                    dbc.Col([
                        html.Div(f"{p['size_usdt']} USDT", style={'fontSize': '14px', 'fontWeight': 'bold'}),
                        html.Div(f"{p['roe']}% ROE", style={
                            'color': '#16c784' if float(p['roe']) >= 0 else '#ea3943',
                            'fontSize': '12px'
                        })
                    ], width=5, className="text-end")
                ], className="g-1 align-items-center"),
                dbc.Row([
                    dbc.Col([
                        html.Small(f"Entry: {p['entryPrice']}", className="text-muted"),
                        html.Br(),
                        html.Small(f"Mark: {p['markPrice']}", className="text-muted"),
                    ], width=7),
                    dbc.Col([
                        html.Div(f"PNL: {p['unRealizedProfit']}", style={
                            'color': '#16c784' if float(p['unRealizedProfit']) >= 0 else '#ea3943',
                            'fontSize': '13px',
                            'fontWeight': 'bold'
                        })
                    ], width=5, className="text-end")
                ], className="g-1 mt-1")
            ], style={'marginBottom': '8px', 'backgroundColor': '#1e2329'}, className="p-2")
            for p in positions
        ] if positions else [
            html.P("No open positions", className="text-muted", style={'textAlign': 'center', 'marginTop': '10px'})]

        return (
            f"{futures_total:.2f} USDT",
            f"Last update: {timestamp}",
            html.Span(f"{total_pnl:+.2f} USDT ({pnl_percentage:+.2f}%)", style={'color': pnl_color}),
            html.Span(f"{total_size:.2f} USDT", style={'color': size_color}),
            html.Small(f"Used: {size_percent:.1f}% of balance", style={'color': size_color}),
            position_cards,
            f"{len(positions)}"
        )

    except Exception as e:
        logger.error(f"Update error: {e}")
        logger.error(traceback.format_exc())
        return "–", "", "Error", "–", "", html.P("Error loading positions", style={'textAlign': 'center'}), "–"


# =============
# Запуск сервера
# =============
if __name__ == '__main__':
    try:
        logger.info("🚀 Starting Binance Futures Dashboard...")
        server.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8066)), debug=False)
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        logger.error(traceback.format_exc())
    finally:
        balance_storage.close()