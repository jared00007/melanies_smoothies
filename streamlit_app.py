# --- paste this block in place of the current per-fruit API lookup loop ---

import urllib.parse

# extra candidates to try for tricky fruits like "Cantaloupe"
EXTRA_SYNONYMS = {
    "cantaloupe": ["canteloupe", "cantaloup", "muskmelon", "melon", "cantalope"],  # muskmelon / melon often used
    "dragon fruit": ["dragonfruit", "dragon-fruit", "dragon_fruit"],
    # add other manual synonyms you suspect here
}

if ingredients_list:
    ingredient_notes = {}
    for idx, ingredient in enumerate(ingredients_list, start=1):
        st.subheader(f"{idx}. {ingredient}")
        note = st.text_input(f"Notes or customizations for {ingredient} (optional):", key=f"note_{ingredient}_{idx}")
        ingredient_notes[ingredient] = note

        # prefer SEARCH_ON from DB if present
        search_term_from_db = search_map.get(ingredient, ingredient)

        # Build primary candidates (existing logic)
        candidates = []
        if search_term_from_db and search_term_from_db != ingredient:
            candidates.extend(build_search_candidates(search_term_from_db))
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
            safe_candidate = urllib.parse.quote(candidate, safe='')
            api_url = f"https://my.smoothiefroot.com/api/fruit/{safe_candidate}"
            try:
                resp = requests.get(api_url, timeout=8)
            except requests.RequestException as e:
                tried_results.append((candidate, "error", str(e)))
                continue

            # log the status and a short sample of response for debugging
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
            # show the results table so you can inspect (status + short text)
            for cand, status, sample in tried_results:
                st.text(f"{cand}  →  {status}  {' — ' + sample if sample else ''}")

        # If there *is* a working candidate, offer to save it to Snowflake
        if working_candidate:
            if st.button(f"Use '{working_candidate}' as SEARCH_ON for '{ingredient}'", key=f"save_{ingredient}_{idx}"):
                # caution: requires write privileges
                update_sql = (
                    "UPDATE smoothies.public.fruit_options "
                    f"SET SEARCH_ON = '{working_candidate.replace(\"'\", \"''\")}' "
                    f"WHERE FRUIT_NAME = '{ingredient.replace(\"'\", \"''")}';"
                )
                try:
                    session.sql(update_sql).collect()
                    st.success(f"Saved SEARCH_ON = '{working_candidate}' for '{ingredient}' in Snowflake.")
                    # update local mapping so further runs in this session use it
                    search_map[ingredient] = working_candidate
                except Exception as e:
                    st.error(f"Failed to update Snowflake: {e}")

# --- end block ---
