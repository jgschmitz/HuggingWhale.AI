import streamlit as st

provider = st.selectbox("Choose LLM Provider", ["OpenAI", "Voyage"])
prompt = st.text_area("Your prompt")

if st.button("Submit"):
    if provider == "OpenAI":
        st.write(call_openai(prompt))
    else:
        st.write(call_voyage(prompt))
