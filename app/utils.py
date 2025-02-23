# app/utils.py
from app.logger import logger
import re

def split_into_sentences(text: str) -> dict:
    """Splits text into sentences, handling common abbreviations."""
    # Improved regex to handle more cases, including abbreviations.
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<![A-Z]\.)(?<=\.|\?|\!)\s', text)
    complete_sentences = []
    remainder = ""

    if sentences:
        complete_sentences = sentences[:-1]  # All except last
        remainder = sentences[-1]  # Last one might be incomplete

    return {"complete": complete_sentences, "remainder": remainder}