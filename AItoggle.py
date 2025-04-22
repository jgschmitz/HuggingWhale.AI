import streamlit as st

# 🧠 Title
st.title("🧠 HuggingWhale Agent Chat")

# 🐳 Prompt input
prompt = st.text_area("Enter your prompt", height=150)

# ⚙️ LLM selector
llm_choice = st.radio("Choose your LLM", ["OpenAI", "Voyage"], horizontal=True)

# 🐬 Submit button
if st.button("Send"):
    with st.spinner("Thinking..."):
        if llm_choice == "OpenAI":
            response = call_openai(prompt)
        else:
            response = call_voyage(prompt)

        st.markdown(f"**{llm_choice} says:**")
        st.write(response)
