import json

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _flatten(value) -> str:
    """Turn strings / JSON strings / lists / dicts into one plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            return _flatten(json.loads(value))
        except Exception:
            return value
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def listing_document(row: dict) -> str:
    """The text of one listing that the model learns from."""
    fields = [
        "title",
        "category",
        "layout_type",
        "village_name",
        "amenity_list",
        "nearby_establishments",
    ]
    return " ".join(_flatten(row.get(f)) for f in fields).lower()


class PropertyRecommender:
    def __init__(self):
        self.word_vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.char_vec = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
        )
        self.rows: list[dict] = []
        self.matrix = None

    # ---------- training ----------
    def fit(self, rows: list[dict]):
        """Fit TF-IDF on the real listings pulled from Supabase."""
        self.rows = rows
        if not rows:
            self.matrix = None
            return self
        docs = [listing_document(r) for r in rows]
        words = self.word_vec.fit_transform(docs)
        chars = self.char_vec.fit_transform(docs)
        self.matrix = hstack([words, chars]).tocsr()
        return self

    # ---------- scoring ----------
    def _query_vec(self, text: str):
        text = text.lower()
        return hstack(
            [self.word_vec.transform([text]), self.char_vec.transform([text])]
        ).tocsr()

    def text_similarity(self, text: str) -> np.ndarray:
        if self.matrix is None:
            return np.zeros(0)
        return cosine_similarity(self._query_vec(text), self.matrix).ravel()

    @staticmethod
    def _budget_fit(values, budget) -> np.ndarray:
        """1.0 when within budget, decays smoothly the further a listing goes over it."""
        if not budget:
            return np.ones(len(values))
        v = np.array([x if x is not None else np.inf for x in values], dtype=float)
        over = np.clip(v / budget - 1.0, 0, None)
        return np.exp(-5.0 * over)

    def is_in_domain(self, text: str, threshold: float) -> bool:
        sim = self.text_similarity(text)
        return bool(sim.size) and float(sim.max()) >= threshold

    def rank(
        self,
        text: str,
        budget=None,
        monthly=None,
        downpayment=None,
        is_downpayment=False,
        top_n: int = 20,
    ) -> list[dict]:
        if self.matrix is None:
            return []

        sim = self.text_similarity(text)

        price_col = "initial_dp" if is_downpayment else "price_total"
        fit = self._budget_fit([r.get(price_col) for r in self.rows], budget)
        fit = fit * self._budget_fit([r.get("initial_dp") for r in self.rows], downpayment)
        fit = fit * self._budget_fit([r.get("monthly_rate") for r in self.rows], monthly)

        score = 0.6 * sim + 0.4 * fit
        idx = np.argsort(-score)[:top_n]

        return [
            {
                "row": self.rows[i],
                "text_sim": float(sim[i]),
                "budget_fit": float(fit[i]),
                "score": float(score[i]),
            }
            for i in idx
        ]