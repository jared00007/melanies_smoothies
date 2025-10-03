# streamlit_app.py
import re
import streamlit as st
from snowflake.snowpark.functions import col
import requests

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

# improved candidate generator for API search terms (no urllib.parse)
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

    # title-cased compact (e.g., DragonFruit)
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

# Extra synonyms for known tricky fruits (you can extend this)
EXTRA_SYNONYMS = {
    "cantaloupe": ["muskmelon", "canteloupe", "cantalope", "melon"],
    "dragon fruit": ["dragonfruit", "dragon-fruit", "dragon_fruit"],
    # add other manual synonyms here if you discover them
}

# If user selects ingredients
if ingredients_list:
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

        # Add hand-tuned synonyms/alternatives for known tricky fruits
        key_lower = ingredient.lower()
        for syn in EXTRA_SYNONYMS.get(key_lower, []):
            candidates.append(syn)

        # dedupe preserving order
        seen = set(); dedup = []
        for c in candidates:
            if c and c not in seen:
                dedup.append(c); seen.add(c)
        candidates = dedup

        # Try API calls in order and collect results for display
        tried_results = []  # tuples of (candidate, status_code, text_sample)
        success = False
        working_candidate = None
        for candidate in candidates:
            # Simple safe transform: replace spaces with %20 (no urllib.parse import)
            safe_candidate = candidate.replace(" ", "%20")
            api_url = f"https://my.smoothiefroot.com/api/fruit/{safe_candidate}"

            try:
                resp = requests.get(api_url, timeout=8)
            except requests.RequestException as e:
                tried_results.append((candidate, "error", str(e)))
                continue

            sample = resp.text[:200] if resp.text else ""
            tried_results.append((candidate, resp.status_code, sample))

            if resp.status_code == 200:
                # display JSON nicely if possible
                try:
                    st.dataframe(data=resp.json(), use_container_width=True)
                except Exception:
                    st.text(resp.text)
                success = True
                working_candidate = candidate
                break  # stop on first success

        # If none succeeded, show the tried candidates and their statuses
        if not success:
            st.warning(f"Nutrient info not found for '{ingredient}'. Tried: {', '.join(candidates)}.")
            st.info("If you know which token the API expects, set SEARCH_ON in Snowflake or choose a working candidate below.")
            for cand, status, sample in tried_results:
                st.text(f"{cand}  →  {status}  {' — ' + sample if sample else ''}")

        # If there *is* a working candidate, offer to save it to Snowflake
        if working_candidate:
            if st.button(f"Use '{working_candidate}' as SEARCH_ON for '{ingredient}'", key=f"save_{ingredient}_{idx}"):
                # caution: requires write privileges
                safe_token_for_sql = working_candidate.replace("'", "''")
                safe_fruit_for_sql = ingredient.replace("'", "''")
                update_sql = (
                    "UPDATE smoothies.public.fruit_options "
                    f"SET SEARCH_ON = '{safe_token_for_sql}' "
                    f"WHERE FRUIT_NAME = '{safe_fruit_for_sql}';"
                )
                try:
                    session.sql(update_sql).collect()
                    st.success(f"Saved SEARCH_ON = '{working_candidate}' for '{ingredient}' in Snowflake.")
                    # update local mapping so further runs in this session use it
                    search_map[ingredient] = working_candidate
                except Exception as e:
                    st.error(f"Failed to update Snowflake: {e}")

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
