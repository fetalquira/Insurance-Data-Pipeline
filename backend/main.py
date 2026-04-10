from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import phonenumbers
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    BeforeValidator,
    model_validator,
    AfterValidator,
    computed_field,
    EmailStr
)
from typing import (
    Literal,
    Optional,
    Annotated,
    Any,
    ClassVar,
    Union
)
from mangum import Mangum
import boto3
import json
import uuid
import pycountry
from datetime import datetime, date, UTC
from enum import Enum


# 1. Initialize the App
app = FastAPI(title="HilTim Cheese Insurance API")

# Allow our future Streamlit app to talk to this API without being blocked
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows any frontend to connect (we can lock this down later)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Define the Data Contract (Pydantic)
# Validator Functions
def clean_string(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().capitalize()
    return v

def clean_honorifics(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    
    name_map = {
        "mr": "Mr.",
        "mrs": "Mrs.",
        "ms": "Ms.",
        "dr": "Dr.",
        "prof": "Prof.",
        "rev": "Rev.",
        "hon": "Hon.",
        "engr": "Engr.",
        "ar": "Ar."
    }
    lookup = v.strip().lower().replace(".","")
    return name_map.get(lookup, v)

def parse_date_strings(v: Any) -> Any:
    if isinstance(v, str):
        return v.replace("/", "-")
    return v

def min_age_validator(min_age: int):
    def validator(v: date) -> date:
        today = date.today()
        # Calculate age precisely
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        
        if v > today:
            raise ValueError("Birthdate cannot be in the future.")
        if age < min_age:
            raise ValueError(f"Must be at least {min_age} years old for this role.")
        return v
    return validator

def validate_country(v: Any) -> str:
    if not isinstance(v, str):
        return v
    
    lookup = v.strip()
    try:
        country = pycountry.countries.lookup(lookup)
        return country.alpha_3
    except (LookupError, AttributeError):
        raise ValueError(f"'{lookup}' is not a recognized ISO country.")
    
def strip_id_formatting(v: Any) -> Any:
    if isinstance(v, str):
        return v.replace("-", "").replace(" ", "")
    return v

def ensure_lower(v: str) -> str:
    return v.lower().strip()

def validate_phone(v: Any) -> str:
    if not isinstance(v, str):
        return v
    
    try:
        parsed_number = phonenumbers.parse(v, "PH")

        if not phonenumbers.is_valid_number(parsed_number):
            raise ValueError("Invalid phone number format.")
        
        return phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.E164
        )
    except Exception:
        raise ValueError("Could not parse phone number.")

def IsMobile(v: str) -> str:
    parsed = phonenumbers.parse(v)
    if phonenumbers.number_type(parsed) != phonenumbers.PhoneNumberType.MOBILE:
        raise ValueError("Must be a mobile number")
    return v

class PhRegion(str, Enum):
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

# Define Income Enum
class MonthlyIncomeRange(str, Enum):
    UNDER_10K = "Under ₱10,000"
    RANGE_10K_25K = "₱10,000 - ₱25,000"
    RANGE_25K_50K = "₱25,000 - ₱50,000"
    RANGE_50K_100K = "₱50,000 - ₱100,000"
    RANGE_100K_200K = "₱100,000 - ₱200,000"
    RANGE_200K_500K = "₱200,000 - ₱500,000"
    RANGE_500K_1M = "₱500,000 - ₱1,000,000"
    OVER_1M = "Over ₱1,000,000"

    # Map MonthlyIncomeRange Enum to a Numeric Value
    @property
    def min_income_value(self) -> int:
        """Converts the range selection into a conservative numeric floor."""
        mapping = {
            MonthlyIncomeRange.UNDER_10K: 0,
            MonthlyIncomeRange.RANGE_10K_25K: 10000,
            MonthlyIncomeRange.RANGE_25K_50K: 25000,
            MonthlyIncomeRange.RANGE_50K_100K: 50000,
            MonthlyIncomeRange.RANGE_100K_200K: 100000,
            MonthlyIncomeRange.RANGE_200K_500K: 200000,
            MonthlyIncomeRange.RANGE_500K_1M: 500000,
            MonthlyIncomeRange.OVER_1M: 1000000
        }
        return mapping.get(self, 0)
    
class IncomeSource(str, Enum):
    SALARY = "Salary"
    BUSINESS = "Business"
    PROFESSIONAL_FEES = "Professional Fees"
    SAVINGS_INVESTMENTS = "Savings/Investments"
    SALES_COMMISSIONS = "Sales Commissions"
    SEAFARER_ALLOTMENT = "Allotment from Seafarer"
    ABROAD_REMITTANCE = "Remittance from Abroad"

# Annotations for Reusability
NameString = Annotated[str, Field(..., min_length=2, max_length=100)]
Gender = Annotated[
    Literal["Male", "Female"],
    BeforeValidator(clean_string),
    Field(..., description="Legal gender")
]
Honorific = Annotated[
    Literal["Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Rev.", "Hon.", "Engr.", "Ar."],
    BeforeValidator(clean_honorifics),
    Field(description="Legal honorifics")
]
CivilStatus = Annotated[
    Literal["Single", "Married", "Widowed", "Separated"],
    BeforeValidator(clean_string),
    Field(..., description="Legal Civil Status")
]
BirthDate = Annotated[
    date,
    BeforeValidator(parse_date_strings),
    AfterValidator(min_age_validator(0)),
    Field(..., description="Insured/Owner can be any age from birth onwards")
]
Country = Annotated[
    str,
    BeforeValidator(validate_country),
    Field(..., description="ISO 3166-1 alpha-3 country code", examples=["USA", "PHL", "CAN"])
]
TinID = Annotated[
    str,
    BeforeValidator(strip_id_formatting),
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^\d{9}$"
    ),
    Field(description="A 9-digit Tax Identification Number")
]
ZipCode = Annotated[
    str,
    StringConstraints(pattern=r"^\d{4}$"),
    Field(..., description="4-digit PH Zip Code")
]
Region = Annotated[
    PhRegion,
    Field(..., description="Official Administrative Regions of the Philippines")
]
EmailAdd = Annotated[
    EmailStr,
    AfterValidator(ensure_lower),
    Field(description="Primary contact email", examples=["applicant@example.com"])
]
PhoneNumber = Annotated[
    str,
    BeforeValidator(validate_phone),
    Field(..., description="Standardized E.164 phone number", examples=["+639171234567"])
]
MobileNumber = Annotated[PhoneNumber, AfterValidator(IsMobile)]
AnnualIncome = Annotated[
    float,
    Field(..., gt=0, description="Annual Income for computation of maximum insurance coverage")
]

# The Model
class QuoteRequest(BaseModel):
    # Part 1: Application for Insurance
    # Personal Information of the Proposed Insured/Owner
    # We'll assume that Insured is always the same as the Owner

    # Full name
    first_name: NameString
    last_name: NameString
    middle_name: NameString

    # Gender
    gender: Gender

    # Honorific
    honorific: Honorific

    # Civil Status
    civil_status: CivilStatus

    # Birthdate
    birthdate: BirthDate

    # Place of Birth
    place_of_birth: NameString

    # Country of Citizenship
    country_of_citizenship: Country

    # US Residency
    us_resident: bool

    # US Passport
    us_passport: bool

    # TIN
    tin: TinID

    # To avoid printing sensitive numbers on frontend
    @computed_field
    @property
    def masked_id(self) -> str:
        return f"{'*' * 7}{self.tin[-2:]}"
    
    # Address
    street_address: str = Field(..., min_length=5, max_length=100)
    barangay: str = Field(..., min_length=2, max_length=100)
    city: str = Field(..., min_length=2)
    region: Region
    zip_code: ZipCode

    #E-mail Address
    email: EmailAdd

    # Phone Numbers
    mobile_number: MobileNumber
    landline_number: Optional[PhoneNumber] = None

    # Occupation
    occupation: NameString

    # Company Name
    company_name: NameString

    # Monthly Income Range
    # Keeping this despite asking for Annual Income as a practice for StrEnum class
    monthly_income: MonthlyIncomeRange

    # Annual Income
    # Centralized the field since the insurance company is a Life Insurance company
    annual_income: AnnualIncome

    # Source of Income
    source_of_income: IncomeSource

    # Mother's Maiden Name
    mother_maiden_name: NameString

    # Max Coverage (simple placeholder, but definitely can align with regulatory standards)
    @computed_field
    def max_coverage(self) -> float:
        return self.annual_income * 10

# Life Insurance Products
# Term Life Product: Fortis Pure Life
class FortisPureLife(QuoteRequest):
    product_type: Literal["term_life"]
    product_code: Literal["HTC-TLIF-001"] = "HTC-TLIF-001"

    # Centralized Internal Constants
    # This is necessary so that pydantic doesn't expose variables BUT they're still centralized
    BASE_RATE: ClassVar[float] = 500.0
    COST_PER_THOUSAND: ClassVar[float] = 25.0

    # Mutually Exclusive Inputs (Both are Optional)
    requested_coverage: Optional[float] = Field(None, gt=0, description="Needs-driven approach")
    target_monthly_premium: Optional[float] = Field(None, gt=0, description="Budget-driven approach")

    # XOR logic on whichever the client wants
    @model_validator(mode='after')
    def enforce_exclusive_inputs(self):
        # Return an error if they provided both.
        if self.requested_coverage is not None and self.target_monthly_premium is not None:
            raise ValueError("You cannot provide both a target premium and a requested coverage.")
        
        # Return an error if they didn't provide any of both.
        if self.requested_coverage is None and self.target_monthly_premium is None:
            raise ValueError("You must provide either a target premium or a requested coverage.")
        
        return self
    
    @computed_field
    def calculated_coverage(self) -> float:
        """If they asked for coverage, return it. If they gave a budget, compute the average."""
        if self.requested_coverage is not None:
            return self.requested_coverage
        
        available_for_insurance = self.target_monthly_premium - self.BASE_RATE

        if available_for_insurance <= 0:
            raise ValueError(f"Budget is too low to cover the base policy fee of PHP{self.BASE_RATE}")
        
        return (available_for_insurance / self.COST_PER_THOUSAND) * 50000.0
    
    @computed_field
    def calculated_premium(self) -> float:
        """Calculated the monthly premium from their requested coverage."""
        if self.target_monthly_premium is not None:
            return self.target_monthly_premium
        
        coverage_cost = (self.requested_coverage / 50000.0) * self.COST_PER_THOUSAND
        return self.BASE_RATE + coverage_cost

# VUL Product: Nexus Wealth
# This can be changed in a future release, but for now, this product will be similar to Term-Life
class NexusWealth(QuoteRequest):
    product_type: Literal["variable_life"]
    product_code: Literal["HTC-VULF-001"] = "HTC-VULF-001"

    # Centralized Internal Constants
    # This is necessary so that pydantic doesn't expose variables BUT they're still centralized
    BASE_RATE: ClassVar[float] = 1000.0
    COST_PER_THOUSAND: ClassVar[float] = 50.0

    # Mutually Exclusive Inputs (Both are Optional)
    requested_coverage: Optional[float] = Field(None, gt=0, description="Needs-driven approach")
    target_monthly_premium: Optional[float] = Field(None, gt=0, description="Budget-driven approach")

    # XOR logic on whichever the client wants
    @model_validator(mode='after')
    def enforce_exclusive_inputs(self):
        # Return an error if they provided both.
        if self.requested_coverage is not None and self.target_monthly_premium is not None:
            raise ValueError("You cannot provide both a target premium and a requested coverage.")
        
        # Return an error if they didn't provide any of both.
        if self.requested_coverage is None and self.target_monthly_premium is None:
            raise ValueError("You must provide either a target premium or a requested coverage.")
        
        return self
    
    @computed_field
    def calculated_coverage(self) -> float:
        """If they asked for coverage, return it. If they gave a budget, compute the average."""
        if self.requested_coverage is not None:
            return self.requested_coverage
        
        available_for_insurance = self.target_monthly_premium - self.BASE_RATE

        if available_for_insurance <= 0:
            raise ValueError(f"Budget is too low to cover the base policy fee of PHP{self.BASE_RATE}")
        
        return (available_for_insurance / self.COST_PER_THOUSAND) * 50000.0
    
    @computed_field
    def calculated_premium(self) -> float:
        """Calculated the monthly premium from their requested coverage."""
        if self.target_monthly_premium is not None:
            return self.target_monthly_premium
        
        coverage_cost = (self.requested_coverage / 50000.0) * self.COST_PER_THOUSAND
        return self.BASE_RATE + coverage_cost

# The Annotated that acts as a switchboard for the product suite we have for our insurance company
AnyQuote = Annotated[
    Union[FortisPureLife, NexusWealth],
    Field(discriminator="product_type")
]

# 3. Setup the AWS S3 Connection
# Boto3 will automatically use the IAM Role we attach to the Lambda function later!
s3_client = boto3.client('s3')

# IMPORTANT: Change this to the exact name of the bucket you created in Phase 1
BUCKET_NAME = "hiltim-cheese-insurance" 

# 4. Create the API Endpoint
@app.post("/submit-quote")
async def submit_quote(quote: AnyQuote):
    try:
        # Convert the validated Pydantic model into a Python dictionary
        data_dict = quote.model_dump(mode='json')
        
        # Add a timestamp so we know exactly when this lead came in
        data_dict["timestamp"] = datetime.now(UTC).isoformat()
        
        # Create a totally unique file name (e.g., quote_abc123.json)
        # We add "quotes/raw/" to the beginning of the file name to organize the files
        file_name = f"quotes/raw/quote_{uuid.uuid4().hex}.json"
        
        # Convert the dictionary into a JSON string
        json_payload = json.dumps(data_dict)
        
        # Drop it into the S3 Vault!
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=file_name,
            Body=json_payload,
            ContentType="application/json"
        )
        
        return {"message": "Success! Lead secured in the Vault.", "file": file_name}
        
    except Exception as e:
        # If anything goes wrong, tell us exactly what it is
        raise HTTPException(status_code=500, detail=str(e))

# 5. Wrap the App for AWS Lambda
# AWS Lambda doesn't understand FastAPI natively. Mangum translates it.
handler = Mangum(app)