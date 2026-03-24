from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from mangum import Mangum
import boto3
import json
import uuid
from datetime import datetime

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
# If a user tries to send an age as "Twenty", this will automatically reject it.
class QuoteRequest(BaseModel):
    # Part 1: Application for Insurance
    # Personal Information of the Proposed Insured

    # Full name of the Insured
    first_name_insured: str = Field(..., min_length=2, max_length=100)
    last_name_insured: str = Field(..., min_length=2, max_length=100)
    middle_name_insured: str = Field(..., min_length=2, max_length=100)

    # We use Literal to restrict the choices
    gender_insured: Literal["Male", "Female"]

    # Case-Insensitive Validator for Gender
    # field_validator decorator acts as a security guard at a gate
    @field_validator('gender_insured', mode='before')
    @classmethod
    def normalize_gender(cls, v: str) -> str:
        if isinstance(v, str):
            # Convert "male", "MALE", " Male " -> "Male"
            capitalized = v.strip().capitalize()
            return capitalized
        return v

    # We use Optional to ensure the field is valid even if empty
    honorific_insured: Optional[Literal["Mr.", "Ms.", "Mrs.", "Dr.", "Prof."]] = Field(
        None,
        description="The insured's legal title"
    )

    @field_validator('honorific_insured', mode='before')
    @classmethod
    def clean_honorific(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        
        name_map = {
            "mr": "Mr.",
            "mrs": "Mrs.",
            "ms": "Ms.",
            "dr": "Dr.",
            "prof": "Prof."
        }
        lookup = v.strip().lower().replace(".","")
        return name_map.get(lookup, v)

    age_insured: int
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
        data_dict = quote.model_dump()
        
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