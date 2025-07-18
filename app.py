import os
from flask import Flask, render_template
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
from utils.binance_api import BinanceAPI
from utils.data_storage import BalanceStorage
from config import Config
import logging
logging.basicConfig(level=logging.INFO)
Config.validate_config()  # Проверит наличие обязательных переменных

# Инициализация Flask
server = Flask(__name__)
server.secret_key = Config.SECRET_KEY

# Инициализация Binance API
binance_api = BinanceAPI()

# Инициализация хранилища данных
balance_storage = BalanceStorage()


# Главная страница Flask
@server.route('/')
def index():
    try:
        # Получаем текущие балансы
        spot_balances = binance_api.get_current_balance()
        spot_total = sum(b['total'] for b in spot_balances) if spot_balances else 0

        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(b['balance'] for b in futures_balances) if futures_balances else 0

        # Сохраняем данные в историю
        balance_storage.save_balance(spot_total, futures_total)

        # Получаем открытые позиции
        futures_positions = binance_api.get_futures_positions()

        return render_template(
            'index.html',
            spot_balances=spot_balances or [],
            spot_total=spot_total,
            futures_balances=futures_balances or [],
            futures_total=futures_total,
            futures_positions=futures_positions or [],
            combined_total=spot_total + futures_total,
            last_update=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('error.html', error=str(e)), 500


# Инициализация Dash приложения
app = Dash(
    __name__,
    server=server,
    url_base_pathname='/dashboard/',
    external_stylesheets=[
        'https://codepen.io/chriddyp/pen/bWLwgP.css',
        'https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap'
    ]
)

# Макет Dash приложения
app.layout = html.Div([
    html.Div([
        html.H1("Binance Balance Dashboard", style={
            'textAlign': 'center',
            'fontFamily': 'Roboto',
            'color': '#f0b90b',
            'marginBottom': '30px'
        }),

        html.Div(id='live-update-text', style={
            'textAlign': 'center',
            'marginBottom': '20px',
            'fontSize': '16px'
        }),

        dcc.Graph(id='balance-graph'),

        dcc.Interval(
            id='interval-component',
            interval=5 * 60 * 1000,  # Обновление каждые 5 минут
            n_intervals=0
        )
    ], style={
        'padding': '40px',
        'maxWidth': '1200px',
        'margin': '0 auto',
        'fontFamily': 'Roboto'
    })
])


# Callback для обновления графика
@app.callback(
    Output('balance-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_graph(n):
    try:
        # Получаем исторические данные
        df = balance_storage.get_balance_history(30)

        # Получаем текущие балансы
        spot_balances = binance_api.get_current_balance()
        spot_total = sum(b['total'] for b in spot_balances) if spot_balances else 0

        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(b['balance'] for b in futures_balances) if futures_balances else 0

        current_total = spot_total + futures_total

        # Если нет исторических данных, создаем минимальный набор
        if df.empty:
            dates = [datetime.now() - timedelta(days=1), datetime.now()]
            df = pd.DataFrame({
                'date': dates,
                'spot_balance': [0, spot_total],
                'futures_balance': [0, futures_total],
                'total_balance': [0, current_total]
            })

        fig = go.Figure()

        # График общего баланса
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['total_balance'],
            mode='lines+markers',
            name='Total Balance',
            line=dict(color='#17BECF', width=3),
            hovertemplate='%{y:.2f} USDT<extra></extra>'
        ))

        # График спотового баланса
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['spot_balance'],
            mode='lines',
            name='Spot Balance',
            line=dict(color='#0ecb81', width=2, dash='dot'),
            hovertemplate='%{y:.2f} USDT<extra></extra>'
        ))

        # График фьючерсного баланса
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['futures_balance'],
            mode='lines',
            name='Futures Balance',
            line=dict(color='#f6465d', width=2, dash='dot'),
            hovertemplate='%{y:.2f} USDT<extra></extra>'
        ))

        # Обновляем layout
        fig.update_layout(
            title={
                'text': f'Balance History (Spot: {spot_total:.2f} USDT | Futures: {futures_total:.2f} USDT)',
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title='Date',
            yaxis_title='Balance (USDT)',
            template='plotly_dark',
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=50, r=50, t=80, b=50),
            plot_bgcolor='#1e2026',
            paper_bgcolor='#1e2026',
            font=dict(color='#eaecef')
        )

        # Добавляем текущий баланс как аннотацию
        if not df.empty:
            fig.add_annotation(
                x=df['date'].iloc[-1],
                y=current_total,
                text=f"Current: {current_total:.2f} USDT",
                showarrow=True,
                arrowhead=1,
                font=dict(size=12, color="#f0b90b"),
                bordercolor="#f0b90b",
                borderwidth=1,
                borderpad=4,
                bgcolor="#1e2026",
                opacity=0.8
            )

        return fig

    except Exception as e:
        print(f"Error updating graph: {e}")
        # Возвращаем пустой график в случае ошибки
        return go.Figure()


if __name__ == '__main__':
    try:
        # Проверка инициализации БД
        if not os.path.exists(Config.SQLALCHEMY_DATABASE_URI.split('///')[1]):
            balance_storage._init_db()

        server.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        balance_storage.close()  # Корректное закрытие при завершении