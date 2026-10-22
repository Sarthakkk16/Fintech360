# Fintech360 - Scalable Data & Risk Pipeline

## 📌 Project Overview
Fintech360 is a production-grade scalable data pipeline designed to process loan lifecycle data[cite: 4]. It captures simulated fintech data generated via Python Faker, stores it in an AWS RDS PostgreSQL database, and processes it through a Medallion architecture in Databricks[cite: 2]. The final outputs are optimized to serve Data Analysts, Machine Learning models (for credit risk and underwriting), and Management dashboards in Power BI[cite: 2].

## 🏗️ Architecture & Data Flow
The pipeline follows a robust Medallion architecture with strict validation and routing gates[cite: 2, 3]:

*   **Data Generation & Ingestion:** Python `faker` scripts generate realistic loan applications, KYC status, repayments, and DPD (Days Past Due) tracking, which are stored in AWS RDS[cite: 4].
*   **Data Lake Landing:** Raw data is extracted and lands in an AWS S3 bucket[cite: 2, 3].
*   **Bronze Layer (Raw/CDC):** Ingests raw data from S3, retaining an immutable historical log of all transactions[cite: 2, 3].
*   **Schema Validation Gate:** Enforces checks on columns, data types, nullability, and schema evolution before data enters the Silver layer[cite: 2, 3].
*   **Silver Layer (Clean Data):** Cleanses, deduplicates, and standardizes data while masking Personally Identifiable Information (PII)[cite: 2, 3].
*   **Data Quality Gate & Quarantine:** 
    *   Performs strict checks: Null checks, Duplicate checks, Range checks, and Referential integrity[cite: 2, 3].
    *   **PASS:** Clean data moves to the Business Transformation stage (Gold)[cite: 3].
    *   **FAIL:** Corrupted data is routed to a Quarantine (Error Monitoring) table to prevent downstream metric corruption[cite: 2, 3].
*   **Gold Layer (Business Transformation):** Highly aggregated, denormalized tables (e.g., portfolio quality, collection efficiency) secured and governed by Unity Catalog[cite: 2, 3].
*   **Downstream Serving:** Power BI / Analytics[cite: 3].

## 🛠️ Tech Stack
*   **Data Generation:** Python (Faker library)[cite: 2]
*   **Transactional Source:** AWS RDS (PostgreSQL)[cite: 2]
*   **Data Lake:** AWS S3[cite: 2]
*   **Compute & Processing:** Databricks, PySpark, Delta Lake[cite: 2, 4]
*   **Governance:** Databricks Unity Catalog (Row-Level & Column-Level Security)[cite: 2]
*   **Downstream Consumption:** Power BI, Databricks SQL[cite: 2, 4]

## 🚀 Key Features
*   **Decoupled Compute & Storage:** Leverages distributed PySpark compute to handle variable data volumes natively without bottlenecking[cite: 2].
*   **Strict Quality Routing:** The explicit pass/fail data quality routing guarantees data trust for downstream models and dashboards[cite: 2].
*   **Optimized BI Rendering:** Upstream aggregations allow Power BI to utilize query folding for sub-second dashboard rendering[cite: 2].
*   **Enterprise Security:** Sensitive financial data is isolated using Row-Level Security (RLS) and Column-Level Security (CLS) via Unity Catalog[cite: 2].

## 📂 Project Documentation
For a deep dive into the planning and architecture, refer to the project documents:
*   **Product Requirements Document (PRD)**
*   **Software Requirements Specification (SRS)**[cite: 2]
*   **12-Week Project Plan**[cite: 4]
