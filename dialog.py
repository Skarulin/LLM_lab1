import time

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from journal import RunLogger
from llm import build_llm
from schemas import ProductQuery

STATE_SYSTEM = """Ты обновляешь параметры поиска по каталогу.

Текущие параметры (JSON):
{current_query}

Новая реплика пользователя:
{query}

Верни ПОЛНЫЙ обновлённый объект ProductQuery.
Если пользователь не меняет поле — сохрани его значение.
Если меняет только сортировку — не сбрасывай категорию и max_price.
Если меняет категорию — сохрани max_price и sort_by.

{format_instructions}

Только JSON-объект.
"""

HISTORY_SYSTEM = """Ты интерпретируешь запросы к каталогу с учётом истории.

История:
{history}

Новая реплика пользователя:
{query}

Верни ПОЛНЫЙ объект ProductQuery.

{format_instructions}

Только JSON-объект.
"""

class _Base:
    system: str
    def __init__(self, logger: RunLogger, llm=None):
        self.logger = logger
        self.llm = llm if llm is not None else build_llm(thinking=False)
        self.parser = PydanticOutputParser(pydantic_object=ProductQuery)
        self.prompt = ChatPromptTemplate.from_messages(
            [("system", self.system), ("human", "{query}")]
        ).partial(format_instructions=self.parser.get_format_instructions())
        self.attempt = 0
        self.last_usage = None

    def _call_llm(self, messages):
        self.attempt += 1
        self.logger.log("llm_start", attempt=self.attempt)
        started = time.perf_counter()
        response = self.llm.invoke(messages)
        elapsed = time.perf_counter() - started
        self.last_usage = getattr(response, "usage_metadata", None)
        self.logger.log(
            "llm_end",
            attempt=self.attempt,
            latency_s=round(elapsed, 3),
            usage=self.last_usage,
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
            )
            raise
        self.logger.log("parse_ok", attempt=self.attempt, params=query.model_dump())
        return query

    def _chain(self):
        return (
            self.prompt
            | RunnableLambda(self._call_llm)
            | RunnableLambda(self._parse)
        ).with_retry(
            retry_if_exception_type=(OutputParserException, ValidationError),
            stop_after_attempt=3,
            wait_exponential_jitter=False,
        )


class StatefulAgent(_Base):
    system = STATE_SYSTEM
    def __init__(self, logger: RunLogger, llm=None):
        super().__init__(logger, llm)
        self.state: ProductQuery | None = None

    def ask(self, utterance: str):
        self.attempt = 0
        current = self.state.model_dump_json() if self.state else "null"
        self.logger.log("state_turn_start", utterance=utterance, current=current)
        self.state = self._chain().invoke({"query": utterance, "current_query": current})
        self.logger.log("state_updated", params=self.state.model_dump())
        return self.state

class HistoryAgent(_Base):
    system = HISTORY_SYSTEM
    def __init__(self, logger: RunLogger, llm=None):
        super().__init__(logger, llm)
        self.history: list[dict] = []

    def ask(self, utterance: str):
        self.attempt = 0
        history = "\n".join(f"{t['role']}: {t['content']}" for t in self.history) or "(пусто)"
        query = self._chain().invoke({"query": utterance, "history": history})
        self.history.append({"role": "Пользователь", "content": utterance})
        self.history.append({"role": "Ассистент", "content": query.model_dump_json()})
        return query