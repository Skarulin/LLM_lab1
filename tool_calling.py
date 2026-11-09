import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from pydantic import ValidationError

from journal import RunLogger
from llm import build_llm
from schemas import ProductQuery
from search import search_products


@tool("search_products", args_schema=ProductQuery)
def search_products_tool(
    category: str,
    max_price: int | None = None,
    sort_by: str = "price_asc",
) -> str:
    """Ищет товары в каталоге SQLite по категории, максимальной цене и сортировке."""
    query = ProductQuery(category=category, max_price=max_price, sort_by=sort_by)
    return json.dumps(search_products(query), ensure_ascii=False)


PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Ты интерпретируешь запросы к каталогу товаров. "
            "Если нужен поиск, вызови инструмент search_products. "
            "Не пиши SQL и не придумывай товары.",
        ),
        ("human", "{query}"),
    ]
)


def run(queries: list[str]):
    logger = RunLogger("run_tools.jsonl")
    bound = build_llm(thinking=False).bind_tools([search_products_tool])

    results = []
    for user_query in queries:
        logger.log("tool_request_start", query=user_query)
        response = bound.invoke(PROMPT.format_messages(query=user_query))
        tool_calls = getattr(response, "tool_calls", []) or []

        if not tool_calls:
            logger.log("tool_not_called", query=user_query)
            results.append(
                {
                    "query": user_query,
                    "status": "no_tool_call",
                    "content": response.content,
                }
            )
            continue

        executed = []
        for call in tool_calls:
            try:
                query_obj = ProductQuery.model_validate(call.get("args", {}))
            except ValidationError as exc:
                logger.log("tool_args_invalid", query=user_query, error=str(exc)[:300])
                executed.append({"tool_call": call, "status": "invalid_args", "error": str(exc)})
                continue

            logger.log("tool_args_validated", query=user_query, args=query_obj.model_dump())
            result = search_products(query_obj)
            logger.log("tool_search_done", query=user_query, found=len(result["items"]))
            executed.append(
                {
                    "tool_call": call,
                    "validated_args": query_obj.model_dump(),
                    "search_result": result,
                }
            )

        results.append(
            {
                "query": user_query,
                "status": "ok",
                "model_content": response.content,
                "tool_calls": tool_calls,
                "executed": executed,
            }
        )

    return results

if __name__ == "__main__":
    for item in run(
        [
            "Найди ноутбуки дешевле 70 000 рублей",
            "Покажи самые дорогие смартфоны",
            "Найди холодильники",
        ]
    ):
        print(json.dumps(item, ensure_ascii=False, indent=2, default=str))