from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    BeforeValidator,
    AfterValidator,
    computed_field
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
app = FastAPI(title="Hilaga Timog Cheese Insurance API")

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
BirthDateInsured = Annotated[
    date,
    BeforeValidator(parse_date_strings),
    AfterValidator(min_age_validator(0)),
    Field(description="Insured can be any age from birth onwards")
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

# The Model
class QuoteRequest(BaseModel):
    # Part 1: Application for Insurance
    # Personal Information of the Proposed Insured

    # Full name of Insured
    first_name_insured: NameString
    last_name_insured: NameString
    middle_name_insured: NameString

    # Gender of Insured
    gender_insured: Gender

    # Honorific of Insured
    honorific_insured: Honorific

    # Civil Status of Insured
    civil_status_insured: CivilStatus

    # Birthdate of Insured
    birthdate_insured: BirthDateInsured

    # Place of Birth of Insured
    place_of_birth_insured: NameString

    # Country of Citizenship of Insured
    country_of_citizenship_insured: Country

    # US Residency of Insured
    us_resident_insured: bool

    # US Passport of Insured
    us_passport_insured: bool

    # TIN of Insured
    tin_insured: TinID

    # To avoid printing sensitive numbers on frontend
    @computed_field
    @property
    def masked_id(self) -> str:
        return f"{'*' * 7}{self.tin_insured[-2:]}"

    has_prior_claims_insured: bool

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