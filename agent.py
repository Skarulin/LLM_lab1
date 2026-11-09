import time

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from pydantic import ValidationError

from journal import RunLogger
from llm import build_llm
from schemas import ProductQuery
from search import search_products

SYSTEM = """Ты — модуль интерпретации запросов к каталогу товаров.
Твоя задача — преобразовать запрос в параметры поиска.
Ты НЕ пишешь SQL и НЕ обращаешься к базе. Это делает обычная программа.

{format_instructions}

Правила:
1. Категория: laptop, smartphone, tablet или other.
2. Если товар не из этих трёх категорий — other.
3. max_price — целое число рублей или null. «70 тысяч» = 70000.
4. Если ограничение цены не задано, max_price = null.
5. sort_by: price_asc (сначала дешёвые) или price_desc (сначала дорогие).
6. По умолчанию sort_by = price_asc.
7. Отвечай ТОЛЬКО JSON-объектом. Без markdown, без пояснений, без SQL.
"""


class ProductAgent:
    def __init__(
        self,
        logger: RunLogger,
        llm=None,
        thinking: bool = False,
        max_attempts: int = 3,
        enable_search: bool = True,
    ):
        self.logger = logger
        self.llm = llm if llm is not None else build_llm(thinking=thinking)
        self.parser = PydanticOutputParser(pydantic_object=ProductQuery)
        self.max_attempts = max_attempts
        self.enable_search = enable_search
        self.attempt = 0
        self.search_calls = 0
        self.last_usage = None

        self.prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM), ("human", "{query}")]
        ).partial(format_instructions=self.parser.get_format_instructions())

        generation = (
            self.prompt
            | RunnableLambda(self._call_llm)
            | RunnableLambda(self._parse)
        )
        self.retrying = generation.with_retry(
            retry_if_exception_type=(OutputParserException, ValidationError),
            stop_after_attempt=max_attempts,
            wait_exponential_jitter=False,
        )

        if enable_search:
            self.chain = (
                RunnablePassthrough.assign(query_obj=self.retrying)
                | RunnablePassthrough.assign(
                    search_result=lambda x: self._search(x["query_obj"])
                )
            )
        else:
            self.chain = RunnablePassthrough.assign(query_obj=self.retrying)

    @staticmethod
    def _normalize(response: AIMessage):
        if isinstance(response.content, str):
            return response
        text = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response.content
        )
        return AIMessage(
            content=text,
            additional_kwargs=response.additional_kwargs,
            response_metadata=response.response_metadata,
            usage_metadata=response.usage_metadata,
        )

    def _call_llm(self, messages):
        self.attempt += 1
        self.logger.log("llm_start", attempt=self.attempt, max_attempts=self.max_attempts)
        started = time.perf_counter()
        response = self._normalize(self.llm.invoke(messages))
        elapsed = time.perf_counter() - started
        self.last_usage = getattr(response, "usage_metadata", None)
        self.logger.log(
            "llm_end",
            attempt=self.attempt,
            latency_s=round(elapsed, 3),
            usage=self.last_usage,
            content_len=len(response.content),
        )
        return response

    def _parse(self, response: AIMessage):
        try:
            query = self.parser.parse(response.content)
        except Exception as exc:
            self.logger.log(
                "parse_error",
                attempt=self.attempt,
                error_type=type(exc).__name__,
                cause_type=type(exc.__cause__).__name__ if exc.__cause__ else None,
                error=str(exc)[:300],
            )
            raise
        self.logger.log("parse_ok", attempt=self.attempt, params=query.model_dump())
        return query

    def _search(self, query: ProductQuery):
        self.search_calls += 1
        self.logger.log("params_validated", params=query.model_dump())
        self.logger.log("search_start", params=query.model_dump())
        result = search_products(query)
        self.logger.log(
            "search_done",
            status=result["status"],
            found=len(result["items"]),
            search_call=self.search_calls,
        )
        return result

    def ask(self, query: str):
        self.attempt = 0
        self.logger.log("request_start", query=query)
        try:
            output = self.chain.invoke({"query": query})
        except (OutputParserException, ValidationError) as exc:
            self.logger.log(
                "retry_exhausted",
                query=query,
                attempts=self.attempt,
                error_type=type(exc).__name__,
            )
            return {
                "status": "error",
                "message": f"Не удалось получить корректные параметры после {self.max_attempts} попыток.",
                "details": str(exc),
                "attempts": self.attempt,
                "search": None,
            }

        query_obj: ProductQuery = output["query_obj"]
        search_result = output.get("search_result")
        self.logger.log(
            "request_done",
            query=query,
            params=query_obj.model_dump(),
            found=len(search_result["items"]) if search_result else None,
        )
        return {
            "status": "ok",
            "query": query_obj,
            "search": search_result,
            "attempts": self.attempt,
            "usage": self.last_usage,
        }