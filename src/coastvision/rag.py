from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


KNOWLEDGE_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.json"


def load_documents() -> list[dict[str, str]]:
    return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


def retrieve(query: str, limit: int = 3) -> list[dict[str, Any]]:
    documents = load_documents()
    corpus = [document["content"] for document in documents]
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(corpus + [query])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    ranked = scores.argsort()[::-1][:limit]
    return [{**documents[index], "score": float(scores[index])} for index in ranked]


def _extract_output_text(payload: dict[str, Any]) -> str:
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
    return ""


def answer_with_optional_llm(
    query: str,
    contexts: list[dict[str, Any]],
    *,
    allow_llm: bool = True,
) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    evidence = "\n\n".join(
        f"[{index}] {item['title']}\n{item['content']}\nFuente: {item['source']}"
        for index, item in enumerate(contexts, start=1)
    )
    if api_key and allow_llm:
        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "instructions": (
                    "Eres el asistente técnico de CoastVision. Responde en español, en no más de "
                    "180 palabras, usando solamente la evidencia recuperada. Distingue dato, supuesto "
                    "y limitación. Cita la evidencia como [1], [2] o [3]."
                ),
                "input": f"Pregunta: {query}\n\nEvidencia recuperada:\n{evidence}",
            },
            timeout=45,
        )
        response.raise_for_status()
        text = _extract_output_text(response.json())
        if text:
            return text, f"LLM: {model} + recuperación TF-IDF"

    evidence_summary = "\n".join(
        f"- **[{index}] {item['title']}:** {item['content']}"
        for index, item in enumerate(contexts, start=1)
    )
    answer = (
        f"**Respuesta basada en evidencia local:**\n\n{evidence_summary}\n\n"
        "El módulo recuperó los fragmentos más cercanos a la pregunta. Para una síntesis generativa, "
        "configure `OPENAI_API_KEY`; el resto del MVP funciona sin esa clave."
    )
    return answer, "Modo local: recuperación TF-IDF sin generación externa"
