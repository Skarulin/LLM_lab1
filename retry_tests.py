from langchain_core.language_models import FakeListChatModel

from agent import ProductAgent
from journal import RunLogger
from schemas import ProductQuery
from search import search_products
from langchain_core.output_parsers import PydanticOutputParser


def _agent(responses: list[str], max_attempts: int, log: str):
    fake = FakeListChatModel(responses=responses, sleep=0)
    return ProductAgent(
        logger=RunLogger(log),
        llm=fake,
        max_attempts=max_attempts,
        enable_search=True,
    )

def test_retry_success():
    agent = _agent(
        responses=[
            '{"category": "laptop", "max_price": "oops"}',
            '{"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}',
        ],
        max_attempts=3,
        log="run_fake_retry_success.jsonl",
    )
    result = agent.ask("Ноутбуки до 70 тысяч")
    assert result["status"] == "ok"
    assert result["attempts"] == 2
    assert agent.search_calls == 1
    assert len(result["search"]["items"]) == 3
    print(f"retry success: attempts={result['attempts']}, search_calls={agent.search_calls}")

def test_no_retry_fails():
    agent = _agent(
        responses=[
            '{"category": "laptop", "max_price": "oops"}',
            '{"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}',
        ],
        max_attempts=1,
        log="run_fake_no_retry.jsonl",
    )
    result = agent.ask("Ноутбуки до 70 тысяч")
    assert result["status"] == "error"
    assert agent.search_calls == 0
    print(f"no retry: search_calls={agent.search_calls}")


def test_all_attempts_fail():
    agent = _agent(
        responses=[
            "not json",
            '{"category": "fridge", "max_price": 70000, "sort_by": "price_asc"}',
            '{"category": "laptop", "max_price": -100, "sort_by": "price_asc"}',
        ],
        max_attempts=3,
        log="run_fake_all_fail.jsonl",
    )
    result = agent.ask("Холодильники")
    assert result["status"] == "error"
    assert result["attempts"] == 3
    assert agent.search_calls == 0
    print(f"all fail: attempts={result['attempts']}, search_calls={agent.search_calls}")


def analyze_parser_errors():
    parser = PydanticOutputParser(pydantic_object=ProductQuery)
    samples = {
        "malformed_json":  '{"category": "laptop", "max_price": 70000',
        "invalid_enum":    '{"category": "fridge", "max_price": 70000, "sort_by": "price_asc"}',
        "negative_price":  '{"category": "laptop", "max_price": -100, "sort_by": "price_asc"}',
        "wrong_type":      '{"category": "laptop", "max_price": "много", "sort_by": "price_asc"}',
    }
    for name, raw in samples.items():
        try:
            parser.parse(raw)
            print(f"{name}: неожиданно валидно")
        except Exception as exc:
            cause = type(exc.__cause__).__name__ if exc.__cause__ else None
            print(f"{name}: {type(exc).__name__} (cause={cause})")


if __name__ == "__main__":
    analyze_parser_errors()
    test_retry_success()
    test_no_retry_fails()
    test_all_attempts_fail()