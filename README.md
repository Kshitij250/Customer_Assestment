# CustomerAssessmentAI

An AI-powered financial assessment platform that combines a **FastAPI backend** with a **Streamlit frontend** to analyze company financial documents, generate legal/financial summaries, and support investment decision-making using LLM-driven insights.

## Overview

CustomerAssessmentAI automates the process of extracting, analyzing, and summarizing financial documents (annual reports, balance sheets, quarterly results) to help users quickly assess a company's financial health and make informed decisions. The platform integrates real-time market data, document intelligence, and a trained decision model into a single workflow.

## Features

- **Financial Document Analysis** — Upload annual reports, balance sheets, or quarterly results (PDF) for automated extraction and summarization
- **Legal & Financial Summarization** — LLM-powered summaries of key legal and financial disclosures using the Groq API
- **NSE Market Data Integration** — Pulls live stock data via the NSE service and yfinance for up-to-date company metrics
- **Automated Decision Model** — A trained ML model (`decision_model.pkl`) that scores companies based on extracted financial signals
- **Web Crawling & Screener** — Background crawler and screener services to gather supplementary company data
- **Interactive Frontend** — A Streamlit interface for uploading documents, viewing summaries, and exploring analysis results in real time

## Tech Stack

**Backend**
- FastAPI — REST API layer serving all analysis endpoints
- Groq API (LLaMA) — LLM-powered document summarization and legal analysis
- scikit-learn — Decision model training and inference
- PDF extraction pipeline — Parses uploaded financial documents

**Frontend**
- Streamlit — Interactive web interface

**Data & Integrations**
- yfinance / NSE service — Real-time and historical market data
- Web crawler worker — Background data collection

## Project Structure

```
customer-assessment-ai/
├── backend/
│   ├── main.py                  # FastAPI application entry point
│   ├── crawler_worker.py        # Background web crawler
│   └── services/
│       ├── decision_model.py    # ML decision model logic
│       ├── train_decision_model.py
│       ├── groq_client.py       # Groq LLM API client
│       ├── legal_service.py     # Legal document summarization
│       ├── nse_service.py       # NSE market data integration
│       ├── pdf_extractor.py     # PDF parsing and text extraction
│       └── screener_service.py  # Company screening logic
├── frontend/
│   └── app.py                   # Streamlit application
├── decision_model.pkl           # Trained model artifact
├── train_decision_model.py      # Model training script
├── requirements.txt
├── .env.example                 # Environment variable template
└── README.md
```

## Getting Started

### Prerequisites
- Python 3.10+
- A Groq API key ([console.groq.com](https://console.groq.com))

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/Kshitij250/Customer_Assestment.git
   cd Customer_Assestment
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and add your own API keys (Groq, and any other required credentials).

### Running the app

Start the FastAPI backend:
```bash
cd backend
uvicorn main:app --reload
```

In a separate terminal, start the Streamlit frontend:
```bash
cd frontend
streamlit run app.py
```

The Streamlit app will typically be available at `http://localhost:8501`, and the FastAPI backend at `http://localhost:8000` (interactive API docs at `http://localhost:8000/docs`).

## Notes

- Uploaded documents and cached PDFs are excluded from version control (`backend/uploads/`) to keep the repository lightweight.
- Environment files containing real API keys are excluded via `.gitignore` — only `.env.example` (with placeholder values) is tracked.

## Author

**Kshitij Singh**
B.Tech, Electronics & Communication Engineering, Birla Institute of Technology, Mesra
[LinkedIn](https://www.linkedin.com/in/kshitijsingh2024/) · [GitHub](https://github.com/Kshitij250)