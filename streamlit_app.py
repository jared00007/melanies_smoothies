# Import python packages
import streamlit as st
from snowflake.snowpark.functions import col
import requests  # <-- added for API call

st.title(":cup_with_straw: Customize Your Smoothie!:cup_with_straw:")
st.write("Choose the fruits you want in your custom Smoothie")

# User input
name_on_order = st.text_input('Name on Smoothie')
st.write('The name on your Smoothie will be:', name_on_order)

# Escape name for SQL
name_escaped = name_on_order.replace("'", "''")

# Use your existing Snowflake connection from requirements.txt config
cnx = st.connection("snowflake")
session = cnx.session()

# Fetch fruit options from Snowflake (and SEARCH_ON if available)
try:
    rows = session.table("smoothies.public.fruit_options").select(col('FRUIT_NAME'), col('SEARCH_ON')).collect()
    # build mapping FRUIT_NAME -> SEARCH_ON (may be None)
    search_map = {r['FRUIT_NAME']: (r.get('SEARCH_ON') if r.get('SEARCH_ON') else r['FRUIT_NAME']) for r in rows}
    fruit_options = [r['FRUIT_NAME'] for r in rows]
except Exception:
    # fallback if SEARCH_ON doesn't exist: just select FRUIT_NAME
    rows = session.table("smoothies.public.fruit_options").select(col('FRUIT_NAME')).collect()
    fruit_options = [r['FRUIT_NAME'] for r in rows]
    search_map = {name: name for name in fruit_options}

# Multiselect input (limit 5 manually)
ingredients_list = st.multiselect('Choose up to 5 ingredients:', fruit_options)

if len(ingredients_list) > 5:
    st.warning("Please select up to 5 ingredients only.")
    ingredients_list = ingredients_list[:5]

# If user selects ingredients
if ingredients_list:
    # show input boxes and API info for each selected fruit
    ingredient_notes = {}
    for idx, ingredient in enumerate(ingredients_list, start=1):
        st.subheader(f"{idx}. {ingredient}")  # subheader for each selection

        # small text input box for each ingredient (unique key)
        note = st.text_input(f"Notes or customizations for {ingredient} (optional):", key=f"note_{ingredient}_{idx}")
        ingredient_notes[ingredient] = note

        # determine search term (SEARCH_ON if present, otherwise fruit name)
        search_term = search_map.get(ingredient, ingredient)
        # call the Smoothiefroot API for this fruit (safe URL building)
        api_url = f"https://my.smoothiefroot.com/api/fruit/{search_term}"
        try:
            resp = requests.get(api_url, timeout=8)
            if resp.status_code == 200:
                # attempt to display JSON as dataframe (if it's a list/dict convertible)
                try:
                    sf_df = st.dataframe(data=resp.json(), use_container_width=True)
                except Exception:
                    # fallback to raw text if it can't be shown as dataframe
                    st.text(resp.text)
            else:
                st.warning(f"API returned status {resp.status_code} for {ingredient} ({api_url})")
        except requests.RequestException as e:
            st.error(f"Failed to fetch nutrient info for {ingredient}: {e}")

    # Prepare SQL insert statement (original behavior)
    ingredients_string = ' '.join(ingredients_list).strip()
    ingredients_escaped = ingredients_string.replace("'", "''")

    my_insert_stmt = (
        "INSERT INTO smoothies.public.orders (ingredients, name_on_order) "
        f"VALUES ('{ingredients_escaped}', '{name_escaped}');"
    )

    # Submit order button
    if st.button('Submit Order'):
        session.sql(my_insert_stmt).collect()
        st.success(f"✅ Your Smoothie is ordered, {name_on_order}!")
