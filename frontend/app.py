import streamlit as st
import requests
import os


API_URL = os.getenv("AWS_API_GATEWAY")

# UI Branding
st.set_page_config(page_title="HilTim Cheese Insurance", page_icon="🛡️")
st.title("HilTim Cheese Insurance")
st.write("Get an instant quote in seconds!")

st.subheader("1. Your Details")
col1, col2 = st.columns(2)
with col1:
    first_name = st.text_input("First Name")
    middle_name = st.text_input("Middle Name")
    last_name = st.text_input("Last Name")
with col2:
    gender = st.selectbox(
        "Select your gender",
        ["Male", "Female"]
    )
    annual_income = st.number_input("Annual Income ($)", min_value=10000, value=50000, step=5000)
    has_prior_claims = st.checkbox("Have you had prior insurance claims?")