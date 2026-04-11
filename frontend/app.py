import streamlit as st
import requests
import os
from datetime import date


# Cloud Variables
API_URL = os.getenv("AWS_API_GATEWAY") or st.secrets["AWS_API_GATEWAY"]
API_KEY = os.getenv("SECRET_API_KEY") or st.secrets["SECRET_API_KEY"]

# UI Branding
st.set_page_config(page_title="HilTim Cheese Insurance", page_icon="🛡️")
st.title("HilTim Cheese Insurance")
st.markdown("Enter client details below to generate a real-time insurance quote.")

# We use tabs to organize the massive payload cleanly
tab1, tab2, tab3, tab4 = st.tabs(["Personal Info", "Contact Details", "Financials", "Quote Configuration"])

with tab1:
    st.subheader("Client Identity")
    col1, col2, col3 = st.columns(3)
    with col1:
        honorific = st.selectbox("Honorific", ["Mr.", "Ms.", "Mrs.", "Dr."]) # To be replaced with an enum class
        first_name = st.text_input("First Name", value="Bruce")
        last_name = st.text_input("Last Name", value="Wayne")
    with col2:
        middle_name = st.text_input("Middle Name")
        gender = st.selectbox("Gender", ["Male", "Female"])
        civil_status = st.selectbox("Civil Status", ["Single", "Married", "Widowed", "Divorced"])
    with col3:
        birthdate = st.date_input("Birthdate", value=date(1990, 1, 1))
        place_of_birth = st.text_input("Place of Birth")
        mother_maiden_name = st.text_input("Mother's Maiden Name")