from langchain_ollama import ChatOllama

def create_llm(model: str, base_url: str):
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
        timeout=120,
    )
