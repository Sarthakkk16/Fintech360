from pyspark import pipelines as dp
from pyspark.sql.functions import current_timestamp, col

S3_BASE = "s3://fintech360"

def ingest_dataset(folder):
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .load(f"{S3_BASE}/{folder}/")
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_file", col("_metadata.file_path"))
    )

@dp.table(name="loans", comment="Bronze loans data")
def loans():
    return ingest_dataset("loans")

@dp.table(name="upi_data", comment="Bronze UPI data")
def upi_data():
    return ingest_dataset("upi_data")

@dp.table(name="emi_data", comment="Bronze EMI data")
def emi_data():
    return ingest_dataset("emi_data")

@dp.table(name="bureau_data", comment="Bronze bureau data")
def bureau_data():
    return ingest_dataset("bureau")

@dp.table(name="bank_data", comment="Bronze bank data")
def bank_data():
    return ingest_dataset("bank")