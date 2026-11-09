import argparse
import json
import time

from agent import ProductAgent
from basic_chain import build_chain, demo_batch, demo_types
from db import init_db
from dialog import HistoryAgent, StatefulAgent
from journal import RunLogger
from search import search_products
from tool_calling import run as run_tools


PART2 = [
    "Найди ноутбуки дешевле 70 000 рублей",
    "Покажи самые дорогие смартфоны",
    "Хочу посмотреть планшеты",
    "Покажи ноутбуки до 50 тысяч",
    "Найди холодильники",
    "Хочу что-нибудь недорогое для учёбы",
    "Покажи ноутбуки, но чтобы не как у меня",
]

PART3 = PART2 + [
    "Смартфоны дешевле 30 тысяч",
    "Самые дорогие планшеты",
    "Ноутбуки до 90 тысяч",
]

def part1():
    chain = build_chain()
    demo_types(chain)
    demo_batch(chain)

def part2():
    agent = ProductAgent(logger=RunLogger("run_part2.jsonl"), enable_search=False)
    for text in PART2:
        result = agent.ask(text)
        print(f"\n{text}")
        if result["status"] == "ok":
            print(json.dumps(result["query"].model_dump(), ensure_ascii=False))
            print("attempts:", result["attempts"])
        else:
            print(result["message"])

def part2_thinking():
    logger = RunLogger("run_part2_thinking.jsonl")
    for thinking in (False, True):
        agent = ProductAgent(logger=logger, thinking=thinking, enable_search=False)
        for text in PART2[-2:]:
            started = time.perf_counter()
            result = agent.ask(text)
            elapsed = time.perf_counter() - started
            params = result["query"].model_dump() if result["status"] == "ok" else result["message"]
            print(f"thinking={thinking} | {text} | {params} | "
                  f"{elapsed:.2f}s | usage={result.get('usage')}")

def part3():
    agent = ProductAgent(logger=RunLogger("run_part3.jsonl"), enable_search=True)
    for text in PART3:
        result = agent.ask(text)
        print(f"\n{text}")
        if result["status"] != "ok":
            print("ОШИБКА:", result["message"])
            continue
        print("Параметры:", result["query"].model_dump())
        print("Статус:", result["search"]["status"], "| найдено:", len(result["search"]["items"]))
        for item in result["search"]["items"]:
            print(f"  - {item['name']}: {item['price']} руб.")

def part4():
    from retry_tests import (
        analyze_parser_errors,
        test_all_attempts_fail,
        test_no_retry_fails,
        test_retry_success,
    )

    analyze_parser_errors()
    test_retry_success()
    test_no_retry_fails()
    test_all_attempts_fail()


def part5():
    logger = RunLogger("run_part5.jsonl")
    state_agent = StatefulAgent(logger=logger)
    history_agent = HistoryAgent(logger=logger)

    dialogue = [
        "Покажи ноутбуки до 80 тысяч",
        "А сначала дорогие?",
        "А что есть среди смартфонов?",
    ]

    for label, agent in (("STATE", state_agent), ("HISTORY", history_agent)):
        print(f"\n {label}")
        for utterance in dialogue:
            q = agent.ask(utterance)
            res = search_products(q)
            print(f"{utterance}\n  -> {q.model_dump()} | найдено: {len(res['items'])} | "
                  f"usage: {agent.last_usage}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "part",
        choices=["init-db", "part1", "part2", "part2-thinking", "part3", "part4", "part5", "tools"],
    )
    args = parser.parse_args()

    if args.part == "init-db":
        init_db()
    elif args.part == "part1":
        part1()
    elif args.part == "part2":
        part2()
    elif args.part == "part2-thinking":
        part2_thinking()
    elif args.part == "part3":
        part3()
    elif args.part == "part4":
        part4()
    elif args.part == "part5":
        part5()
    elif args.part == "tools":
        for item in run_tools(PART2[:5]):
            print(json.dumps(item, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()