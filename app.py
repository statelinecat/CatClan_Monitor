import os
import logging
import traceback
from flask import Flask
from dash import Dash, dcc, html, callback_context, Input, Output, State
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

# Инициализация Dash с Bootstrap
app = Dash(
    __name__,
    server=server,
    url_base_pathname='/',
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    title="CatClan Monitor"  # Отображается в заголовке браузера
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
    # Метатеги
    dcc.Location(id='url'),
    html.Meta(name='viewport', content='width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'),
    html.Link(rel='icon', href='/assets/favicon.svg'),  # Иконка (опционально)

    # Хранилище для сортировки
    dcc.Store(id='sort-store', data={'field': 'size_usdt', 'order': 'desc'}),

    # Основной контейнер
    dbc.Container([
        # Заголовок
        dbc.Row([
            dbc.Col(
                html.H1("🐱 CatClan Monitor", className="text-center my-3", style={
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
                dcc.Graph(
                    id='balance-graph',
                    style={'height': '300px'},
                    config={'displayModeBar': False}
                ),
                # Кнопки периодов
                html.Div([
                    html.Div(
                        id='period-buttons-container',
                        style={
                            'display': 'flex',
                            'justifyContent': 'center',
                            'overflowX': 'auto',
                            'padding': '8px 0',
                            'gap': '8px',
                            'scrollbarWidth': 'thin',
                            'WebkitOverflowScrolling': 'touch',
                            'width': '100%'
                        },
                        children=[
                            dbc.Button("7D", id='btn-7d', color="secondary", size="sm", className="period-btn"),
                            dbc.Button("14D", id='btn-14d', color="secondary", size="sm", className="period-btn"),
                            dbc.Button("1M", id='btn-1m', color="secondary", size="sm", className="period-btn"),
                            dbc.Button("3M", id='btn-3m', color="secondary", size="sm", className="period-btn"),
                            dbc.Button("6M", id='btn-6m', color="secondary", size="sm", className="period-btn"),
                            dbc.Button("12M", id='btn-12m', color="secondary", size="sm", className="period-btn"),
                            dbc.Button("All", id='btn-all', color="secondary", size="sm", className="period-btn"),
                        ]
                    )
                ], style={'width': '100%', 'overflow': 'hidden'})
            ])
        ], className="mb-3"),

        # Интервал автообновления
        dcc.Interval(id='interval-component', interval=5 * 60 * 1000, n_intervals=0),

        # Статистика
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

        # Заголовок с сортировкой
        dbc.Row([
            dbc.Col([
                html.H5([
                    html.Span("🟢", className="float-animation", style={'marginRight': '6px'}),  # ✅ Анимация через CSS
                    "Open Positions: ",
                    html.Strong(id='positions-count'),
                    html.Span(" ", style={'width': '8px', 'display': 'inline-block'}),
                    html.Span("🔄", id='sort-icon', style={
                        'transform': 'rotate(0deg)',
                        'transition': 'transform 0.3s ease',
                        'cursor': 'pointer',
                        'fontSize': '18px'
                    })
                ], style={'color': '#f5f5dc', 'textAlign': 'center', 'cursor': 'pointer'}, id='positions-header')
            ], width=12, className="my-3")
        ]),

        # Карточки позиций
        dbc.Row([
            dbc.Col([
                html.Div(id='positions-container', style={'marginTop': '10px'})
            ], width=12)
        ], className="mb-3")

    ], fluid=False, style={'padding': '10px', 'minHeight': '100vh'})

], style={'backgroundColor': '#121212', 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'})


# =============
# Получение данных фьючерсов
# =============
def get_futures_data():
    try:
        logger.info("Fetching futures data from Binance API...")

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

            positions_data = df_positions[[
                'symbol', 'positionSide', 'size_usdt', 'leverage_x', 'contracts_abs',
                'entryPrice', 'markPrice', 'unRealizedProfit', 'roe'
            ]].to_dict('records')
        else:
            positions_data = []

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
# Callback: Обновление графика и кнопок
# =============
@app.callback(
    [Output('btn-7d', 'className'),
     Output('btn-14d', 'className'),
     Output('btn-1m', 'className'),
     Output('btn-3m', 'className'),
     Output('btn-6m', 'className'),
     Output('btn-12m', 'className'),
     Output('btn-all', 'className'),
     Output('balance-graph', 'figure')],
    [Input('btn-7d', 'n_clicks'),
     Input('btn-14d', 'n_clicks'),
     Input('btn-1m', 'n_clicks'),
     Input('btn-3m', 'n_clicks'),
     Input('btn-6m', 'n_clicks'),
     Input('btn-12m', 'n_clicks'),
     Input('btn-all', 'n_clicks'),
     Input('interval-component', 'n_intervals')]
)
def update_graph_and_buttons(btn_7d, btn_14d, btn_1m, btn_3m, btn_6m, btn_12m, btn_all, n_intervals):
    ctx = callback_context
    if not ctx.triggered:
        button_id = 'btn-1m'
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    btn_classes = {
        'btn-7d': 'period-btn',
        'btn-14d': 'period-btn',
        'btn-1m': 'period-btn',
        'btn-3m': 'period-btn',
        'btn-6m': 'period-btn',
        'btn-12m': 'period-btn',
        'btn-all': 'period-btn'
    }
    btn_classes[button_id] += ' active'

    period_map = {
        'btn-7d': 7,
        'btn-14d': 14,
        'btn-1m': 30,
        'btn-3m': 90,
        'btn-6m': 180,
        'btn-12m': 365,
        'btn-all': None
    }
    period_days = period_map.get(button_id, 30)

    try:
        df = balance_storage.get_balance_history(9999)
        if df.empty:
            fig = go.Figure().update_layout(title="No data", template="plotly_dark", height=300)
            return list(btn_classes.values()) + [fig]

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Фильтр: с 01.08.2025
        start_date = datetime(2025, 8, 1)
        df = df[df['date'] >= start_date]

        if period_days is not None:
            cutoff_date = datetime.now() - timedelta(days=period_days)
            df = df[df['date'] >= cutoff_date]

        if df.empty:
            fig = go.Figure().update_layout(title="No data", template="plotly_dark", height=300)
            return list(btn_classes.values()) + [fig]

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

        fig.add_trace(go.Scatter(
            x=df_daily['date'],
            y=df_daily['min_balance'],
            mode='lines',
            line=dict(color='#ea3943', width=1, dash='dot'),
            showlegend=False,
            hovertemplate='Min: %{y:.2f} USDT<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=df_daily['date'],
            y=df_daily['max_balance'],
            mode='lines',
            line=dict(color='#16c784', width=1, dash='dot'),
            showlegend=False,
            hovertemplate='Max: %{y:.2f} USDT<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=df_daily['date'],
            y=df_daily['last_balance'],
            mode='lines+markers',
            line=dict(color='#f6465d', width=2.5),
            marker=dict(size=4),
            hovertemplate='%{y:.2f} USDT<extra></extra>',
            showlegend=False
        ))

        period_labels = {7: "7D", 14: "14D", 30: "1M", 90: "3M", 180: "6M", 365: "12M", None: "All"}
        period_label = period_labels.get(period_days, "Custom")

        fig.update_layout(
            title=f"Total Futures Balance — {period_label}",
            xaxis_title="",
            yaxis_title="USDT",
            template="plotly_dark",
            height=300,
            margin=dict(l=50, r=20, t=50, b=40),
            hovermode='x unified',
            xaxis=dict(tickformat='%d.%m', tickmode='auto', nticks=6, showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=10),
            transition=dict(duration=400, easing='cubic-in-out')
        )

        return list(btn_classes.values()) + [fig]

    except Exception as e:
        logger.error(f"Graph update error: {e}")
        fig = go.Figure().update_layout(title="Error", template="plotly_dark", height=300)
        return list(btn_classes.values()) + [fig]


# =============
# Callback: Переключение сортировки
# =============
@app.callback(
    Output('sort-store', 'data'),
    Input('positions-header', 'n_clicks'),
    State('sort-store', 'data')
)
def toggle_sort_field(n_clicks, current_sort):
    if n_clicks is None:
        return current_sort

    fields = ['size_usdt', 'unRealizedProfit', 'roe']
    current_field = current_sort['field']
    idx = fields.index(current_field)
    next_field = fields[(idx + 1) % len(fields)]

    return {'field': next_field, 'order': 'desc'}


# =============
# Callback: Обновление данных и карточек
# =============
@app.callback(
    [Output('futures-total', 'children'),
     Output('last-update', 'children'),
     Output('total-pnl', 'children'),
     Output('total-size', 'children'),
     Output('total-size-percent', 'children'),
     Output('positions-container', 'children'),
     Output('positions-count', 'children'),
     Output('sort-icon', 'style')],
    [Input('interval-component', 'n_intervals'),
     Input('sort-store', 'data')]
)
def update_data_and_sort(n_intervals, sort_data):
    try:
        data = get_futures_data()
        if 'error' in data:
            logger.error(f"Data fetch error: {data['error']}")
            return "–", "", "Error", "–", "", html.P("Failed to load"), "–", {'transform': 'rotate(0deg)'}

        futures_total = data['futures_total']
        positions = data['positions']
        timestamp = data['timestamp']

        total_pnl = sum(float(p['unRealizedProfit']) for p in positions) if positions else 0.0
        pnl_percentage = (total_pnl / futures_total * 100) if futures_total > 0 else 0
        pnl_color = '#16c784' if total_pnl >= 0 else '#ea3943'

        total_size = sum(float(p['size_usdt']) for p in positions) if positions else 0.0
        size_percent = (total_size / (20 * futures_total) * 100) if futures_total > 0 else 0
        size_color = '#ea3943' if total_size > (10 * futures_total) else '#16c784'

        # Сортировка
        field = sort_data['field']
        reverse = sort_data['order'] == 'desc'
        sorted_positions = sorted(positions, key=lambda x: float(x[field]), reverse=reverse)

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
            for p in sorted_positions
        ] if sorted_positions else [html.P("No open positions", className="text-muted", style={'textAlign': 'center', 'marginTop': '10px'})]

        # Анимация иконки
        rotation = (n_intervals * 10) % 360 if sort_data['field'] == 'size_usdt' else 0
        icon_style = {
            'transform': f'rotate({rotation}deg)',
            'transition': 'transform 0.3s ease',
            'cursor': 'pointer',
            'fontSize': '18px'
        }

        return (
            f"{futures_total:.2f} USDT",
            f"Last update: {timestamp}",
            html.Span(f"{total_pnl:+.2f} USDT ({pnl_percentage:+.2f}%)", style={'color': pnl_color}),
            html.Span(f"{total_size:.2f} USDT", style={'color': size_color}),
            html.Small(f"Used: {size_percent:.1f}% of balance", style={'color': size_color}),
            position_cards,
            f"{len(positions)}",
            icon_style
        )

    except Exception as e:
        logger.error(f"Update error: {e}")
        logger.error(traceback.format_exc())
        return "–", "", "Error", "–", "", html.P("Error"), "–", {}


# =============
# Запуск сервера
# =============
if __name__ == '__main__':
    try:
        logger.info("🚀 Starting CatClan Monitor...")
        port = int(os.environ.get("PORT", 8066))
        server.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        logger.error(traceback.format_exc())
    finally:
        balance_storage.close()