from pathlib import Path
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
import numpy as np 
import openmeteo_requests
from shinywidgets import render_widget,output_widget 
from ipyleaflet import GeoJSON, Map, Marker  
from plotnine import element_text, ggplot, aes, geom_point, geom_line, geom_hline, scale_x_date, theme, theme_bw, scale_fill_manual, labs, scale_y_continuous , scale_x_datetime
from prophet import Prophet
 

cities = pd.read_csv("data/cities.csv")  

choices=cities['city']+", "+cities['state_name']
choices = list(choices)

app_ui = ui.page_sidebar( # Reference for shiny ui : https://shiny.posit.co/py/components/
    ui.sidebar(
        ui.input_selectize("city","City",choices,selected="Urbana, Illinois"),
        ui.div(ui.output_ui("value", style="text-align: center;"),align="center"),        
        ui.input_date_range("daterange", "Dates", start="2022-01-01", end="2024-01-01"),
        ui.input_numeric("numeric", "Years to Forecast", 1, min=1, max=10),
        ui.input_radio_buttons("radio1","Forecast Trends",{"1": "Flat", "2": "Linear"},),
        ui.input_radio_buttons("radio2","Units",{"1": "Fahrenheit", "2": "Celsius"},),
        (ui.input_slider("slider1", "Plot Temperature", -15, 50, 5),),
        ui.input_checkbox_group("checkbox_group","Plot Options", { "a": "Weekly Rolling Average", "b": "Monthly Rolling Average",},),
        ui.input_slider("slider2", "Table Temperatures", min=-25, max=60, value=[0, 15]),
        output_widget("map",fillable=True,height=200), width= 350, bg="#f8f8f8",  open="always",), 
       
        ui.div(
            ui.navset_underline(  
            ui.nav_panel("Historical", 
            ui.output_plot("graph"),
            ui.output_data_frame("table"), 
        ),
        ui.nav_panel("Forecast",
            ui.output_plot("prop"),
            ui.output_data_frame("table2"),  
        ),
        ui.nav_panel("About", ui.markdown(""" ### Welcome!

Welcome to this interactive dashboard, created to visually depict the efficacy of heat pumps in various locations across the United States, specifically related to local weather conditions. Below, you'll find detailed instructions on how to use this dashboard along with some background information to help you make the most informed decision about installing a heat pump.

### What are Heat Pumps?

Heat pumps are introduced as an energy-efficient alternative to traditional heating systems. They essentially function as a reverse air conditioner, working by transferring heat from the outside environment into our houses during colder months and does the opposite during warmer months. As opposed to traditional heating systems that generate heat, heat pumps work on transferring existing heat, which significantly reduces energy consumption.

### Relation between Local Weather and Heat Pump Efficiency

The efficiency of heat pumps can vary with local weather conditions, especially in extreme temperatures. This dashboard utilizes historical weather data, sourced from Open-Meteo's Historical Weather API, to analyze the minimum daily temperatures and predict how well a heat pump would perform in a given location. This feature is especially beneficial for regions with fluctuating or extreme weather patterns.

### Instructions to use the Dashboard

1. **Selecting Your Location**:
   - Start by choosing your city and state from the interactive map or the dropdown menu. This will be the basis for gathering local weather data.

2. **Setting the Date Range**:
   - Input your desired date range for historical weather data analysis. The default range is set from January 1, 2022, to January 1, 2024.

3. **Choosing Temperature Units**:
   - Select your preferred temperature units - Fahrenheit or Celsius. The dashboard will automatically adjust all temperature data accordingly.

4. **Temperature and Range Input**:
   - Use the temperature slider to set a specific temperature for analysis or a temperature range for a more comprehensive overview. The default setting is 5°F, with a range from -15°F to 50°F.

5. **Rolling Averages**:
   - Optionally, you can add weekly or monthly rolling averages to smooth out short-term fluctuations and see broader trends.

6. **Interpreting the Data**:
   - The dashboard will display a plot and a table based on your inputs, showing historical minimum daily temperatures and the proportion of days below your selected temperature threshold.

7. **Forecasting Feature**:
   - You can use the forecasting feature to predict future temperature trends. Enter the number of years for forecasting and select the trend type (flat or linear).

### Citatations:

**Data Sources**

1. **Open-Meteo Historical Weather API**: 
   - This API provides historical weather data essential for analyzing the efficiency of heat pumps in different locations.
   - Website: [Open-Meteo](https://open-meteo.com/)

2. **SimpleMaps - U.S. Cities Database**:
   - This database offers comprehensive location data for U.S. cities, including city-state combinations, latitude, and longitude.
   - Website: [SimpleMaps](https://simplemaps.com/data/us-cities)

**Python Frameworks and Libraries**

1. **Shiny for Python**:
   - A framework used for building interactive web applications entirely in Python, suitable for creating the user interface of the dashboard.
   - Website: [Shiny Python](https://shiny.rstudio.com/py/)

2. **ipywidgets**:
   - Provides interactive HTML widgets for Python kernel.
   - Website: [ipywidgets](https://ipywidgets.readthedocs.io/en/latest/)

4. **ipyleaflet**:
   - Helps in enabling interactive maps.
   - Website: [ipyleaflet](https://ipyleaflet.readthedocs.io/)

5. **Prophet: Forecasting at Scale (For DDG students)**:
   - A tool for producing high-quality forecasts for time series data that has multiple seasonality with linear or non-linear growth.
   - Website: [Prophet](https://facebook.github.io/prophet/)


### Acknowledgements

This dashboard was developed as part of the CS 498 course taught by Professor David Dalpiaz.

 """)))),
        
        title= "Daily Heat Pump Efficiency Counter", 
    )

cache_session = requests_cache.CachedSession('.cache', expire_after = -1) # Reference for Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

url = "https://archive-api.open-meteo.com/v1/archive"

def server(input: Inputs, output: Outputs, session: Session): # Reference for Server Side programming: https://rstudio.github.io/cheatsheets/html/shiny-python.html
    @reactive.Effect
    @reactive.event(input.radio2)
    def _():
        range_type = input.radio2()
        if range_type == "1":
            ui.update_slider("slider1", min=-15, max=50, value=5)
        else:
            ui.update_slider("slider1", min=-25, max=10, value=-15)

    @reactive.Effect
    @reactive.event(input.radio2)
    def _():
        range_type = input.radio2()
        if range_type == "1":
            ui.update_slider("slider2", min=-25, max=65, value=[0, 15])
        else:
            ui.update_slider("slider2", min=-30, max=15, value=[-20, -10])


    @reactive.calc
    def get_weather_data(): # Reference for Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api 
        city = input.city().split(',')[0].strip()
        state_name = input.city().split(',')[1].strip()
        filtered_cities = cities[(cities['city'] == city) & (cities['state_name'] == state_name)]
        latitude = filtered_cities['lat'].values[0]
        longitude = filtered_cities['lng'].values[0]
        start_date = input.daterange()[0]
        end_date = input.daterange()[1]
        temperature_unit = "fahrenheit" if input.radio2() == "1" else "celsius"

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_min",
            "temperature_unit": temperature_unit
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        daily = response.Daily()
        daily_temperature_2m_min = daily.Variables(0).ValuesAsNumpy()

        daily_data = {"date": pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        )}
        daily_data["temperature_2m_min"] = daily_temperature_2m_min
        daily_dataframe = pd.DataFrame(data = daily_data)
        x=[daily_dataframe['date']]
        y=[daily_dataframe['temperature_2m_min']]

        return x, y, daily_dataframe, response

    @render.text
    def value():
        x, y, daily_dataframe, response = get_weather_data()
        return '{:.4f}°N , {:.4f}°E'.format(response.Latitude(), response.Longitude())

    @render.plot
    def prop():
        x, y, daily_dataframe, response = get_weather_data()

        df=pd.DataFrame()
        df['y']=daily_dataframe['temperature_2m_min']
        df['ds'] = pd.to_datetime(daily_dataframe['date']).dt.date
        if(input.radio1()=="1"):  # Refernce for Prophet Model Fitting: https://facebook.github.io/prophet/
            m = Prophet(growth='flat')
        else:
            m = Prophet(growth='linear')
        m.fit(df)
        future = m.make_future_dataframe(periods=365*input.numeric())
        forecast = m.predict(future).tail(365*input.numeric())
        fig1 = m.plot(forecast)
        plt.axhline(y=input.slider1(), color='darkgrey')
        
        if "1" in input.radio2():
            plt.ylabel('Daily Minimum Temperature °F')
            plt.xlabel('')
        else:
            plt.ylabel('Daily Minimum Temperature °C')
            plt.xlabel('')
        return fig1

    @render.data_frame
    def table2():
        x, y, daily_dataframe, response = get_weather_data()

        df=pd.DataFrame()
        df['y']=daily_dataframe['temperature_2m_min']
        df['ds'] = pd.to_datetime(daily_dataframe['date']).dt.date
        if(input.radio1()=="1"):
            m = Prophet(interval_width=0.95,growth='flat')
        else:
            m = Prophet(interval_width=0.95,growth='linear')
        m.fit(df)
        future = m.make_future_dataframe(periods=365*input.numeric())
        forecast = m.predict(future).tail(365*input.numeric())
        c1=[]
        c2=[]
        c3=[]  

        for i in range(input.slider2()[1], input.slider2()[0]-1, -1):
            c1.append(i)
            days_below_temp = len(forecast[forecast['yhat_lower'] < i])
            c2.append(days_below_temp)
            proportion_below_temp = round(days_below_temp / forecast.shape[0],3)
            c3.append(proportion_below_temp)

        table_dataframe = pd.DataFrame({
            'Temp': c1,
            'Days Below': c2,
            'Proportion Below': c3
        })

        return render.DataGrid(table_dataframe,width=1450)
    
    @render.plot
    def graph():
        x, y, daily_dataframe, response = get_weather_data() 
        daily_dataframe['date']=pd.to_datetime(daily_dataframe['date']).dt.date
        plot = (
            ggplot(daily_dataframe, aes(x='date', y='temperature_2m_min')) +
            geom_point() +
            theme_bw() +     
            scale_x_date(date_breaks='3 month', date_labels='%Y-%m')
        )

        if "a" in input.checkbox_group():
            weekly_rolling_avg = daily_dataframe['temperature_2m_min'].rolling(7).mean() # Reference for calculating rolling averages: https://www.geeksforgeeks.org/how-to-calculate-moving-averages-in-python/
            plot += geom_line(aes(y=weekly_rolling_avg), color='orange', linetype='solid')
            

        if "b" in input.checkbox_group():
            monthly_rolling_avg = daily_dataframe['temperature_2m_min'].rolling(30).mean() # Reference for calculating rolling averages: https://www.geeksforgeeks.org/how-to-calculate-moving-averages-in-python/
            plot += geom_line(aes(y=monthly_rolling_avg), color='blue', linetype='solid')
        
        plot_temp = input.slider1()
        plot += geom_hline(yintercept=plot_temp, color='lightgrey')
        plot += geom_point(data=daily_dataframe[daily_dataframe['temperature_2m_min'] < plot_temp], fill="gainsboro", color="gainsboro")
        
        if "1" in input.radio2():
            plot += labs(x='', y='Daily Minimum Temperature °F')
        else:
            plot += labs(x='', y='Daily Minimum Temperature °C')
        
        plot += scale_y_continuous(limits=[daily_dataframe['temperature_2m_min'].min() - 5, daily_dataframe['temperature_2m_min'].max() + 10])

        return plot


    @render_widget  
    def map():
        x, y, daily_dataframe, response = get_weather_data()

        map = Map(center=(response.Latitude(), response.Longitude()), zoom=12)
        marker = Marker(location=(response.Latitude(), response.Longitude()))
        map.add_layer(marker)
        return map


    @render.data_frame
    def table():
        x, y, daily_dataframe, response = get_weather_data()

        c1=[]
        c2=[]
        c3=[]

        for i in range(input.slider2()[1], input.slider2()[0]-1, -1):
            c1.append(i)
            days_below_temp = len(daily_dataframe[daily_dataframe['temperature_2m_min'] < i])
            c2.append(days_below_temp)
            proportion_below_temp = round(days_below_temp / daily_dataframe.shape[0],3)
            c3.append(proportion_below_temp)

        table_dataframe = pd.DataFrame({
            'Temp': c1,
            'Days Below': c2,
            'Proportion Below': c3
        })

        return render.DataGrid(table_dataframe,width=1450)
    
app = App(app_ui, server)
