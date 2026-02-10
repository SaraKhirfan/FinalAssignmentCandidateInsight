import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev_key_123')
    UPLOAD_FOLDER = 'uploads/resumes'
    PARSED_DATA_FOLDER = 'data/parsed_resumes'
    MATCH_RESULTS_FOLDER = 'data/match_results'
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')