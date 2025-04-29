import os
import streamlit as st
from streamlit.web import cli as stcli

# Debugging header - ALWAYS visible
st.markdown("""
<style>
  .stApp { border: 5px solid #00FF00 !important; background-color: #F9FAFB; }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("My App is Running! 🚀")
    st.write("Basic content loaded successfully")
    
    # Test database connection
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            connect_timeout=3
        )
        st.success("✅ Database connection successful")
        conn.close()
    except Exception as e:
        st.error(f"❌ Database connection failed: {str(e)}")

if __name__ == "__main__":
    if os.getenv('AWS_EXECUTION_ENV'):
        # App Runner specific config
        import sys
        sys.argv = [
            "streamlit", "run",
            os.path.abspath(__file__),
            "--server.port=8080",
            "--server.address=0.0.0.0",
            "--server.headless=true",
            "--server.enableCORS=true",
            "--server.enableXsrfProtection=true"
        ]
        sys.exit(stcli.main())
    else:
        main()
