"""RAG engine: retrieve context from Azure AI Search and generate answers with GPT-4o."""

from src.config import AZURE_GPT_DEPLOYMENT, get_openai_client
from src.search.hybrid_search import hybrid_search
from src.telemetry import trace_rag_query

SYSTEM_PROMPT = (
    "You are the Contoso Smart Incident Assistant, helping city officials "
    "and emergency response teams analyze urban safety incidents. "
    "Use the retrieved context to provide accurate, actionable answers. "
    "When citing sources, mention the document type and filename. "
    "If the context does not contain enough information, say so clearly."
)


class RAGEngine:
    def __init__(self, max_history: int = 10):
        self.client = get_openai_client()
        self.chat_history: list[dict] = []
        self.max_history = max_history

    def query(self, user_question: str, top_k: int = 5) -> dict:
        with trace_rag_query(user_question) as trace:
            trace.start_retrieval()
            docs = hybrid_search(user_question, top_k=top_k)
            trace.set_retrieval(docs)

            prompt = self._build_prompt(user_question, docs)

            trace.start_generation()
            answer = self._generate(prompt)
            trace.set_generation(answer)

        self._update_history(user_question, answer)
        return {
            "answer": answer,
            "sources": docs,
            "query": user_question,
        }

    def _build_prompt(self, query: str, docs: list[dict]) -> str:
        context = "\n\n---\n\n".join(
            f"[{doc.get('type', 'unknown')}] {doc.get('source', 'unknown')}:\n{doc.get('content', '')}"
            for doc in docs
        )

        history_lines = "\n\n".join(
            f"User: {entry['query']}\nAssistant: {entry['answer']}"
            for entry in self.chat_history
        )

        return (
            f"Context:\n{context}\n\n"
            f"Chat History:\n{history_lines}\n\n"
            f"Question:\n{query}\n\n"
            f"Answer:"
        )

    def _generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=AZURE_GPT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()

    def _update_history(self, query: str, answer: str):
        self.chat_history.append({"query": query, "answer": answer})
        if len(self.chat_history) > self.max_history:
            self.chat_history.pop(0)

    def clear_history(self):
        self.chat_history.clear()


if __name__ == "__main__":
    from src.config import validate_env
    validate_env()
    engine = RAGEngine()
    print("Contoso Smart Incident Assistant (type 'exit' to quit)\n")
    while True:
        q = input("Ask: ").strip()
        if q.lower() == "exit":
            break
        result = engine.query(q)
        print(f"\n{result['answer']}\n")
        if result["sources"]:
            print("Sources:", ", ".join(s.get("source", "?") for s in result["sources"]))
        print()
