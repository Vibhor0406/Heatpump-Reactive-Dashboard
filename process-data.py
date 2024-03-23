import pandas as pd
import matplotlib.pyplot as plt

# Read the CSV file into a pandas DataFrame
cities = pd.read_csv('data-raw/uscities.csv')
cities[['city','city_ascii','state_name','lat','lng']].to_csv('data/cities.csv',index=False) 
