# Import python packages
import streamlit as st
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col

st.title(":cup_with_straw: Customize Your Smoothie!:cup_with_straw:")
st.write("Choose the fruits you want in your custom Smoothie")

# User input
name_on_order = st.text_input('Name on Smoothie')
st.write('The name on your Smoothie will be:', name_on_order)

# Escape name for SQL
name_escaped = name_on_order.replace("'", "''")

# Snowflake session
# Assumes session is created via environment variables or external config
session = Session.builder.from_env().create()  # Pulls credentials from environment

# Fetch fruit options from Snowflake
rows = session.table("smoothies.public.fruit_options").select(col('FRUIT_NAME')).collect()
fruit_options = [r['FRUIT_NAME'] for r in rows]

# Multiselect input
ingredients_list = st.multiselect('Choose up to 5 ingredients:', fruit_options)

# Enforce selection limit
if len(ingredients_list) > 5:
    st.warning("Please select up to 5 ingredients only.")
    ingredients_list = ingredients_list[:5]

# If user selects ingredients
if ingredients_list:
    ingredients_string = ' '.join(ingredients_list).strip()
    ingredients_escaped = ingredients_string.replace("'", "''")
    
    # Insert into Snowflake
    my_insert_stmt = (
        "INSERT INTO smoothies.public.orders (ingredients, name_on_order) "
        f"VALUES ('{ingredients_escaped}', '{name_escaped}');"
    )
    
    if st.button('Submit Order'):
        session.sql(my_insert_stmt).collect()
        st.success(f"✅ Your Smoothie is ordered, {name_on_order}!")
