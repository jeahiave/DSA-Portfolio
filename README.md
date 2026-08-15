# Data Science, Analytics, & Data Engineering Portfolio

A consolidated monorepo housing projects in predictive analytics and automated data engineering pipelines.

---

## Repository Migration Note

This repository is the result of a structural consolidation. The projects contained here were originally developed and maintained in separate repositories. To streamline presentation, they were merged into this unified monorepo.

Consequently, granular commit histories prior to **August 2026** were not preserved. However, all core source code, documentation, and project assets have been fully retained.

---

## Projects Overview

### 1. Digital Engagement Analytics for Agribusiness Growth
[![Project Status: Active](https://img.shields.io/badge/status-active-success.svg)](./proj-00-digital-engagement-analytics-for-agribusiness-growth/)

This project uses machine learning to quantify the impact of social media marketing on agribusiness profitability in Ghana. It builds predictive models to link digital engagement with financial value and customer churn.

*   **Directory:** [`./proj-00-digital-engagement-analytics-for-agribusiness-growth/`](./proj-00-digital-engagement-analytics-for-agribusiness-growth/)
*   **Key Technologies:** Python, Pandas, Scikit-learn, XGBoost, LightGBM
*   **Core Outcome:** The model demonstrated a strong statistical link between digital engagement and financial value **(R² = 0.836)**, proving that social media is a significant driver of agribusiness growth.

### 2. Data Engineering ETL Pipelines
[![Project Status: Active](https://img.shields.io/badge/status-active-success.svg)](./proj-01-basic-to-advanced-data-eng-ETL-pipelines/)
 
A collection of automated ETL (Extract, Transform, Load) pipelines designed to handle various data sources and business needs. Each pipeline is a self-contained demonstration of data engineering principles.

*   **Directory:** `./proj-01-basic-to-advanced-data-eng-ETL-pipelines/`
*   **Key Technologies:** Python, Pandas, SQLAlchemy, `requests`, `yfinance`, Google Gemini API
*   **Included Pipelines:**
    *   **Daily Employee Roster ETL:** Extracts, flattens, and loads JSON API data into a SQLite database.
    *   **Live Global Earthquake Monitor:** Ingests a live GeoJSON feed and appends filtered data to a persistent database.
    *   **Stock Update & Insight Automation:** Fetches daily stock data and uses a GenAI model to generate automated marketing insights.

---

## Repository Structure

```text
dsa-portfolio/
├── .github/
│   └── workflows/
│       └── python-app.yml      # CI workflow for ETL project
├── proj-00-digital-engagement-analytics-for-agribusiness-growth/
│   ├── notebooks/
│   ├── src/
│   └── README.md               # Project-specific details
├── proj-01-basic-to-advanced-data-eng-ETL-pipelines/
│   ├── 00-ETL-daily-employee-record-data-pipeline/
│   ├── 02-ETL-global-earthquake-data-pipeline/
│   ├── 03-ETL-appl-stock-update-automation-pipeline/
│   └── README.md               # Project-specific details
└── README.md                   # Top-level repository overview (this file)
```

##    Getting Started

For detailed setup, dependency installation, and execution instructions, please refer to the `README.md` file located within each project's sub-directory:

*    **Project 1: Digital Engagement Analytics**
*    **Project 2: Data Engineering ETL Pipelines**

---

Thank you for visiting!
