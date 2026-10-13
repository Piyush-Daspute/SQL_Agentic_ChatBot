from retrieval import SchemaRetriever

def test_retrieval_returns_relevant_schema():
    catalog = {
        "tables": {
            "sales": {
                "columns": [{"name": "Sale_Date", "type": "TEXT"},
                            {"name": "Revenue_INR", "type": "INTEGER"}],
                "primary_key": ["Sale_ID"],
                "row_count": 3,
            },
            "employees": {
                "columns": [{"name": "Department", "type": "TEXT"}],
                "primary_key": ["Employee_ID"],
                "row_count": 5,
            },
        },
        "relationships": [],
        "signature": "test",
    }
    retriever = SchemaRetriever(catalog)
    docs = retriever.retrieve("sales revenue by date", top_k=1)
    assert docs
    assert "sales" in docs[0].lower()
