"""Web search via SerpAPI with GPT-4o analysis."""

import requests

from src.config import AZURE_GPT_DEPLOYMENT, SERP_API_KEY, get_openai_client


def search_web(query: str, top_n: int = 3) -> dict | None:
    if not SERP_API_KEY:
        return None

    params = {
        "q": query,
        "api_key": SERP_API_KEY,
        "engine": "google",
    }

    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("organic_results", [])[:top_n]
    except Exception as e:
        print(f"  SerpAPI error: {e}")
        return None

    if not results:
        return None

    summaries = []
    links = []
    for idx, result in enumerate(results, 1):
        title = result.get("title", "No title")
        snippet = result.get("snippet", "No snippet")
        link = result.get("link", "")
        summaries.append(f"Result {idx}:\nTitle: {title}\nLink: {link}\nSnippet: {snippet}")
        if link:
            links.append(link)

    prompt = (
        "Summarize and analyze the following web search results in the context of "
        "urban safety incidents. Be concise (2-3 paragraphs):\n\n"
        + "\n\n".join(summaries)
    )

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=AZURE_GPT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are a research assistant that summarizes web search results with insight, focusing on urban safety relevance.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        analysis = response.choices[0].message.content.strip()
    except Exception as e:
        analysis = f"Analysis unavailable: {e}"

    return {
        "analysis": analysis,
        "links": links,
        "raw_results": results,
    }


if __name__ == "__main__":
    q = input("Search: ").strip()
    if q:
        result = search_web(q)
        if result:
            print(f"\n{result['analysis']}")
            print("\nLinks:", result["links"])
        else:
            print("No results (check SERP_API_KEY)")
