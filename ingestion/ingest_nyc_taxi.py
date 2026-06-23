import boto3
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

def download_nyc_taxi(year: int, month: int) -> str:
    """Download NYC Yellow Taxi parquet for a given month."""
    filename = f"yellow_tripdata_{year}-{month:02d}.parquet"
    url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{filename}"
    local_path = filename

    print(f"Downloading {filename}...")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Downloaded {filename} ({os.path.getsize(local_path) / 1e6:.1f} MB)")
    return local_path

def upload_to_s3(local_path: str, s3_key: str) -> str:
    """Upload a file to S3 raw layer."""
    s3 = boto3.client("s3", region_name=REGION)
    s3.upload_file(local_path, BUCKET, s3_key)
    s3_uri = f"s3://{BUCKET}/{s3_key}"
    print(f"Uploaded to {s3_uri}")
    return s3_uri

def ingest(year: int = None, month: int = None) -> str:
    """Full ingest: download from source → upload to S3 raw/."""
    now = datetime.now()
    year = year or now.year
    month = month or (now.month - 1 or 12)  # default: last month

    local_path = download_nyc_taxi(year, month)
    s3_key = f"raw/nyc_taxi/year={year}/month={month:02d}/yellow_tripdata_{year}-{month:02d}.parquet"
    s3_uri = upload_to_s3(local_path, s3_key)

    os.remove(local_path)  # clean up /tmp
    return s3_uri

if __name__ == "__main__":
    result = ingest(2024, 1)
    print(f"Done: {result}")