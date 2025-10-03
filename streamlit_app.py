# If user selects ingredients
if ingredients_list:
    ingredients_string = ' '.join(ingredients_list).strip()
    ingredients_escaped = ingredients_string.replace("'", "''")
    
    # Show subheader for selected fruits
    st.subheader("Nutrient Information for Your Selected Fruit(s):")
    st.write(", ".join(ingredients_list))
    
    # Filter API data for selected fruits (assuming API returns list of dicts)
    api_data = smoothiefroot_response.json()
    selected_nutrients = [fruit for fruit in api_data if fruit['name'].lower() in [i.lower() for i in ingredients_list]]
    
    if selected_nutrients:
        st.dataframe(selected_nutrients, use_container_width=True)
    else:
        st.info("Nutrient information for selected fruits not available in API.")
    
    # Prepare SQL insert statement
    my_insert_stmt = (
        "INSERT INTO smoothies.public.orders (ingredients, name_on_order) "
        f"VALUES ('{ingredients_escaped}', '{name_escaped}');"
    )
    
    # Submit order button
    if st.button('Submit Order'):
        session.sql(my_insert_stmt).collect()
        st.success(f"✅ Your Smoothie is ordered, {name_on_order}!")
