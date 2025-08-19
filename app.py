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
        'https://codepen.io/chriddyp/pen/bWLwgP.css',
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
                    # Чередование цветов строк
                    {
                        'if': {'row_index': 'even'},
                        'backgroundColor': '#161a1f'
                    },
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': '#1e2329'
                    },
                    # Цвет PNL
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
                    # Цвет ROE
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
                    'maxHeight': '800px'  # Можно убрать, если хочешь бесконечную высоту
                }
            )
        ], style=styles['section'])
    ], style=styles['container'])
])

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
        logger.info(f"Balance history before processing: {df}")

        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title="Нет данных",
                template="plotly_dark",
                font=dict(color="#eaecef")
            )
            return fig

        # Преобразуем 'date' в datetime
        df['date'] = pd.to_datetime(df['date'])

        # Фильтруем по дате (начиная с 01.08.2025)
        start_date = datetime(2025, 8, 1)
        df = df[df['date'] >= start_date]

        # Убедимся, что отсортировано по времени
        df = df.sort_values('date')

        # Группируем по дате (без времени) и берём последнюю запись за день
        df['date_only'] = df['date'].dt.date
        df_daily = df.groupby('date_only').last().reset_index()

        # Восстанавливаем полноценную дату (для графика)
        df_daily['date'] = pd.to_datetime(df_daily['date_only'])

        # Сортируем по дате
        df_daily = df_daily.sort_values('date')

        # Если всё ещё пусто
        if df_daily.empty:
            df_daily = pd.DataFrame({
                'date': [datetime.now()],
                'futures_balance': [0]
            })

        # Строим график
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=df_daily['date'],
                    y=df_daily['futures_balance'],
                    mode='lines+markers',
                    name='Futures Balance',
                    line=dict(color='#f6465d', width=3),
                    marker=dict(size=6),
                    hovertemplate='%{y:.2f} USDT<extra></extra>'
                )
            ],
            layout=go.Layout(
                title=f"История баланса фьючерсов - {f'Последние {period_days} дней' if period_days else 'Весь период'}",
                xaxis_title='Дата',
                yaxis_title='Баланс (USDT)',
                template='plotly_dark',
                hovermode='x unified',
                plot_bgcolor='#1e2026',
                paper_bgcolor='#1e2026',
                font=dict(color='#eaecef'),
                xaxis=dict(
                    tickformat='%d.%m',
                    tickmode='auto',
                    nticks=10
                )
            )
        )

        return fig

    except Exception as e:
        logger.error(f"Error updating graph: {e}")
        fig = go.Figure()
        fig.update_layout(
            title="Ошибка загрузки данных",
            template="plotly_dark",
            font=dict(color="#eaecef")
        )
        return fig

# =============
# API: Получение данных фьючерсов
# =============
@server.route('/get_futures_data')
def get_futures_data():
    try:
        # Получение балансов
        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(
            float(b['balance']) for b in futures_balances
            if isinstance(b, dict) and 'balance' in b
        ) if futures_balances else 0.0

        # Получение позиций
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

            # Оставляем нужные колонки
            df_positions = df_positions[[
                'symbol', 'positionSide', 'size_usdt', 'leverage_x', 'contracts_abs',
                'entryPrice', 'markPrice', 'unRealizedProfit', 'roe'
            ]]
        else:
            df_positions = pd.DataFrame(columns=[
                'symbol', 'positionSide', 'size_usdt', 'leverage_x', 'contracts_abs',
                'entryPrice', 'markPrice', 'unRealizedProfit', 'roe'
            ])

        # Сохраняем баланс
        balance_storage.save_balance(0, futures_total)

        return jsonify({
            'futures_total': round(futures_total, 2),
            'positions': df_positions.to_dict('records'),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logger.error(f"Error getting futures data: {e}")
        return jsonify({'error': str(e)}), 500

# =============
# Callback: Обновление таблицы и баланса
# =============
@app.callback(
    [Output('futures-total', 'children'),
     Output('last-update', 'children'),
     Output('total-pnl', 'children'),
     Output('positions-table', 'data')],
    [Input('interval-component', 'n_intervals')]
)
def update_positions_table(n_intervals):
    try:
        resp = requests.get('http://localhost:5000/get_futures_data')
        data = resp.json()

        if 'error' in data:
            return "–", "", "Ошибка загрузки данных", []

        futures_total = data['futures_total']
        positions = data['positions']
        timestamp = data['timestamp']

        # Расчёт общего PnL
        total_pnl = sum(float(p['unRealizedProfit']) for p in positions) if positions else 0.0
        pnl_percentage = (total_pnl / futures_total * 100) if futures_total > 0 else 0

        pnl_text = html.Span(
            f"{total_pnl:+.2f} USDT ({pnl_percentage:+.2f}%)",
            style={'color': '#16c784' if total_pnl >= 0 else '#ea3943', 'fontWeight': 'bold'}
        )

        return (
            f"{futures_total:.2f} USDT",
            f"Last update: {timestamp}",
            html.P([
                "Unrealized PnL: ", pnl_text
            ]),
            positions
        )
    except Exception as e:
        logger.error(f"Error updating positions table: {e}")
        return "–", "", "Ошибка", []

# =============
# Запуск приложения
# =============
if __name__ == '__main__':
    try:
        server.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        balance_storage.close()