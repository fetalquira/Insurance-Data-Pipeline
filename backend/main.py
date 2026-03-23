from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    first_name: str
    age: int
    has_prior_claims: bool

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