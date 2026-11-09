from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from llm import build_llm

SYSTEM = (
    "Ты — классификатор товаров. Определи категорию товара по запросу. "
    "Ответь ОДНИМ словом на языке {language}: laptop, smartphone, tablet или other. "
    "Если товар не относится к ноутбукам, смартфонам или планшетам — other. "
    "Без пояснений, без markdown, только одно слово."
)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "{query}"),
    ]
)
parser = StrOutputParser()

def build_chain():
    return prompt | build_llm(thinking=False) | parser

def demo_types(chain, query: str = "Хочу ноутбук до 70 тысяч", language: str = "русском"):
    llm = build_llm(thinking=False)
    messages = prompt.format_messages(query=query, language=language)

    raw = llm.invoke(messages)
    print("llm.invoke:", type(raw).__name__, raw.content)

    text = chain.invoke({"query": query, "language": language})
    print("chain.invoke:", type(text).__name__, text)

def demo_batch(chain):
    queries = [
        {"query": "Ноутбук для учёбы, бюджет небольшой", "language": "русском"},
        {"query": "Смартфон с хорошей камерой", "language": "русском"},
        {"query": "Планшет для рисования", "language": "русском"},
        {"query": "Двухкамерный холодильник", "language": "русском"},
    ]
    results = chain.batch(queries, config={"max_concurrency": 2})
    for q, r in zip(queries, results):
        print(q['query'], '->', r)

if __name__ == "__main__":
    chain = build_chain()
    demo_types(chain)
    demo_batch(chain)