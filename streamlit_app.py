# Debug header
st.markdown("""
<style>
  .stApp { border: 5px solid #00FF00 !important; }
</style>
""", unsafe_allow_html=True)

# streamlit_app.py (Minimal Test)
import streamlit as st
st.set_page_config(page_title="Test", layout="wide")
st.title("Test App")
st.write("Minimal app loaded successfully!")
print("DEBUG: Minimal Streamlit app executed fully.")
