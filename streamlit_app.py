# Import python packages
import streamlit as st
from snowflake.snowpark.functions import col
import requests
import urllib.parse

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
    search_map = {
        r['FRUIT_NAME']: (r.get('SEARCH_ON') if r.get('SEARCH_ON') else r['FRUIT_NAME'])
        for r in rows
    }
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

# helper: produce simple singular form(s)
def simple_singular_variants(term: str):
    variants = []
    if not term:
        return variants
    t = term.strip()
    variants.append(t)
    # lowercase and stripped punctuation
    variants.append(t.lower())
    # singular heuristics
    if t.lower().endswith("ies"):
        variants.append(t[:-3] + "y")           # berries -> berry
        variants.append((t[:-3] + "y").lower())
    if t.lower().endswith("es") and not t.lower().endswith("ses"):
        variants.append(t[:-2])                 # peaches -> peach
        variants.append(t[:-2].lower())
    if t.lower().endswith("s"):
        variants.append(t[:-1])                 # apples -> apple
        variants.append(t[:-1].lower())
    # de-duplicate while preserving order
    seen = set()
    dedup = []
    for v in variants:
        if v and v not in seen:
            dedup.append(v)
            seen.add(v)
    return dedup

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
        search_term_from_db = search_map.get(ingredient, ingredient)

        # Build candidate search terms to try (prefer SEARCH_ON first)
        candidates = []
        # If SEARCH_ON exists and is not identical to displayed name, try it first
        if search_term_from_db and search_term_from_db != ingredi
