import os
import psycopg2
import ssl
import streamlit as st
from streamlit.web import cli as stcli

# SSL Context for RDS
ssl_context = ssl.create_default_context()
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.load_verify_locations(cafile='global-bundle.pem')  # Download from AWS RDS

def create_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT'),
        sslmode='require',
        sslrootcert='global-bundle.pem'
    )

def main():
    st.title("App Dashboard")
    try:
        conn = create_db_connection()
        st.success("✅ Database connected!")
        conn.close()
    except Exception as e:
        st.error(f"❌ Database error: {str(e)}")

if __name__ == "__main__":
    if os.getenv('AWS_EXECUTION_ENV'):
        sys.argv = [
            "streamlit", "run",
            os.path.abspath(__file__),
            "--server.port=8080",
            "--server.address=0.0.0.0",
            "--server.headless=true"
        ]
        sys.exit(stcli.main())
    else:
        main()


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
