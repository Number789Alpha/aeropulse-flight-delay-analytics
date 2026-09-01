# ✈️ AeroPulse: Commercial Airline & Flight Delay Analytics Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://aeropulse-flight-delay-analytics-xdpdjhpyfifrfgmxruwkcw.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQL%20Server%20%7C%20SQLite-00E5FF.svg)](https://www.microsoft.com/en-us/sql-server/)
[![Machine Learning](https://img.shields.io/badge/ML-Scikit--Learn%20%7C%20HistGradientBoosting-F59E0B.svg)](https://scikit-learn.org/)
[![Graph Analytics](https://img.shields.io/badge/NetworkX-Centrality%20Analysis-8B5CF6.svg)](https://networkx.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B.svg)](https://streamlit.io/)
[![CI Workflow](https://img.shields.io/badge/CI-GitHub%20Actions%20Passing-10B981.svg)](.github/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> 🌐 **Live Interactive Cockpit Dashboard:**  
> 👉 **[https://aeropulse-flight-delay-analytics-xdpdjhpyfifrfgmxruwkcw.streamlit.app/](https://aeropulse-flight-delay-analytics-xdpdjhpyfifrfgmxruwkcw.streamlit.app/)**

> **Portfolio Pitch:** *"I can design a normalized relational schema (Star Schema / 3NF), engineer an automated high-throughput ETL pipeline with automated Data Quality validation, author non-trivial analytical SQL (window functions, recursive CTEs, and lag-based propagation), layer in a predictive delay-risk machine learning model, and serve sub-100ms insights through an interactive cockpit HUD dashboard reading live from the database — not just plot a flat CSV in pandas."*

---

## 📌 Executive Summary

**AeroPulse** is an enterprise-grade commercial aviation data platform built to quantify delay patterns, root causes, and turnaround cascading effects across the US flight network. 

Historical flight data (Bureau of Transportation Statistics / Kaggle) is ingested, validated, and normalized into a **Star Schema** relational database (**Microsoft SQL Server** with `fast_executemany` bulk inserts and **SQLite** for zero-dependency portability). Analytical SQL queries run directly against the database to measure punctuality, airport congestion, and aircraft turnaround propagation, while an integrated **Gradient Boosting Machine Learning model** forecasts future flight delay risk and a **NetworkX directed graph** pinpoints structural hub bottlenecks.

---

## 🗺️ System Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["1. Ingestion & Data Quality"]
        A[US DOT BTS / Kaggle] --> B[etl/download_data.py]
        B --> C[data/raw_flights.csv]
        C --> D[etl/validate.py<br/>Schema & Logic Checks]
        D -->|Log Violations| E[(DQ_Issues Table)]
    end

    subgraph Data_Engineering ["2. Normalization & Star Schema ETL"]
        D --> F[etl/01_etl.py]
        F --> G[Surrogate Key Dimension Mapping]
        G --> H[(Relational Database<br/>SQL Server / SQLite)]
        F -->|Log Batch Audit| I[(ETL_Log Table)]
    end

    subgraph Analytical_Engines ["3. SQL Analytics, ML & Graph Layers"]
        H --> J["sql/analysis_queries.sql<br/>• LAG() Turnaround Propagation<br/>• 7-Day Rolling Averages<br/>• DENSE_RANK() Airline Ratings<br/>• Delay Cause Breakdown (%)<br/>• Statistical Anomaly (>2σ)"]
        H --> K[ml/predict_delay.py<br/>HistGradientBoosting Classifier]
        H --> L[dashboard/network_graph.py<br/>NetworkX Bottlenecks & Centrality]
    end

    subgraph User_Interface ["4. Interactive Cockpit HUD Dashboard"]
        J --> M[dashboard/app.py]
        K --> M
        L --> M
        M --> N[Executive KPIs & FAA Cost Estimator]
        M --> O[Route Corridors & Bottlenecks]
        M --> P[Punctuality Leaderboards]
        M --> Q[Interactive Delay Risk Predictor]
        M --> R[Live SQL Studio & Recruiter Sandbox]
    end
```

---

## 🎯 Business Questions Answered

| Business Question | Analytical SQL / ML Method | Key Insight / Value |
|---|---|---|
| **1. Does an inbound flight delay propagate into the next departure?** | `LAG(arr_delay_min) OVER (PARTITION BY tail_number, date_id ORDER BY scheduled_dep_time)` | Isolates when inbound delays >15m cause outbound delays vs when ground buffers absorb them. |
| **2. Which hubs suffer from chronic congestion vs temporary shock?** | `AVG(dep_delay_min) OVER (PARTITION BY airport_id ORDER BY full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` | Smooths daily noise to reveal structural delays at congested hubs (e.g. ORD, EWR, JFK). |
| **3. How do airlines rank on true punctuality?** | `RANK()` and `DENSE_RANK()` against US DOT 15-minute standard | Distinguishes between carriers with frequent minor delays vs rare catastrophic delays. |
| **4. What are the primary root causes of flight delays per corridor?** | Categorical aggregation of `carrier_delay`, `weather_delay`, `nas_delay`, `late_aircraft_delay` | Identifies whether delays are airline-controllable or airspace/weather-driven. |
| **5. Do delays cascade across 3+ connecting legs for an aircraft?** | Multi-hop Succession CTE tracking Leg 1 ➔ Leg 2 ➔ Leg 3 sequences partitioned by tail number | Identifies whether ground turnaround buffers absorbed delay at Leg 2 or cascaded fleet-wide. |
| **6. Which flights suffered abnormal, systemic disruptions?** | Route rolling $Z$-Score: `(arr_delay - mean) / std_dev > 2.0` | Surfaces black-swan weather events and FAA ground stops automatically. |
| **7. Which airports represent single-point-of-failure bottlenecks?** | NetworkX Directed Graph: **Betweenness Centrality** & PageRank | Identifies hubs on the critical path of multi-leg aircraft rotations. |
| **8. What is the operational delay risk of a scheduled flight?** | Scikit-Learn `HistGradientBoostingClassifier` with feature scoring | Delivers live delay probability scores and risk mitigation advice before departure. |

---

## 🗄️ Relational Database Schema (Star Schema / 3NF)

```mermaid
erDiagram
    DATES ||--o{ FLIGHTS : "occurs_on (date_id)"
    AIRLINES ||--o{ FLIGHTS : "operated_by (airline_id)"
    AIRPORTS ||--o{ FLIGHTS : "departs_from (origin_airport_id)"
    AIRPORTS ||--o{ FLIGHTS : "arrives_at (dest_airport_id)"
    ETL_LOG ||--o{ DQ_ISSUES : "tracks (run_id)"

    DATES {
        int date_id PK "YYYYMMDD"
        date full_date
        varchar day_of_week
        int day_num_of_week
        int month
        varchar month_name
        int quarter
        int year
        smallint is_weekend
    }

    AIRLINES {
        int airline_id PK
        varchar airline_code UK "e.g. DL, AA, UA"
        varchar airline_name
    }

    AIRPORTS {
        int airport_id PK
        varchar airport_code UK "e.g. ATL, ORD, DFW"
        varchar airport_name
        varchar city
        varchar state
        decimal latitude
        decimal longitude
    }

    FLIGHTS {
        bigint flight_id PK
        int date_id FK
        int airline_id FK
        int origin_airport_id FK
        int dest_airport_id FK
        varchar flight_number
        varchar tail_number
        smallint scheduled_dep_time
        smallint actual_dep_time
        smallint scheduled_arr_time
        smallint actual_arr_time
        int dep_delay_min
        int arr_delay_min
        smallint cancelled
        varchar cancellation_reason
        smallint diverted
        int carrier_delay
        int weather_delay
        int nas_delay
        int security_delay
        int late_aircraft_delay
    }

    ETL_LOG {
        int run_id PK
        datetime run_timestamp
        int rows_inserted
        varchar source_file
        varchar status
        decimal execution_time_sec
    }

    DQ_ISSUES {
        int issue_id PK
        int run_id FK
        varchar issue_type
        varchar record_ref
        datetime detected_at
        text details
    }
```

---

## 📂 Repository Structure

```
aeropulse/
├── data/                       # Raw and sample datasets (gitignored)
│   ├── raw_flights.csv         # 49,405 flight records
│   ├── airlines.csv            # Airline carriers reference table
│   ├── airports.csv            # US airport hubs reference table with GPS coordinates
│   └── flights.db              # Portable SQLite database fallback
├── sql/
│   ├── schema.sql              # Star Schema & audit tables DDL with performance indexes
│   └── analysis_queries.sql    # 6 advanced analytical SQL queries
├── etl/
│   ├── 01_etl.py               # Production ETL pipeline: cleaning, surrogate keys, bulk load
│   ├── download_data.py        # Data acquisition: Kaggle API, BTS TranStats, & realistic synthesizer
│   ├── validate.py             # Data quality & logic validation rules (logs to DQ_Issues)
│   ├── scheduler.py            # Simulated monthly BTS batch refresh scheduler
│   └── etl_pipeline.py         # Clean import wrapper
├── ml/
│   ├── predict_delay.py        # Gradient Boosting delay classifier & inference engine
│   └── model.pkl               # Serialized model artifact
├── dashboard/
│   ├── app.py                  # Streamlit Cockpit HUD multi-page analytics dashboard
│   ├── network_graph.py        # NetworkX betweenness centrality & 2D graph renderer
│   └── assets/
│       └── airplane_bg.jpg     # Cinematic twilight cockpit background image
├── tests/
│   ├── test_etl.py             # Automated unit tests for ETL pipeline
│   └── test_validation.py      # Automated unit tests for DQ assertions & ML inference
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI workflow (lint + pytest)
├── Dockerfile                  # Container definition for production deployment
├── docker-compose.yml          # One-command Docker orchestration
├── .env.example                # Database connection string template
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies
└── README.md                   # Recruiter-ready documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Environment Setup
```bash
git clone https://github.com/Number789Alpha/aeropulse-flight-delay-analytics.git
cd aeropulse-flight-delay-analytics

python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # macOS/Linux

pip install -r requirements.txt
```

### 2. Run Data Acquisition & ETL Pipeline
```bash
# 1. Synthesize 49,000+ realistic BTS flights:
python etl/download_data.py --days 60 --flights-per-day 400

# 2. Run Data Quality checks and Star Schema bulk loading:
python etl/01_etl.py
```

### 3. Train the Delay Risk Machine Learning Model
```bash
python ml/predict_delay.py
```

### 4. Run Automated Test Suite
```bash
python -m pytest tests/ -v
```

### 5. Launch the Streamlit Cockpit Dashboard
```bash
streamlit run dashboard/app.py --server.port 8502
```
Navigate to **`http://localhost:8502`** in your browser.

---

## ☁️ Live Cloud Deployment (Streamlit Community Cloud)

AeroPulse is deployed and running live on **Streamlit Community Cloud**:

🔗 **Live Public App:** [https://aeropulse-flight-delay-analytics-xdpdjhpyfifrfgmxruwkcw.streamlit.app/](https://aeropulse-flight-delay-analytics-xdpdjhpyfifrfgmxruwkcw.streamlit.app/)

### Cloud Architecture Highlights:
- **Zero-Setup Database Replica**: Embeds a portable SQLite 3NF Star Schema (`data/flights.db`) containing 49,405 flight records with full dimensional indexing.
- **System ODBC Drivers**: Automatically installed via `packages.txt` (`unixodbc`, `unixodbc-dev`).
- **Dark Cockpit Theme**: Pre-configured via `.streamlit/config.toml`.
- **Runtime Pinned to Python 3.11**: Guaranteed package stability via `.python-version`.
- **Role-Based Access Control**: Configurable via Streamlit Secrets (`[admin_credentials]`).

---

## 🐳 Docker Deployment

To spin up the entire application inside Docker with zero local setup:
```bash
docker-compose up --build
```
Access the dashboard on `http://localhost:8502`.

---

## 💼 Resume & Interview Talking Points

- **Data Engineering / Normalization:** *"Designed and implemented a 3NF Star Schema relational database with surrogate key mapping, audit logging (`ETL_Log`), and automated data validation rules (`DQ_Issues`), using SQLAlchemy with `fast_executemany` for high-throughput batch ingestion."*
- **Advanced SQL:** *"Engineered complex analytical SQL utilizing window functions (`LAG`, `LEAD`, `RANK`, `DENSE_RANK`, rolling multi-day frame clauses, and standard deviation anomaly detection) to isolate aircraft turnaround cascading and carrier reliability."*
- **Predictive Machine Learning:** *"Trained a `HistGradientBoostingClassifier` predicting flight departure delay probabilities (>15 min) with live inference integrated directly into the dashboard."*
- **Graph / Network Analytics:** *"Leveraged NetworkX to construct a directed route graph weighted by delay and flight volume, computing Betweenness Centrality and PageRank to spot structural airport bottlenecks."*
- **Full-Stack Analytics Delivery:** *"Architected an interactive Streamlit dashboard featuring custom aviation cockpit aesthetics, glassmorphism cards, and sub-100ms query caching reading directly from live relational database connections."*

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
