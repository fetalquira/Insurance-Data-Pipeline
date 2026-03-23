# 1. Pull the official AWS Lambda Python 3.10 image
FROM public.ecr.aws/lambda/python:3.10

# 2. Copy our requirements file into the container
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 3. Install the Python packages
RUN pip install -r requirements.txt

# 4. Copy our actual code file into the container
COPY main.py ${LAMBDA_TASK_ROOT}

# 5. Tell AWS Lambda where to start executing (the Mangum handler in main.py)
CMD [ "main.handler" ]