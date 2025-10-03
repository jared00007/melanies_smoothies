# Import python packages
import re
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

# improved candidate generator for API search terms
def build_search_candidates(term: str):
    """
    Return a list of candidate search tokens to try against the API,
    ordered from most-preferred to least.
    """
    if not term:
        return []

    t = term.strip()

    # base variants
    variants = []
    variants.append(t)                       # original with case
    variants.append(t.lower())               # lowercase
    # common space-handling
    variants.append(t.replace(" ", ""))      # remove spaces -> dragonfruit
    variants.append(t.replace(" ", "-"))     # hyphen -> dragon-fruit
    variants.append(t.replace(" ", "_"))     # underscore -> dragon_fruit
    variants.append(t.lower().replace(" ", ""))   # lowercase compact
    variants.append(t.lower().replace(" ", "-"))  # lowercase hyphen
    variants.append(t.lower().replace(" ", "_"))  # lowercase underscore

    # punctuation-stripped compact form (letters+numbers only)
    compact = re.sub(r'[^A-Za-z0-9]', '', t)
    if compact:
        variants.append(compact)
        variants.append(compact.lower())

    # also try title-cased compact (e.g., DragonFruit)
    title_compact = ''.join(word.capitalize() for word in re.split(r'\s+', t))
    if title_compact:
        variants.append(title_compact)

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
        if search_term_from_db and search_term_from_db != ingredient:
            candidates.extend(build_search_candidates(search_term_from_db))
        # Always try variants of the displayed ingredient name as well
        candidates.extend(build_search_candidates(ingredient))

        # Ensure uniqueness in order
        seen = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        # Try API calls in order of candidates until success
        success = False
        last_resp_text = None
        for candidate in candidates:
            safe_candidate = urllib.parse.quote(candidate, safe='')
            api_url = f"https://my.smoothiefroot.com/api/fruit/{safe_candidate}"
            try:
                resp = requests.get(api_url, timeout=8)
            except requests.RequestException as e:
                last_resp_text = f"Request error for {api_url}: {e}"
                continue

            if resp.status_code == 200:
                last_resp_text = resp.text
                # Display as dataframe if possible
                try:
                    st.dataframe(data=resp.json(), use_container_width=True)
                except Exception:
                    st.text(resp.text)
                success = True
                break
            else:
                # remember last response for debug and keep trying next candidate
                last_resp_text = f"API returned status {resp.status_code} for {api_url}"

        if not success:
            st.warning(f"Nutrient info not found for '{ingredient}'. Tried: {', '.join(candidates)}.")
            st.info("If the SEARCH_ON value should be different, update the SEARCH_ON column for this fruit in Snowflake.")
            if last_resp_text:
                st.text(f"Last attempt: {last_resp_text}")

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
