import os
import logging
from flask import Flask, render_template, jsonify
from dash import Dash, dcc, html, callback_context
from dash.dependencies import Input, Output, State
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

# Инициализация Dash приложения
app = Dash(
    __name__,
    server=server,
    url_base_pathname='/',
    external_stylesheets=[
        'https://codepen.io/chriddyp/pen/bWLwgP.css',
        'https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap'
    ]
)

# Макет Dash приложения
app.layout = html.Div([
    html.Div([
        html.H1("Binance Futures Dashboard", style={
            'textAlign': 'center',
            'fontFamily': 'Roboto',
            'color': '#f0b90b',
            'marginBottom': '30px'
        }),

        dcc.Graph(id='balance-graph'),

        html.Div([
            html.Button('30 дней', id='btn-30', n_clicks=0, style={
                'backgroundColor': '#f0b90b',
                'color': '#1e2026',
                'border': 'none',
                'padding': '10px 20px',
                'margin': '0 10px',
                'borderRadius': '5px',
                'cursor': 'pointer'
            }),
            html.Button('90 дней', id='btn-90', n_clicks=0, style={
                'backgroundColor': '#f0b90b',
                'color': '#1e2026',
                'border': 'none',
                'padding': '10px 20px',
                'margin': '0 10px',
                'borderRadius': '5px',
                'cursor': 'pointer'
            }),
            html.Button('Весь период', id='btn-all', n_clicks=0, style={
                'backgroundColor': '#f0b90b',
                'color': '#1e2026',
                'border': 'none',
                'padding': '10px 20px',
                'margin': '0 10px',
                'borderRadius': '5px',
                'cursor': 'pointer'
            })
        ], style={
            'textAlign': 'center',
            'margin': '20px 0'
        }),

        dcc.Interval(
            id='interval-component',
            interval=5 * 60 * 1000,
            n_intervals=0
        ),

        # Контейнер для содержимого Flask
        html.Iframe(id='flask-content', src='/flask-content', style={
            'width': '100%',
            'height': '1200px',
            'border': 'none'
        })
    ], style={
        'padding': '40px',
        'maxWidth': '1200px',
        'margin': '0 auto',
        'fontFamily': 'Roboto',
        'backgroundColor': '#1e2026',
        'color': '#eaecef'
    })
])

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

    period_map = {
        'btn-30': 30,
        'btn-90': 90,
        'btn-all': None
    }
    period_days = period_map.get(button_id, 30)

    try:
        df = balance_storage.get_balance_history(period_days or 9999)
        logger.info(f"Balance history data before filtering: {df}")

        # Преобразование столбца 'date' в datetime
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            logger.info(f"Balance history data after converting to datetime: {df}")

            # Фильтрация данных: только записи с 01.08.2025
            start_date = datetime(2025, 8, 1)
            df = df[df['date'] >= start_date]
            logger.info(f"Balance history data after filtering (from 01.08.2025): {df}")

        futures_data = get_futures_data()

        if df.empty:
            df = pd.DataFrame({
                'date': [max(datetime.now() - timedelta(days=1), start_date), datetime.now()],
                'futures_balance': [0, futures_data['futures_total']]
            })

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=df['date'],
                    y=df['futures_balance'],
                    mode='lines+markers',
                    name='Futures Balance',
                    line=dict(color='#f6465d', width=3),
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
                font=dict(color='#eaecef')
            )
        )

        return fig
    except Exception as e:
        logger.error(f"Error updating graph: {e}")
        return go.Figure()

def get_futures_data():
    try:
        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(float(b['balance']) for b in futures_balances if isinstance(b, dict) and 'balance' in b) if futures_balances else 0
        return {'futures_total': futures_total}
    except Exception as e:
        logger.error(f"Error getting futures data: {e}")
        return {'futures_total': 0}

@server.route('/flask-content')
def flask_content():
    try:
        # Получение и логирование балансов спот
        spot_balances = binance_api.get_current_balance()
        logger.info(f"Spot balances: {spot_balances}")
        spot_balances = spot_balances.get('assets', []) if isinstance(spot_balances, dict) else spot_balances or []
        spot_total = sum(float(b['total']) for b in spot_balances if isinstance(b, dict) and 'total' in b) if spot_balances else 0

        # Получение и логирование балансов фьючерсов
        futures_balances = binance_api.get_futures_balance()
        logger.info(f"Futures balances: {futures_balances}")
        futures_balances = futures_balances.get('assets', []) if isinstance(futures_balances, dict) else futures_balances or []
        futures_total = sum(float(b['balance']) for b in futures_balances if isinstance(b, dict) and 'balance' in b) if futures_balances else 0

        # Сохранение балансов
        balance_storage.save_balance(spot_total, futures_total)

        # Получение и логирование позиций фьючерсов
        futures_positions = binance_api.get_futures_positions()
        logger.info(f"Futures positions: {futures_positions}")
        logger.info(f"Number of futures positions: {len(futures_positions)}")
        logger.info(f"Sample position: {futures_positions[0] if futures_positions else 'No positions'}")
        futures_positions = futures_positions.get('positions', []) if isinstance(futures_positions, dict) else futures_positions or []
        total_unrealized_pnl = sum(float(pos['unRealizedProfit']) for pos in futures_positions if isinstance(pos, dict) and 'unRealizedProfit' in pos) if futures_positions else 0

        # Расчет процента PNL
        pnl_percentage = (total_unrealized_pnl / futures_total * 100) if futures_total > 0 else 0

        return render_template(
            'flask_content.html',
            futures_balances=futures_balances,
            futures_total=futures_total,
            futures_positions=futures_positions,
            total_unrealized_pnl=total_unrealized_pnl,
            pnl_percentage=pnl_percentage,
            last_update=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        logger.error(f"Ошибка в маршруте flask-content: {e}")
        return render_template('error.html', error=str(e)), 500

if __name__ == '__main__':
    try:
        server.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        balance_storage.close()