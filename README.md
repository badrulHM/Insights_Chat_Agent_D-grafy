D'grafy Insight Agent is a simple AI-powered data insights application designed to allow users to ask questions about business data through a web interface.
The application uses Streamlit for the user interface and connects to Google BigQuery as the data source. The goal is to provide a simple way for users to access and understand business information without needing to work directly with SQL or BigQuery.

The application is being developed with a simple architecture: Streamlit --> Insight Agent --> BigQuery --> Business Insights

Tech stack:

- Python
- Streamlit
- Google BigQuery
- Google Cloud authentication
- Gemini for the Insight Agent
- LangChain for agent orchestration
- LangSmith for observability

Project Structure:

D'grafy agent/
│
├── app.py
├── agent/
├── auth/
├── db/
├── eval/
├── .gitignore
├── requirements.txt
└── README.md