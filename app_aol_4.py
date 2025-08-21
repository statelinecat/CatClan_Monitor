import os
import logging
import requests
from flask import Flask, jsonify
from dash import Dash, dcc, html, callback_context, Input, Output, State
from dash import dash_table
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
from utils.binance_api import BinanceAPI
from utils.data_storage import BalanceStorage
from config import Config

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация конфигурации
Config.validate_config()

# Инициализация Flask
server = Flask(__name__)
server.secret_key = Config.SECRET_KEY

# Инициализация API и хранилища
binance_api = BinanceAPI()
balance_storage = BalanceStorage()

# Инициализация Dash
app = Dash(
    __name__,
    server=server,
    url_base_pathname='/',
    external_stylesheets=[
        'https://codepen.io/chriddyp/pen/bWLwgP.css  ',
        'https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap'
    ]
)

# =============
# Стили
# =============
styles = {
    'container': {
        'padding': '40px',
        'maxWidth': '1200px',
        'margin': '0 auto',
        'fontFamily': 'Roboto, sans-serif',
        'backgroundColor': '#1e2026',
        'color': '#eaecef'
    },
    'header': {
        'textAlign': 'center',
        'fontFamily': 'Roboto',
        'color': '#f0b90b',
        'marginBottom': '30px'
    },
    'button': {
        'backgroundColor': '#f0b90b',
        'color': '#1e2026',
        'border': 'none',
        'padding': '10px 20px',
        'margin': '0 10px',
        'borderRadius': '5px',
        'cursor': 'pointer',
        'fontWeight': '500'
    },
    'section': {
        'margin': '30px 0',
        'padding': '20px',
        'backgroundColor': '#1e2329',
        'borderRadius': '12px',
        'boxShadow': '0 4px 12px rgba(0,0,0,0.4)'
    },
    'h2': {
        'color': '#f0b90b',
        'marginBottom': '15px',
        'borderBottom': '1px solid #2c3137',
        'paddingBottom': '8px'
    }
}

# =============
# Макет Dash
# =============
app.layout = html.Div([
    html.Div([
        html.H1("Binance Futures Dashboard", style=styles['header']),

        # График баланса
        dcc.Graph(id='balance-graph'),

        # Кнопки периода
        html.Div([
            html.Button('30 дней', id='btn-30', n_clicks=0, style=styles['button']),
            html.Button('90 дней', id='btn-90', n_clicks=0, style=styles['button']),
            html.Button('Весь период', id='btn-all', n_clicks=0, style=styles['button'])
        ], style={'textAlign': 'center', 'margin': '20px 0'}),

        # Интервал обновления
        dcc.Interval(id='interval-component', interval=5 * 60 * 1000, n_intervals=0),

        # Блок: Общий баланс
        html.Div([
            html.H2("Total Futures Balance", style=styles['h2']),
            html.P(id='futures-total', style={'fontSize': '24px', 'fontWeight': 'bold'}),
            html.P(id='last-update')
        ], style=styles['section']),

        # Блок: PnL
        html.Div([
            html.H2("Total PnL", style=styles['h2']),
            html.P(id='total-pnl')
        ], style=styles['section']),

        # Таблица позиций
        html.Div([
            html.H2("Open Positions", style=styles['h2']),

            # Новый блок для общей суммы позиций
            html.P("Total size (USDT):", style={'fontSize': '18px', 'fontWeight': '500'}),
            html.P(id='positions-total-size', style={'fontSize': '22px', 'fontWeight': 'bold'}),

            dash_table.DataTable(
                id='positions-table',
                columns=[
                    {"name": "Symbol", "id": "symbol"},
                    {"name": "Side", "id": "positionSide"},
                    {"name": "Size (USDT)", "id": "size_usdt", "type": "numeric"},
                    {"name": "Leverage", "id": "leverage_x"},
                    {"name": "Contracts", "id": "contracts_abs", "type": "numeric"},
                    {"name": "Entry", "id": "entryPrice", "type": "numeric"},
                    {"name": "Mark", "id": "markPrice", "type": "numeric"},
                    {"name": "PNL", "id": "unRealizedProfit", "type": "numeric"},
                    {"name": "ROE (%)", "id": "roe", "type": "numeric"}
                ],
                sort_action="native",
                sort_mode="single",
                style_header={
                    'backgroundColor': '#1e2329',
                    'color': '#aaa',
                    'fontWeight': 'normal',
                    'borderBottom': '1px solid #2c3137',
                    'padding': '10px',
                    'fontSize': '13px'
                },
                style_cell={
                    'backgroundColor': '#161a1f',
                    'color': '#eaecef',
                    'textAlign': 'left',
                    'padding': '10px',
                    'borderBottom': '1px solid #2c3137',
                    'whiteSpace': 'no-wrap',
                    'lineHeight': '1.4'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'even'},
                        'backgroundColor': '#161a1f'
                    },
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': '#1e2329'
                    },
                    {
                        'if': {'filter_query': '{unRealizedProfit} > 0', 'column_id': 'unRealizedProfit'},
                        'color': '#16c784',
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {'filter_query': '{unRealizedProfit} < 0', 'column_id': 'unRealizedProfit'},
                        'color': '#ea3943',
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {'filter_query': '{roe} > 0', 'column_id': 'roe'},
                        'color': '#16c784',
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {'filter_query': '{roe} < 0', 'column_id': 'roe'},
                        'color': '#ea3943',
                        'fontWeight': 'bold'
                    }
                ],
                style_table={
                    'overflowX': 'auto',
                    'overflowY': 'auto',
                    'maxHeight': '800px'
                }
            )
        ], style=styles['section'])
    ], style=styles['container'])
])

# =============
# Callback: Обновление таблицы и баланса
# =============
@app.callback(
    [Output('futures-total', 'children'),
     Output('last-update', 'children'),
     Output('total-pnl', 'children'),
     Output('positions-table', 'data'),
     Output('positions-total-size', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_positions_table(n_intervals):
    try:
        resp = requests.get('http://localhost:5000/get_futures_data')
        data = resp.json()

        if 'error' in data:
            return "–", "", "Ошибка загрузки данных", [], "–"

        futures_total = data['futures_total']
        positions = data['positions']
        timestamp = data['timestamp']

        # Общий PnL
        total_pnl = sum(float(p['unRealizedProfit']) for p in positions) if positions else 0.0
        pnl_percentage = (total_pnl / futures_total * 100) if futures_total > 0 else 0
        pnl_text = html.Span(
            f"{total_pnl:+.2f} USDT ({pnl_percentage:+.2f}%)",
            style={'color': '#16c784' if total_pnl >= 0 else '#ea3943', 'fontWeight': 'bold'}
        )

        # Общая сумма позиций
        total_size = sum(float(p['size_usdt']) for p in positions) if positions else 0.0

        # Цвет: красный если size > balance, жёлтый если > 80% баланса
        if futures_total > 0:
            if total_size > futures_total:
                color = '#ea3943'  # красный
            elif total_size > futures_total * 0.8:
                color = '#f0b90b'  # жёлтый
            else:
                color = '#eaecef'  # белый
        else:
            color = '#eaecef'

        size_style = {'color': color, 'fontWeight': 'bold'}

        return (
            f"{futures_total:.2f} USDT",
            f"Last update: {timestamp}",
            html.P(["Unrealized PnL: ", pnl_text]),
            positions,
            html.Span(f"{total_size:.2f} USDT", style=size_style)
        )
    except Exception as e:
        logger.error(f"Error updating positions table: {e}")
        return "–", "", "Ошибка", [], "–"

# =============
# Запуск приложения
# =============
if __name__ == '__main__':
    try:
        server.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        balance_storage.close()
