# Self-Healing ELT Pipeline 🚀

## Phase 1 — Data Ingestion Pipeline (Completed ✅)

This project implements a production-style data ingestion pipeline that downloads real-world data and stores it in a structured data lake on AWS S3.

---

## 📌 What this phase does

* Downloads NYC Yellow Taxi trip data (Parquet format)
* Uploads data to AWS S3
* Organizes data using partitioning (year/month)
* Uses environment variables for secure credential management

---

## 🏗️ Architecture (Phase 1)

Public Dataset → Python Script → AWS S3 Data Lake

---

## 📂 Project Structure

```
self-healing-data-pipeline/
│
├── ingestion/
│   └── ingest_nyc_taxi.py
├── dags/
├── dbt/
├── docker/
├── k8s/
├── tests/
├── ge/
├── terraform/
├── .env.example
├── requirements.txt
└── README.md
```

---

## ⚙️ Tech Stack (Phase 1)

* Python
* boto3 (AWS SDK)
* pandas
* requests
* python-dotenv
* AWS S3

---

## 📊 Data Source

NYC Yellow Taxi Trip Data
Public dataset (~1.5M rows/month) in Parquet format.

---

## 🧠 Data Lake Design (Partitioning)

Data is stored in S3 using partitioned paths:

```
s3://<your-bucket>/raw/nyc_taxi/year=2024/month=01/
```

### Why partitioning?

* Faster queries
* Lower cloud cost
* Easier data management

---

## 🔐 Environment Setup

Create a `.env` file:

```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-south-1
S3_BUCKET=your-bucket-name
```

---

## ▶️ How to Run

```bash
python ingestion/ingest_nyc_taxi.py
```

---

## ✅ Expected Output

* File downloaded locally (~50MB)
* Uploaded to S3
* Structured folder created:

```
raw/
 └── nyc_taxi/
      └── year=2024/
           └── month=01/
```

---

## 🚧 Next Steps (Phase 2)

* Automate pipeline using Apache Airflow
* Containerize using Docker
* Add scheduling and retries
* Introduce monitoring

---

## 💡 Key Learnings

* Built a real-world ingestion pipeline
* Integrated Python with AWS S3
* Implemented data lake partitioning
* Managed credentials securely using environment variables

---
