import json
import re

import pandas as pd


def test_taxonomy_loaded():
    with open("data/processed/taxonomy.json") as f:
        tax = json.load(f)
    assert len(tax["terms"]) >= 200
    assert all("id" in t and "term" in t for t in tax["terms"])


def test_sample_data_quality():
    df = pd.read_csv("data/processed/listing_sample.csv")
    assert len(df) >= 500
    assert df["remarks"].str.len().min() > 50


def test_taxonomy_categories():
    with open("data/processed/taxonomy.json") as f:
        tax = json.load(f)

    categories = set(tax["categories"])
    term_categories = {term["category"] for term in tax["terms"]}

    assert len(categories) >= 8
    assert term_categories.issubset(categories)
    assert all(
        {"id", "term", "category", "aliases", "frequency", "ngram_type", "source"}.issubset(
            term
        )
        for term in tax["terms"]
    )


def test_sample_queries_loaded():
    with open("data/processed/sample_queries.json") as f:
        queries = json.load(f)

    assert len(queries) >= 50
    assert all(
        {"id", "query", "intent", "entities", "difficulty"}.issubset(query)
        for query in queries
    )
    assert {query["difficulty"] for query in queries} == {"simple", "medium", "hard"}
    assert len({query["intent"] for query in queries}) >= 8


def test_taxonomy_coverage():
    with open("data/processed/taxonomy.json") as f:
        tax = json.load(f)

    df = pd.read_csv("data/processed/listing_sample.csv")
    remarks = df["remarks"].dropna().astype(str).str.lower()
    terms = [
        term["term"].lower()
        for term in tax["terms"]
        if isinstance(term.get("term"), str) and len(term["term"]) >= 3
    ]

    pattern = re.compile("|".join(re.escape(term) for term in terms))
    covered = remarks.apply(lambda text: bool(pattern.search(text)))
    coverage = covered.mean()

    assert coverage >= 0.30
