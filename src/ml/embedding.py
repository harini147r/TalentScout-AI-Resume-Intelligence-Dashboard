from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def load_sbert_model():
    """Initializes and returns the lightweight MiniLM transformer model."""
    return SentenceTransformer('all-MiniLM-L6-v2')

def calculate_similarity(jd_vector, resume_vector):
    """Calculates the geometric cosine angle between two SBERT embeddings."""
    v1 = np.array(jd_vector).reshape(1, -1)
    v2 = np.array(resume_vector).reshape(1, -1)
    return float(cosine_similarity(v1, v2)[0][0])