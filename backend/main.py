from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import phonenumbers
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    BeforeValidator,
    AfterValidator,
    field_validator,
    computed_field,
    EmailStr
)
from typing import (
    Literal,
    Optional,
    Annotated,
    Any
)
from mangum import Mangum
import boto3
import json
import uuid
import pycountry
from datetime import datetime, date


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

# Annotations for Reusability
NameString = Annotated[str, Field(..., min_length=2, max_length=100)]
Gender = Annotated[
    Literal["Male", "Female"],
    BeforeValidator(clean_string),
    Field(description="Legal gender")
]
Honorific = Annotated[
    Literal["Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Rev.", "Hon.", "Engr.", "Ar."],
    BeforeValidator(clean_honorifics),
    Field(description="Legal honorifics")
]
CivilStatus = Annotated[
    Literal["Single", "Married", "Widowed", "Separated"],
    BeforeValidator(clean_string),
    Field(description="Legal Civil Status")
]
BirthDate = Annotated[
    date,
    BeforeValidator(parse_date_strings),
    AfterValidator(min_age_validator(0)),
    Field(description="Insured/Owner can be any age from birth onwards")
]
Country = Annotated[
    str,
    BeforeValidator(validate_country),
    Field(description="ISO 3166-1 alpha-3 country code", examples=["USA", "PHL", "CAN"])
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
    Field(description="4-digit PH Zip Code")
]
Region = Annotated[
    Literal[
        "NCR",
        "CAR",
        "Region I",
        "Region II",
        "Region III",
        "Region IV-A",
        "MIMAROPA",
        "Region V",
        "Region VI",
        "Region VII",
        "Region VIII",
        "NIR",
        "Region IX",
        "Region X",
        "Region XI",
        "Region XII",
        "SOCCSKSARGEN",
        "CARAGA",
        "BARMM"
    ],
    Field(..., min_length=2, max_length=20, description="Official Regions of the Philippines")
]
EmailAdd = Annotated[
    EmailStr,
    AfterValidator(ensure_lower),
    Field(description="Primary contact email", examples=["applicant@example.com"])
]
PhoneNumber = Annotated[
    str,
    BeforeValidator(validate_phone),
    Field(description="Standardized E.164 phone number", examples=["+639171234567"])
]
MobileNumber = Annotated[PhoneNumber, AfterValidator(IsMobile)]

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

# 3. Setup the AWS S3 Connection
# Boto3 will automatically use the IAM Role we attach to the Lambda function later!
s3_client = boto3.client('s3')

# IMPORTANT: Change this to the exact name of the bucket you created in Phase 1
BUCKET_NAME = "hiltim-cheese-insurance" 

# 4. Create the API Endpoint
@app.post("/submit-quote")
async def submit_quote(quote: QuoteRequest):
    try:
        # Convert the validated Pydantic model into a Python dictionary
        data_dict = quote.model_dump(mode='json')
        
        # Add a timestamp so we know exactly when this lead came in
        data_dict["timestamp"] = datetime.utcnow().isoformat()
        
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