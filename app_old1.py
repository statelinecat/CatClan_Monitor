import os
from flask import Flask, render_template, jsonify
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
Config.validate_config()

# Инициализация Flask
server = Flask(__name__)
server.secret_key = Config.SECRET_KEY

# Инициализация Binance API
binance_api = BinanceAPI()

# Инициализация хранилища данных
balance_storage = BalanceStorage()


def format_datetime_for_json(dt):
    """Форматирование datetime для JSON ответа"""
    return dt.strftime('%Y-%m-%d %H:%M:%S') if isinstance(dt, (datetime, pd.Timestamp)) else dt


def get_futures_data():
    """Получение и обработка фьючерсных данных"""
    try:
        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(b['balance'] for b in futures_balances) if futures_balances else 0

        futures_positions = binance_api.get_futures_positions()

        total_unrealized_pnl = sum(pos['unRealizedProfit'] for pos in futures_positions)
        total_unrealized_pnl_roe = (total_unrealized_pnl / futures_total * 100) if futures_total > 0 else 0

        daily_pnl = total_unrealized_pnl
        daily_pnl_roe = (daily_pnl / futures_total * 100) if futures_total > 0 else 0

        return {
            'futures_balances': futures_balances or [],
            'futures_total': futures_total,
            'futures_positions': futures_positions or [],
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_unrealized_pnl_roe': total_unrealized_pnl_roe,
            'daily_pnl': daily_pnl,
            'daily_pnl_roe': daily_pnl_roe
        }
    except Exception as e:
        logging.error(f"Error getting futures data: {e}")
        raise


def get_spot_data():
    """Получение спотовых данных (только для сохранения в БД)"""
    try:
        spot_balances = binance_api.get_current_balance()
        spot_total = sum(b['total'] for b in spot_balances) if spot_balances else 0
        return spot_total
    except Exception as e:
        logging.error(f"Error getting spot data: {e}")
        return 0


@server.route('/get_futures_graph_data')
def get_futures_graph_data():
    try:
        df = balance_storage.get_balance_history(30)

        if df.empty:
            return jsonify({
                'dates': [],
                'futures_balance': [],
                'total_balance': []
            })

        # Преобразуем даты в строки
        dates = [format_datetime_for_json(dt) for dt in df['date']]

        return jsonify({
            'dates': dates,
            'futures_balance': df['futures_balance'].tolist(),
            'total_balance': df['futures_balance'].tolist()
        })
    except Exception as e:
        logging.error(f"Error in get_futures_graph_data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@server.route('/')
def index():
    try:
        futures_data = get_futures_data()
        spot_total = get_spot_data()

        balance_storage.save_balance(spot_total, futures_data['futures_total'])

        return render_template(
            'index.html',
            last_update=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **futures_data
        )
    except Exception as e:
        logging.error(f"Error in index route: {e}", exc_info=True)
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

app.layout = html.Div([
    html.Div([
        html.H1("Binance Futures Dashboard", style={
            'textAlign': 'center',
            'fontFamily': 'Roboto',
            'color': '#f0b90b',
            'marginBottom': '30px'
        }),
        dcc.Graph(id='balance-graph'),
        dcc.Interval(
            id='interval-component',
            interval=5 * 60 * 1000,
            n_intervals=0
        )
    ], style={
        'padding': '40px',
        'maxWidth': '1200px',
        'margin': '0 auto',
        'fontFamily': 'Roboto'
    })
])


@app.callback(
    Output('balance-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_graph(n):
    try:
        df = balance_storage.get_balance_history(30)
        futures_data = get_futures_data()

        if df.empty:
            dates = [datetime.now() - timedelta(days=1), datetime.now()]
            df = pd.DataFrame({
                'date': dates,
                'futures_balance': [0, futures_data['futures_total']],
                'total_balance': [0, futures_data['futures_total']]
            })

        # Убедимся, что даты в правильном формате
        df['date'] = pd.to_datetime(df['date'])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['futures_balance'],
            mode='lines+markers',
            name='Futures Balance',
            line=dict(color='#f6465d', width=3),
            hovertemplate='%{y:.2f} USDT<extra></extra>'
        ))

        fig.update_layout(
            title=f'Futures Balance History (Current: {futures_data["futures_total"]:.2f} USDT)',
            xaxis_title='Date',
            yaxis_title='Balance (USDT)',
            template='plotly_dark',
            hovermode='x unified',
            plot_bgcolor='#1e2026',
            paper_bgcolor='#1e2026',
            font=dict(color='#eaecef')
        )

        return fig
    except Exception as e:
        logging.error(f"Error updating graph: {e}", exc_info=True)
        return go.Figure()


if __name__ == '__main__':
    try:
        # Проверка инициализации БД
        db_path = Config.SQLALCHEMY_DATABASE_URI.split('///')[1]
        if not os.path.exists(db_path):
            balance_storage._init_db()
            logging.info(f"Initialized new database at {db_path}")

        server.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logging.error(f"Failed to start server: {e}", exc_info=True)
    finally:
        balance_storage.close()