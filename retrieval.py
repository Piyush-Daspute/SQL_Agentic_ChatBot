from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SchemaRetriever:
    """Small local retrieval index over live table/column/relationship metadata."""
    def __init__(self, catalog):
        self.catalog = catalog
        self.documents = []
        self.doc_table = []
        for table_name, details in catalog.get("tables", {}).items():
            col_text = "; ".join(
                f"{c['name']} ({c['type']})" for c in details.get("columns", [])
            )
            pk_text = ", ".join(details.get("primary_key", []))
            related = [
                f"{r['from_table']}.{r['from_column']} -> {r['to_table']}.{r['to_column']}"
                for r in catalog.get("relationships", [])
                if r.get("from_table") == table_name or r.get("to_table") == table_name
            ]
            doc = (
                f"Table {table_name}. Columns: {col_text}. "
                f"Primary key: {pk_text}. Relationships: {'; '.join(related)}"
            )
            self.documents.append(doc)
            self.doc_table.append(table_name)
        self.vectorizer = None
        self.matrix = None
        if self.documents:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            self.matrix = self.vectorizer.fit_transform(self.documents)

    def retrieve(self, question, top_k=4):
        if not self.documents:
            return []
        if self.vectorizer is None or self.matrix is None:
            return self.documents[:top_k]
        query = self.vectorizer.transform([question])
        scores = cosine_similarity(query, self.matrix).ravel()
        order = scores.argsort()[::-1][:min(top_k, len(scores))]
        # Always include exact table-name matches even if lexical similarity is weak.
        q = question.lower()
        chosen = list(order)
        for i, table_name in enumerate(self.doc_table):
            if table_name.lower() in q and i not in chosen:
                chosen.insert(0, i)
        return [self.documents[i] for i in chosen[:top_k]]

    def table_names(self):
        return list(self.catalog.get("tables", {}).keys())
