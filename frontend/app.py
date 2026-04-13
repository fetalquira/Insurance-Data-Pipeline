import streamlit as st
import requests
import os
from datetime import date
from enum import Enum, StrEnum


# Lists used in backend; decoupled for now, future development can follow DRY principle
class Honorific(StrEnum):
    MR = "Mr."
    MRS = "Mrs."
    MS = "Ms."
    DR = "Dr."
    PROF = "Prof."
    REV = "Rev."
    HON = "Hon."
    ENGR = "Engr."
    AR = "Ar."

class PhRegion(StrEnum):
    # LUZON
    NCR = "National Capital Region (NCR)"
    CAR = "Cordillera Administrative Region (CAR)"
    R1 = "Region I (Ilocos Region)"
    R2 = "Region II (Cagayan Valley)"
    R3 = "Region III (Central Luzon)"
    R4A = "Region IV-A (CALABARZON)"
    MIMAROPA = "MIMAROPA Region"
    R5 = "Region V (Bicol Region)"
    
    # VISAYAS
    R6 = "Region VI (Western Visayas)"
    NIR = "Negros Island Region (NIR)"
    R7 = "Region VII (Central Visayas)"
    R8 = "Region VIII (Eastern Visayas)"
    
    # MINDANAO
    R9 = "Region IX (Zamboanga Peninsula)"
    R10 = "Region X (Northern Mindanao)"
    R11 = "Region XI (Davao Region)"
    R12 = "Region XII (SOCCSKSARGEN)"
    CARAGA = "Region XIII (Caraga)"
    BARMM = "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)"

class IncomeSource(StrEnum):
    SALARY = "Salary"
    BUSINESS = "Business"
    PROFESSIONAL_FEES = "Professional Fees"
    SAVINGS_INVESTMENTS = "Savings/Investments"
    SALES_COMMISSIONS = "Sales Commissions"
    SEAFARER_ALLOTMENT = "Allotment from Seafarer"
    ABROAD_REMITTANCE = "Remittance from Abroad"

class MonthlyIncomeRange(StrEnum):
    UNDER_10K = "Under ₱10,000"
    RANGE_10K_25K = "₱10,000 - ₱25,000"
    RANGE_25K_50K = "₱25,000 - ₱50,000"
    RANGE_50K_100K = "₱50,000 - ₱100,000"
    RANGE_100K_200K = "₱100,000 - ₱200,000"
    RANGE_200K_500K = "₱200,000 - ₱500,000"
    RANGE_500K_1M = "₱500,000 - ₱1,000,000"
    OVER_1M = "Over ₱1,000,000"

PRODUCT_CATALOG = {
    "Fortis Pure Life": {"type": "term_life", "code": "HTC-TLIF-001"},
    "Nexus Wealth": {"type": "variable_life", "code": "HTC-VULF-001"}
}

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
        honorific = st.selectbox("Honorific", options=list(Honorific), format_func=lambda honorific: honorific.value) # To be replaced with an enum class
        first_name = st.text_input("First Name", value="Bruce")
        last_name = st.text_input("Last Name", value="Wayne")
    with col2:
        middle_name = st.text_input("Middle Name")
        gender = st.selectbox("Gender", ["Male", "Female"])
        civil_status = st.selectbox("Civil Status", ["Single", "Married", "Widowed", "Separated"])
    with col3:
        birthdate = st.date_input("Birthdate", value=date(1990, 1, 1))
        place_of_birth = st.text_input("Place of Birth")
        mother_maiden_name = st.text_input("Mother's Maiden Name")

    st.subheader("Citizenship & Residency")
    col4, col5, col6 = st.columns(3)
    with col4:
        country_of_citizenship = st.text_input("Country of Citizenship", value="PHL")
    with col5:
        us_resident = st.checkbox("US Resident", value=False)
    with col6:
        us_passport = st.checkbox("Has a US Passport", value=False)

with tab2:
    st.subheader("Address")
    street_address = st.text_input("Street Address")
    col1, col2 = st.columns(2)
    with col1:
        barangay = st.text_input("Barangay")
    with col2:
        city = st.text_input("City")
    col3, col4 = st.columns(2)
    with col3:
        region = st.selectbox(
            "Region",
            options=list(PhRegion),
            format_func=lambda region: region.value
        )
    with col4:
        zip_code = st.text_input("Zip Code", value="1000")

    st.subheader("Contact Numbers & Email")
    col5, col6, col7 = st.columns(3)
    with col5:
        email = st.text_input("Email Address", value="applicant@example.com")
    with col6:
        mobile_number = st.text_input("Mobile Number", value="+639171234567")
    with col7:
        landline_number = st.text_input("Landline Number", value="+63281234567")

with tab3:
    st.subheader("Employment & Income")
    col1, col2 = st.columns(2)
    with col1:
        occupation = st.text_input("Occupation")
        company_name = st.text_input("Company Name")
        source_of_income = st.selectbox(
            "Source of Income",
            options=list(IncomeSource),
            format_func=lambda incomesource: incomesource.value
        )
    with col2:
        monthly_income = st.selectbox(
            "Monthly Income Range",
            options=list(MonthlyIncomeRange),
            format_func=lambda monthlyincomerange: monthlyincomerange.value
        )
        annual_income = st.number_input("Exact Annual Income (PHP)", min_value=0, value=1000000, step=50000)
        tin = st.text_input("Tax Identification Number (TIN)", value="000000000")

with tab4:
    st.subheader("Product Details")
    col1, col2, col3 = st.columns(3)
    with col1:
        product_name = st.selectbox("Product Name", list(PRODUCT_CATALOG.keys()))
    with col2:
        product_type = st.text_input("Product Type", value=PRODUCT_CATALOG[product_name]["type"], disabled=True)
    with col3:
        product_code = st.text_input("Product Code", value=PRODUCT_CATALOG[product_name]["code"], disabled=True)

    st.subheader("Client Benefits")
    # We ask the user to pick one path, ensuring we never send both values to the API.
    quote_basis = st.radio(
        "How would you like to calculate the quote?", 
        ["Based on Target Coverage", "Based on Monthly Budget"]
    )

    if quote_basis == "Based on Target Coverage":
        requested_coverage = st.number_input("Requested Coverage Amount", min_value=100000, value=5000000, step=100000)
        target_monthly_premium = None # Explicitly setting to None per your backend rule
    else:
        requested_coverage = None # Explicitly setting to None per your backend rule
        target_monthly_premium = st.number_input("Target Monthly Premium", min_value=1000, value=5000, step=500)

    st.divider()

    # --- 3. API Integration & Execution ---
    if st.button("🚀 Generate Quote", type="primary", use_container_width=True):
        
        # 1. Map the UI variables directly to your JSON Payload structure
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "middle_name": middle_name,
            "gender": gender,
            "honorific": honorific,
            "civil_status": civil_status,
            "birthdate": birthdate.isoformat(), # Convert date object to YYYY-MM-DD string
            "place_of_birth": place_of_birth,
            "country_of_citizenship": country_of_citizenship,
            "us_resident": us_resident,
            "us_passport": us_passport,
            "tin": tin,
            "street_address": street_address,
            "barangay": barangay,
            "city": city,
            "region": region,
            "zip_code": zip_code,
            "email": email,
            "mobile_number": mobile_number,
            "landline_number": landline_number,
            "occupation": occupation,
            "company_name": company_name,
            "monthly_income": monthly_income,
            "annual_income": annual_income,
            "source_of_income": source_of_income,
            "mother_maiden_name": mother_maiden_name,
            "requested_coverage": requested_coverage,
            "target_monthly_premium": target_monthly_premium,
            "product_name": product_name,
            "product_type": product_type,
            "product_code": product_code
        }

        # 2. Configure your Bouncer credentials
        # BEST PRACTICE: Pull these from .streamlit/secrets.toml
        try:
            API_URL = os.getenv("AWS_API_GATEWAY") or st.secrets["AWS_API_GATEWAY"]
            API_KEY = os.getenv("SECRET_API_KEY") or st.secrets["SECRET_API_KEY"]
        except Exception:
            # Fallback for testing if secrets aren't set up yet
            st.warning("⚠️ Secrets not found. Using hardcoded variables for testing.")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": API_KEY
        }

        # 3. Fire the request and handle the response
        with st.spinner("Calculating via HiltimCheeseInsurance Engine..."):
            try:
                response = requests.post(API_URL + "/submit-quote", json=payload, headers=headers)
                
                if response.status_code == 200:
                    st.success("Quote Generated Successfully!")
                    
                    # Display the raw JSON response beautifully
                    st.json(response.json())
                    
                    # Optional: Extract specific values to show prominently
                    # result_data = response.json()
                    # st.metric(label="Calculated Premium", value=f"₱ {result_data.get('calculated_premium', 0):,.2f}")
                    
                elif response.status_code == 422:
                    st.error("Validation Error: The data provided didn't match the backend rules.")
                    st.json(response.json())
                elif response.status_code in [401, 403]:
                    st.error("Security Error: The Bouncer rejected your API Key.")
                else:
                    st.error(f"Server Error {response.status_code}")
                    st.write(response.text)
                    
            except requests.exceptions.RequestException as e:
                st.error("Critical Error: Could not connect to AWS.")
                st.exception(e)