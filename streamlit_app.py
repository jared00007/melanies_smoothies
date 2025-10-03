# Import python packages
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

# improved candidate generator for API search terms (includes pluralization)
def build_search_candidates(term: str):
    if not term:
        return []

    t = term.strip()
    variants = []

    # basic variants
    variants.append(t)                       
    variants.append(t.lower())
    variants.append(t.replace(" ", ""))      
    variants.append(t.replace(" ", "-"))     
    variants.append(t.replace(" ", "_"))     
    variants.append(t.lower().replace(" ", ""))
    variants.append(t.lower().replace(" ", "-"))
    variants.append(t.lower().replace(" ", "_"))

    # punctuation-stripped compact form (letters+numbers only)
    compact = re.sub(r'[^A-Za-z0-9]', '', t)
    if compact:
        variants.append(compact)
        variants.append(compact.lower())

    # title-cased compact
    title_compact = ''.join(word.capitalize() for word in re.split(r'\s+', t))
    if title_compact:
        variants.append(title_compact)

    # pluralization
    lower_t = t.lower()
    if not lower_t.endswith('s'):
        variants.append(t + 's')
        variants.append(lower_t + 's')
        if lower_t.endswith('y') and len(lower_t) > 1:
            variants.append(t[:-1] + 'ies')
            variants.append(lower_t[:-1] + 'ies')
    else:
        variants.append(t[:-1])
        variants.append(lower_t[:-1])
        if lower_t.endswith('ies'):
            variants.append(t[:-3] + 'y')
            variants.append(lower_t[:-3] + 'y')

    if compact:
        if not compact.lower().endswith('s'):
            variants.append(compact + 's')
            variants.append(compact.lower() + 's')
        else:
            variants.append(compact[:-1])
            variants.append(compact.lower()[:-1])

    # de-duplicate
    seen = set()
    dedup = []
    for v in variants:
        if v and v not in seen:
            dedup.append(v)
            seen.add(v)
    return dedup

# If user selects ingredients
if ingredients_list:
    ingredient_notes = {}
    for idx, ingredient in enumerate(ingredients_list, start=1):
        st.subheader(f"{idx}. {ingredient}")  

        # input box for notes
        note = st.text_input(f"Notes or customizations for {ingredient} (optional):", key=f"note_{ingredient}_{idx}")
        ingredient_notes[ingredient] = note

        # determine search term
        search_term_from_db = search_map.get(ingredient, ingredient)

        # Build candidate search terms
        candidates = []
        if search_term_from_db and search_term_from_db != ingredient:
            candidates.extend(build_search_candidates(search_term_from_db))
        candidates.extend(build_search_candidates(ingredient))

        # deduplicate
        seen = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        # Try API calls
        tried_results = []
        success = False
        working_candidate = None
        last_resp_text = None

        for candidate in candidates:
            safe_candidate = candidate.replace(" ", "%20")
            api_url = f"https://my.smoothiefroot.com/api/fruit/{safe_candidate}"
            try:
                resp = requests.get(api_url, timeout=8)
            except requests.RequestException as e:
                tried_results.append((candidate, "error", str(e)[:200]))
                last_resp_text = f"Request error for {api_url}: {e}"
                continue

            sample = resp.text[:200] if resp.text else ""
            tried_results.append((candidate, resp.status_code, sample))

            if resp.status_code == 200:
                try:
                    st.dataframe(data=resp.json(), use_container_width=True)
                except Exception:
                    st.text(resp.text)
                success = True
                working_candidate = candidate
                last_resp_text = resp.text
                break
            else:
                last_resp_text = f"API returned status {resp.status_code} for {api_url}"

        if not success:
            st.warning(f"Nutrient info not found for '{ingredient}'. Tried: {', '.join(candidates)}.")
            st.info("If the SEARCH_ON value should be different, update the SEARCH_ON column for this fruit in Snowflake.")
            if last_resp_text:
                st.text(f"Last attempt: {last_resp_text}")

            # Blueberry helper
            if ingredient.lower().startswith('blueber'):
                if st.button("Set SEARCH_ON = 'Blueberries' for this Blueberry row", key=f"set_blueberries_{idx}"):
                    safe_token_for_sql = "Blueberries".replace("'", "''")
                    safe_fruit_for_sql = ingredient.replace("'", "''")
                    update_sql = (
                        "UPDATE smoothies.public.fruit_options "
                        f"SET SEARCH_ON = '{safe_token_for_sql}' "
                        f"WHERE FRUIT_NAME = '{safe_fruit_for_sql}';"
                    )
                    try:
                        session.sql(update_sql).collect()
                        st.success("Saved SEARCH_ON = 'Blueberries' for this Blueberry row in Snowflake.")
                        search_map[ingredient] = "Blueberries"
                    except Exception as e:
                        st.error(f"Failed to update Snowflake: {e}")

            # Ximenia helper
            if ingredient.lower() == 'ximenia':
                if st.button("Set SEARCH_ON = 'ximenia' for this Ximenia row", key=f"set_ximenia_{idx}"):
                    safe_token_for_sql = "ximenia".replace("'", "''")
                    safe_fruit_for_sql = ingredient.replace("'", "''")
                    update_sql = (
                        "UPDATE smoothies.public.fruit_options "
                        f"SET SEARCH_ON = '{safe_token_for_sql}' "
                        f"WHERE FRUIT_NAME = '{safe_fruit_for_sql}';"
                    )
                    try:
                        session.sql(update_sql).collect()
                        st.success("Saved SEARCH_ON = 'ximenia' for this Ximenia row in Snowflake.")
                        search_map[ingredient] = "ximenia"
                    except Exception as e:
                        st.error(f"Failed to update Snowflake: {e}")

            # show tried candidates for debug
            for cand, status, sample in tried_results:
                st.text(f"{cand}  →  {status}  {' — ' + sample if sample else ''}")

        # Save working candidate if API succeeded
        if working_candidate:
            if st.button(f"Use '{working_candidate}' as SEARCH_ON for '{ingredient}'", key=f"save_{ingredient}_{idx}"):
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
                    search_map[ingredient] = working_candidate
                except Exception as e:
                    st.error(f"Failed to update Snowflake: {e}")

    # Prepare SQL insert
    ingredients_string = ' '.join(ingredients_list).strip()
    ingredients_escaped = ingredients_string.replace("'", "''")

    my_insert_stmt = (
        "INSERT INTO smoothies.public.orders (ingredients, name_on_order) "
        f"VALUES ('{ingredients_escaped}', '{name_escaped}');"
    )

    # Submit order
    if st.button('Submit Order'):
        session.sql(my_insert_stmt).collect()
        st.success(f"✅ Your Smoothie is ordered, {name_on_order}!")
