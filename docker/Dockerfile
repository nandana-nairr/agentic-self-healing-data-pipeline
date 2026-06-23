FROM apache/airflow:2.9.1-python3.11

USER root

# install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && apt-get clean

USER airflow

#copy and install python dependencies
COPY requirements-airflow.txt .
RUN pip install --no-cache-dir -r requirements-airflow.txt