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
        'fontFamily': 'Arial, Helvetica, sans-serif',
        'backgroundColor': '#1e2026',
        'color': '#eaecef'
    },
    'header': {
        'textAlign': 'center',
        'fontFamily': 'Arial, Helvetica, sans-serif',
        'color': '#f5f5dc',
        'marginBottom': '30px',
        'fontWeight': 'bold',
        'fontSize': '28px'
    },
    'button': {
        'backgroundColor': '#f5f5dc',
        'color': '#000000',
        'border': 'none',
        'padding': '10px 20px',
        'margin': '0 10px',
        'borderRadius': '4px',
        'cursor': 'pointer',
        'fontWeight': 'bold',
        'fontFamily': 'Arial, Helvetica, sans-serif',
        'fontSize': '18px',
        'boxShadow': '0 2px 4px rgba(0,0,0,0.2)',
        'textAlign': 'center',
        'display': 'inline-flex',
        'alignItems': 'center',
        'justifyContent': 'center',
        'minHeight': '36px',
        'textTransform': 'none'
    },
    'section': {
        'margin': '30px 0',
        'padding': '20px',
        'backgroundColor': '#1e2329',
        'borderRadius': '12px',
        'boxShadow': '0 4px 12px rgba(0,0,0,0.4)'
    },
    'h2': {
        'color': '#f5f5dc',
        'marginBottom': '15px',
        'borderBottom': '1px solid #2c3137',
        'paddingBottom': '8px',
        'fontFamily': 'Arial, Helvetica, sans-serif',
        'fontWeight': 'bold',
        'fontSize': '18px'
    }
}

# =============
# Макет Dash
# =============
app.layout = html.Div([
    # Хранилище для сохранения выбора типа графика
    dcc.Store(id='chart-type-store', data='lines'),

    html.Div([
        html.H1("📊 Binance Futures Dashboard", style=styles['header']),

        # Выбор типа графика
        html.Div([
            html.Span("📈 Chart Type: ", style={'color': '#f5f5dc', 'marginRight': '8px'}),
            dcc.Dropdown(
                id='chart-type',
                options=[
                    {'label': 'Lines', 'value': 'lines'},
                    {'label': 'Candlestick', 'value': 'candlestick'}
                ],
                value='lines',
                style={
                    'width': '140px',
                    'fontSize': '14px',
                    'color': '#000000'
                },
                clearable=False
            )
        ], style={'textAlign': 'center', 'margin': '10px 0'}),

        # Кнопки периода
        html.Div([
            html.Button('30 days', id='btn-30', n_clicks=0, style=styles['button']),
            html.Button('90 days', id='btn-90', n_clicks=0, style=styles['button']),
            html.Button('All time', id='btn-all', n_clicks=0, style=styles['button'])
        ], style={'textAlign': 'center', 'margin': '20px 0'}),

        # Интервал обновления
        dcc.Interval(id='interval-component', interval=5 * 60 * 1000, n_intervals=0),

        # График баланса
        dcc.Graph(id='balance-graph'),

        # Блок: Общий баланс
        html.Div([
            html.H2("💰 Total Futures Balance", style=styles['h2']),
            html.P(id='futures-total', style={'fontSize': '24px', 'fontWeight': 'bold'}),
            html.P(id='last-update')
        ], style=styles['section']),

        # Блок: PnL
        html.Div([
            html.H2("📈 Total PnL", style=styles['h2']),
            html.P(id='total-pnl')
        ], style=styles['section']),

        # Блок: Total Size
        html.Div([
            html.H2("💰 Total Size (USDT)", style=styles['h2']),
            html.P(id='total-size', style={'fontSize': '24px', 'fontWeight': 'bold'}),
            html.P(id='total-size-percent', style={'fontSize': '14px', 'marginTop': '5px'})
        ], style=styles['section']),

        # Таблица позиций с анимированным заголовком
        html.Div([
            # Анимированный заголовок: "📊🟢 Open Positions: 23"
            html.H2(
                children=[
                    "📊",
                    html.Span("🟢", style={
                        'display': 'inline-block',
                        'marginLeft': '8px',
                        'animation': 'float 2s ease-in-out infinite'
                    }),
                    html.Span(" Open Positions: ", style={'marginLeft': '6px'}),
                    html.Span(id='positions-count', style={'fontWeight': 'bold'})
                ],
                style=styles['h2']
            ),
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
                    'fontSize': '13px',
                    'fontFamily': 'Arial, Helvetica, sans-serif'
                },
                style_cell={
                    'backgroundColor': '#161a1f',
                    'color': '#eaecef',
                    'textAlign': 'left',
                    'padding': '10px',
                    'borderBottom': '1px solid #2c3137',
                    'whiteSpace': 'no-wrap',
                    'lineHeight': '1.4',
                    'fontFamily': 'Arial, Helvetica, sans-serif'
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
                    'maxHeight': None,
                    'height': 'auto'
                },
                page_action='none'
            )
        ], style=styles['section'])
    ], style=styles['container'])
])

# =============
# Callback: Сохранение выбора типа графика
# =============
@app.callback(
    Output('chart-type-store', 'data'),
    Input('chart-type', 'value')
)
def save_chart_type(chart_type):
    return chart_type

# =============
# Callback: Обновление графика
# =============
@app.callback(
    Output('balance-graph', 'figure'),
    [Input('btn-30', 'n_clicks'),
     Input('btn-90', 'n_clicks'),
     Input('btn-all', 'n_clicks'),
     Input('interval-component', 'n_intervals'),
     Input('chart-type-store', 'data')]
)
def update_graph(btn30, btn90, btn_all, n_intervals, chart_type):
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

        # Работаем с копией
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Фильтр по дате
        start_date = datetime(2025, 8, 1)
        df = df[df['date'] >= start_date]

        df = df.sort_values('date')

        # Создаём date_only
        df['date_only'] = df['date'].dt.date

        # Убираем нулевые балансы
        df_filtered = df[df['futures_balance'] > 0]
        if df_filtered.empty:
            df_filtered = df.copy()

        # Группируем
        daily_stats = df_filtered.groupby('date_only').agg(
            min_balance=('futures_balance', 'min'),
            max_balance=('futures_balance', 'max'),
            open_balance=('futures_balance', 'first'),
            close_balance=('futures_balance', 'last')
        ).reset_index()

        daily_stats['date'] = pd.to_datetime(daily_stats['date_only'])
        daily_stats = daily_stats.sort_values('date')

        if daily_stats.empty:
            daily_stats = pd.DataFrame({
                'date_only': [datetime.now().date()],
                'min_balance': [0],
                'max_balance': [0],
                'open_balance': [0],
                'close_balance': [0],
                'date': [datetime.now()]
            })

        fig = go.Figure()

        if chart_type == 'candlestick':
            # Кастомный hover через text
            hover_text = [
                f"<b>Open</b>: {o:.2f}<br>"
                f"<b>High</b>: {h:.2f}<br>"
                f"<b>Low</b>: {l:.2f}<br>"
                f"<b>Close</b>: {c:.2f}"
                for o, h, l, c in zip(
                    daily_stats['open_balance'],
                    daily_stats['max_balance'],
                    daily_stats['min_balance'],
                    daily_stats['close_balance']
                )
            ]

            fig.add_trace(go.Candlestick(
                x=daily_stats['date'],
                open=daily_stats['open_balance'],
                high=daily_stats['max_balance'],
                low=daily_stats['min_balance'],
                close=daily_stats['close_balance'],
                name='Balance',
                increasing_line_color='#16c784',
                decreasing_line_color='#ea3943',
                text=hover_text,
                hoverinfo='x+text',
                hoverlabel=dict(bgcolor='black', font_color='white')
            ))
        else:
            fig.add_trace(go.Scatter(
                x=daily_stats['date'],
                y=daily_stats['min_balance'],
                mode='lines',
                name='Min Balance',
                line=dict(color='#ea3943', width=1, dash='dot'),
                hovertemplate='Min: %{y:.2f} USDT<extra></extra>'
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats['date'],
                y=daily_stats['max_balance'],
                mode='lines',
                name='Max Balance',
                line=dict(color='#16c784', width=1, dash='dot'),
                hovertemplate='Max: %{y:.2f} USDT<extra></extra>'
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats['date'],
                y=daily_stats['close_balance'],
                mode='lines+markers',
                name='Close Balance',
                line=dict(color='#f6465d', width=3),
                marker=dict(size=6),
                hovertemplate='%{y:.2f} USDT<extra></extra>'
            ))

        fig.update_layout(
            title=f"Total Futures Balance - {f'{period_days} days' if period_days else 'All time'}",
            xaxis_title='Дата',
            yaxis_title='Баланс (USDT)',
            template='plotly_dark',
            hovermode='x unified',
            plot_bgcolor='#1e2026',
            paper_bgcolor='#1e2026',
            font=dict(color='#eaecef'),
            xaxis=dict(tickformat='%d.%m', tickmode='auto', nticks=10),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
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
        futures_balances = binance_api.get_futures_balance()
        futures_total = sum(
            float(b['balance']) for b in futures_balances
            if isinstance(b, dict) and 'balance' in b
        ) if futures_balances else 0.0

        raw_positions = binance_api.get_futures_positions()
        positions = raw_positions.get('positions', []) if isinstance(raw_positions, dict) else raw_positions or []

        df_positions = pd.DataFrame(positions)
        if not df_positions.empty:
            df_positions['size_usdt'] = df_positions['usdtValue'].round(2)
            df_positions['leverage_x'] = df_positions['leverage'].astype(str) + 'x'
            df_positions['contracts_abs'] = df_positions['positionAmt'].abs()
            df_positions['entryPrice'] = df_positions['entryPrice'].round(6)
            df_positions['markPrice'] = df_positions['markPrice'].round(6)
            df_positions['unRealizedProfit'] = df_positions['unRealizedProfit'].round(2)
            df_positions['roe'] = df_positions['roe'].round(2)

            df_positions = df_positions[[
                'symbol', 'positionSide', 'size_usdt', 'leverage_x', 'contracts_abs',
                'entryPrice', 'markPrice', 'unRealizedProfit', 'roe'
            ]]
        else:
            df_positions = pd.DataFrame(columns=[
                'symbol', 'positionSide', 'size_usdt', 'leverage_x', 'contracts_abs',
                'entryPrice', 'markPrice', 'unRealizedProfit', 'roe'
            ])

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
# Callback: Обновление всех данных
# =============
@app.callback(
    [Output('futures-total', 'children'),
     Output('last-update', 'children'),
     Output('total-pnl', 'children'),
     Output('total-size', 'children'),
     Output('total-size-percent', 'children'),
     Output('positions-table', 'data'),
     Output('positions-count', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_positions_table(n_intervals):
    try:
        resp = requests.get('http://localhost:5000/get_futures_data')
        data = resp.json()

        if 'error' in data:
            return "–", "", "Ошибка загрузки данных", "–", "", [], "–"

        futures_total = data['futures_total']
        positions = data['positions']
        timestamp = data['timestamp']

        total_pnl = sum(float(p['unRealizedProfit']) for p in positions) if positions else 0.0
        pnl_percentage = (total_pnl / futures_total * 100) if futures_total > 0 else 0

        total_size = sum(float(p['size_usdt']) for p in positions) if positions else 0.0
        size_percent = (total_size / futures_total * 100) if futures_total > 0 else 0

        size_color = '#ea3943' if total_size > futures_total else '#16c784'

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
            html.Span(
                f"{total_size:.2f} USDT",
                style={'color': size_color, 'fontWeight': 'bold'}
            ),
            html.Span(
                f"Used: {size_percent:.1f}% of the balance",
                style={'color': size_color}
            ),
            positions,
            f"{len(positions)}"
        )
    except Exception as e:
        logger.error(f"Error updating positions table: {e}")
        return "–", "", "Ошибка", "–", "", [], "–"

# =============
# Запуск приложения
# =============
if __name__ == '__main__':
    try:
        server.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        balance_storage.close()