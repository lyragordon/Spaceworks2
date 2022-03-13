import pandas as pd
pd.options.plotting.backend = "plotly"
import serial as s

# Visualization Imports
import plotly.express as px
import numpy as np
j = 0

import dash as ds
from dash import dcc, html
from dash.dependencies import Input, Output

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = ds.Dash(__name__, external_stylesheets=external_stylesheets)
app.layout = html.Div(
    html.Div([
        html.H4('SW Optics Live Feed'),
        dcc.Graph(id='live-update-graph'),
        dcc.Interval(
            id='interval-component',
            interval=1*5000, #To be changed with refresh rate.
            n_intervals=0
        ),
        html.Button('Save Picture', id='take-pic'),
        html.Div(id='pic-confirm'),
    ])
)

@app.callback(Output('live-update-graph', 'figure'),
              Input('interval-component', 'n_intervals'))
def update_metrics(n):
    data = (np.random.rand(24,32)+2.5)*10
    a = data
    #a = np.reshape(np.array([float(i) for i in data.split(", ")]), (24,32))
    global fig
    maxHeat = np.max(a)
    minHeat = np.min(a)
    avgHeat = np.average(a)
    fig = px.imshow(a, text_auto=True, labels=dict(color="Temperaute, Celsius"), title='Minimum: {0:0.2f} Celsius, Maximum: {1:0.2f} Celsius, Average: {2:0.2f} Celsius.'.format(minHeat,maxHeat,avgHeat))
    return fig

@app.callback(
    Output(component_id='pic-confirm', component_property='children'),
    Input(component_id='take-pic', component_property='n_clicks')
)
def update_output(n_clicks):
    global j
    if n_clicks is None:
        return ""
    else:
        fig.write_image("C:/Users/ranes/Documents/SpaceWorks/PlotsTrial/fig{}.png".format(j))
        j += 1
        n_clicks = 0
        return "Saved {} Picture(s)!".format(j)



if __name__ == '__main__':
    app.run_server(debug=True)