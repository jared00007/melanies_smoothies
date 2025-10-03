# Import python packages
import streamlit as st
from snowflake.snowpark.functions import col
import requests

# Write directly to the app
st.title(f":cup_with_straw: Customize Your Smoothie!:cup_with_straw:")
st.write("""Choose the fruits you want in your custom Smoothie
    """)

name_on_order = st.text_input('Name on Smoothie')
st.write('The name on your Smoothie will be:', name_on_order)

cnx = st.connection("snowflake")
session = cnx.session()

# Fetch fruit names from Snowpark and convert to a plain Python list for Streamlit
rows = session.table("smoothies.public.fruit_options").select(col('fruit_name')).collect()
fruit_options = [r['FRUIT_NAME'] for r in rows]

ingredients_list = st.multiselect(
    'Choose up to 5 ingredients:'
    , fruit_options
    , max_selections=5
    )

if ingredients_list:
    # build ingredients string (trim trailing space)
    ingredients_string = ' '.join(ingredients_list).strip()

    # Escape single quotes for SQL safety (Snowflake uses '' to represent a single quote inside a string)
    ingredients_escaped = ingredients_string.replace("'", "''")
    name_escaped = name_on_order.replace("'", "''")
    smoothiefroot_response = requests.get("https://my.smoothiefroot.com/")
    st.text(smoothiefroot_response.json())
    # Correct INSERT statement: specify both columns and properly quote values
    #my_insert_stmt = (
        #"INSERT INTO smoothies.public.orders (ingredients, name_on_order)"
        #f"VALUES ('{ingredients_escaped}', '{name_escaped}');"
    #)
    time_to_insert = st.button('Submit Order')

    if time_to_insert:
        session.sql(my_insert_stmt).collect()
        st.success(f"✅ Your Smoothie is ordered, {name_on_order}!")
