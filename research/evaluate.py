"""
Скрипт оценки качества RAG-агента FinBridge.

Метрики:
  - relevance_score     : доля ожидаемых источников, найденных в retrieved docs (Recall)
  - factual_score       : доля key_facts из эталона, присутствующих в ответе агента
  - is_hallucination    : флаг галлюцинации (подробнее — см. detect_hallucination)
  - registration_ms     : время от отправки вопроса до получения task_id
  - ttft_ms             : время от отправки вопроса до первого токена (TTFT)
  - total_ms            : полное время от отправки до события "done"

Использование:
  python evaluate.py                                 # все 50 вопросов
  python evaluate.py --ids 1,5,41                    # только указанные id
  python evaluate.py --category hallucination_trap   # только категория
  python evaluate.py --api-url http://localhost:8000 # другой хост
  python evaluate.py --delay 1.5                     # пауза между вопросами (сек)

Атрошенко Б. С.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
DATASET_PATH = SCRIPT_DIR / "test_dataset.json"
RESULTS_DIR = SCRIPT_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Фразы, указывающие что модель призналась в незнании
REJECTION_PHRASES = [
    "не знаю", "нет информации", "не нашёл", "не нашел",
    "не упоминается", "не содержится", "в документах", "не могу найти",
    "нет данных", "не указано", "не имею информации", "не могу ответить",
    "недоступн", "отсутствует", "нет сведений", "не предоставлен",
    "не описан", "не задокументирован", "нет такой информации",
    "i don't", "not found", "not available", "not mentioned",
]

def create_session(base_url: str) -> str:
    """Создать новую сессию, вернуть session_id."""

    resp = requests.post(f"{base_url}/chat/sessions", timeout=10)
    resp.raise_for_status()
    return resp.json()["user_identity"]


def submit_question(base_url: str, session_id: str, question: str) -> tuple[str, float]:
    """
    Отправить вопрос, вернуть (task_id, registration_ms).
    registration_ms — время от отправки до получения task_id.
    """

    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/chat/create_insight_stream",
        json={"query": question},
        headers={"X-Session-Id": session_id},
        timeout=15,
    )
    resp.raise_for_status()
    registration_ms = (time.perf_counter() - t0) * 1000
    task_id = resp.json()["task_id"]
    return task_id, registration_ms


def stream_result(base_url: str, task_id: str, t_submit: float, timeout: int = 300):
    """
    Стриминг SSE-ответа агента.

    Возвращает:
      answer        : полный текстовый ответ
      sources       : список документов-источников [{"content": ..., "metadata": ...}]
      ttft_ms       : время от t_submit до первого токена
      total_ms      : время от t_submit до события "done"
    """

    answer = ""
    sources = []
    ttft_ms = None

    with requests.get(
            f"{base_url}/chat/stream/{task_id}",
            stream=True,
            timeout=timeout,
    ) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            if payload["type"] == "token":
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - t_submit) * 1000
                answer += payload["content"]
            elif payload["type"] == "done":
                sources = payload.get("sources", [])
                break

    total_ms = (time.perf_counter() - t_submit) * 1000
    return answer, sources, ttft_ms, total_ms


def compute_relevance_score(expected_docs: list[str], retrieved_sources: list[dict]) -> float | None:
    """
    Recall: доля ожидаемых документов, найденных в retrieved docs.
    Сравнение по basename файла.
    None если expected_docs пуст (small_talk или hallucination_trap без источников).
    """

    if not expected_docs:
        return None

    retrieved_basenames = set()
    for src in retrieved_sources:
        path = src.get("metadata", {}).get("source", "")
        if path:
            retrieved_basenames.add(os.path.basename(path))

    found = sum(1 for doc in expected_docs if doc in retrieved_basenames)
    return round(found / len(expected_docs), 3)


def compute_factual_score(key_facts: list[str], answer: str) -> float:
    """
    Доля key_facts, присутствующих в ответе агента (case-insensitive).
    Если key_facts пуст — возвращает 1.0 если ответ непустой, иначе 0.0.
    """

    if not key_facts:
        return 1.0 if answer.strip() else 0.0

    answer_lower = answer.lower()
    found = sum(1 for fact in key_facts if fact.lower() in answer_lower)
    return round(found / len(key_facts), 3)


def detect_hallucination(category: str, answer: str, factual_score: float) -> bool:
    """
    Эвристика обнаружения галлюцинаций.

    hallucination_trap: если модель дала длинный уверенный ответ без признания незнания — галлюцинация.
    Остальные: если factual_score = 0.0 при длинном ответе без оговорки — вероятная галлюцинация.
    """

    answer_lower = answer.lower()
    seems_rejected = any(phrase in answer_lower for phrase in REJECTION_PHRASES)

    if category == "hallucination_trap":
        # Правильный ответ: признать что информации нет.
        # Если ответ длинный и конкретный без такого признания — галлюцинация.
        return len(answer) > 150 and not seems_rejected

    # Для knowledge_base категорий: 0 совпавших фактов + длинный уверенный ответ = подозрение.
    if factual_score == 0.0 and len(answer) > 200 and not seems_rejected:
        return True

    return False


_COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def _c(text: str, color: str) -> str:
    return f"{_COLORS[color]}{text}{_COLORS['reset']}"


def print_question_result(q: dict, result: dict) -> None:
    score_color = "green" if result["factual_score"] >= 0.6 else ("yellow" if result["factual_score"] >= 0.3 else "red")
    rel_str = f"{result['relevance_score']:.2f}" if result["relevance_score"] is not None else "N/A"
    hall_str = _c("⚠ HALLUCINATION", "red") if result["is_hallucination"] else _c("✓ OK", "green")

    qid = q["id"]
    qcat = q["category"].upper()
    detected = result["detected_intent"]
    factual_str = f"{result['factual_score']:.2f}"
    ttft_val = result["ttft_ms"]
    ttft_disp = f"{ttft_val:.0f}ms" if ttft_val else "—ms"
    total_disp = f"{result['total_ms']:.0f}ms"

    print(f"\n{'─' * 70}")
    print(f"{_c(f'[{qid:02d}] {qcat}', 'bold')} | intent={detected}")
    print(f"Q: {q['question'][:90]}")
    print(
        f"Factual: {_c(factual_str, score_color)} | Relevance: {rel_str} | TTFT: {ttft_disp} | Total: {total_disp} | {hall_str}")
    if result.get("error"):
        print(_c(f"ERROR: {result['error']}", "red"))
    else:
        preview = result["answer"][:200].replace("\n", " ")
        print(f"A: {preview}{'...' if len(result['answer']) > 200 else ''}")
        if result["retrieved_doc_names"]:
            print(f"Sources: {', '.join(result['retrieved_doc_names'][:5])}")


def print_summary(results: list[dict]) -> None:
    """Печать итоговой сводки по всем метрикам."""

    total = len(results)
    errors = [r for r in results if r.get("error")]

    kb_results = [r for r in results if r.get("expected_intent") == "knowledge_base" and not r.get("error")]
    st_results = [r for r in results if r.get("expected_intent") == "small_talk" and not r.get("error")]
    trap_results = [r for r in results if r.get("category") == "hallucination_trap" and not r.get("error")]

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    # Relevance только для тех кто прошёл knowledge_base и у кого relevance != None
    rel_vals = [r["relevance_score"] for r in kb_results if r["relevance_score"] is not None]
    factual_kb = [r["factual_score"] for r in kb_results]
    factual_st = [r["factual_score"] for r in st_results]

    ttft_all = [r["ttft_ms"] for r in results if r.get("ttft_ms")]
    total_ms_all = [r["total_ms"] for r in results if r.get("total_ms") and not r.get("error")]
    reg_ms_all = [r["registration_ms"] for r in results if r.get("registration_ms")]

    hallucinations = [r for r in trap_results if r["is_hallucination"]]
    hallucinations_other = [r for r in results if
                            r.get("is_hallucination") and r.get("category") != "hallucination_trap"]

    print(f"\n{'═' * 70}")
    print(_c("СВОДНАЯ ОЦЕНКА RAG-АГЕНТА FINBRIDGE", "bold"))
    print(f"{'═' * 70}")
    print(f"Вопросов обработано: {total - len(errors)}/{total} (ошибок: {len(errors)})")
    print()

    print(_c("── КАЧЕСТВО ОТВЕТОВ ──────────────────────────────", "cyan"))
    if factual_kb:
        print(
            f"  Factual score (knowledge_base, avg):  {_c(f'{avg(factual_kb):.3f}', 'green' if avg(factual_kb) >= 0.6 else 'yellow')}")
        print(f"  Factual score (small_talk, avg):      {avg(factual_st):.3f}")
    if rel_vals:
        print(
            f"  Relevance / Document Recall (avg):    {_c(f'{avg(rel_vals):.3f}', 'green' if avg(rel_vals) >= 0.5 else 'yellow')}")

    print()
    print(_c("── ГАЛЛЮЦИНАЦИИ ──────────────────────────────────", "cyan"))
    trap_total = len(trap_results)
    trap_hall = len(hallucinations)
    print(f"  Hallucination traps: {trap_total} вопросов, {trap_hall} галлюцинаций")
    if trap_total:
        print(
            f"  Hallucination rate (trap): {_c(f'{trap_hall / trap_total:.1%}', 'red' if trap_hall / trap_total > 0.2 else 'green')}")
    print(f"  Вероятные галлюцинации (non-trap):    {len(hallucinations_other)}")

    print()
    print(_c("── ПРОИЗВОДИТЕЛЬНОСТЬ ────────────────────────────", "cyan"))
    if reg_ms_all:
        print(f"  Task registration (avg):  {avg(reg_ms_all):.0f} ms")
        print(f"  Task registration (p95):  {sorted(reg_ms_all)[int(len(reg_ms_all) * 0.95)]:.0f} ms")
    if ttft_all:
        print(f"  TTFT (avg):               {avg(ttft_all):.0f} ms")
        print(f"  TTFT (p50):               {sorted(ttft_all)[len(ttft_all) // 2]:.0f} ms")
        print(f"  TTFT (p95):               {sorted(ttft_all)[int(len(ttft_all) * 0.95)]:.0f} ms")
    if total_ms_all:
        print(f"  Total time (avg):         {avg(total_ms_all):.0f} ms")
        print(f"  Total time (p95):         {sorted(total_ms_all)[int(len(total_ms_all) * 0.95)]:.0f} ms")

    print()
    print(_c("── ОЦЕНКА ПО КАТЕГОРИЯМ ──────────────────────────", "cyan"))
    categories = ["small_talk", "easy_factual", "medium", "complex", "hallucination_trap"]
    for cat in categories:
        cat_results = [r for r in results if r.get("category") == cat and not r.get("error")]
        if not cat_results:
            continue
        f_avg = avg([r["factual_score"] for r in cat_results])
        r_avg = avg([r["relevance_score"] for r in cat_results if r["relevance_score"] is not None])
        h_cnt = sum(1 for r in cat_results if r["is_hallucination"])
        r_str = f"{r_avg:.2f}" if any(r["relevance_score"] is not None for r in cat_results) else " N/A"
        print(f"  {cat:<20s}  n={len(cat_results):2d}  factual={f_avg:.2f}  relevance={r_str}  hall={h_cnt}")

    if errors:
        print()
        print(_c(f"── ОШИБКИ ({len(errors)} шт.) ────────────────────────────────", "red"))
        for r in errors:
            print(f"  Q{r['id']}: {r['error']}")

    print(f"{'═' * 70}")

def run_evaluation(
        base_url: str,
        questions: list[dict],
        delay: float = 1.0,
        verbose: bool = True,
) -> list[dict]:
    """Прогнать все вопросы через агента, вернуть список результатов."""

    results = []

    for idx, q in enumerate(questions):
        if verbose:
            print(f"\n[{idx + 1}/{len(questions)}] Q{q['id']}: {q['question'][:60]}...")

        result = {
            "id": q["id"],
            "question": q["question"],
            "category": q["category"],
            "expected_intent": q["expected_intent"],
            "answer": "",
            "retrieved_doc_names": [],
            "registration_ms": 0.0,
            "ttft_ms": None,
            "total_ms": 0.0,
            "relevance_score": None,
            "factual_score": 0.0,
            "is_hallucination": False,
            "detected_intent": "unknown",
            "error": None,
        }

        try:
            # Новая сессия на каждый вопрос — чтобы история не влияла
            session_id = create_session(base_url)

            # Отправить вопрос
            t_submit = time.perf_counter()
            task_id, reg_ms = submit_question(base_url, session_id, q["question"])
            result["registration_ms"] = round(reg_ms, 1)

            # Стриминг ответа
            answer, sources, ttft_ms, total_ms = stream_result(base_url, task_id, t_submit)
            result["answer"] = answer
            result["ttft_ms"] = round(ttft_ms, 1) if ttft_ms else None
            result["total_ms"] = round(total_ms, 1)

            # Имена источников
            doc_names = []
            for src in sources:
                path = src.get("metadata", {}).get("source", "")
                if path:
                    doc_names.append(os.path.basename(path))
            result["retrieved_doc_names"] = list(dict.fromkeys(doc_names))  # uniq, preserve order

            # Определяем обнаруженный intent по наличию источников
            result["detected_intent"] = "knowledge_base" if sources else "small_talk"

            # Оценки
            result["relevance_score"] = compute_relevance_score(q["source_docs"], sources)
            result["factual_score"] = compute_factual_score(q["key_facts"], answer)
            result["is_hallucination"] = detect_hallucination(q["category"], answer, result["factual_score"])

        except requests.exceptions.ConnectionError:
            result["error"] = f"Нет соединения с сервером {base_url}"
        except requests.exceptions.Timeout:
            result["error"] = "Timeout"
        except Exception as exc:
            result["error"] = str(exc)

        results.append(result)

        if verbose:
            print_question_result(q, result)

        if delay > 0 and idx < len(questions) - 1:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(description="Оценка RAG-агента FinBridge")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Базовый URL API")
    parser.add_argument("--ids", help="Запустить только указанные id (через запятую), напр. 1,5,41")
    parser.add_argument("--category", help="Запустить только вопросы указанной категории")
    parser.add_argument("--delay", type=float, default=1.5, help="Пауза между вопросами (сек)")
    parser.add_argument("--no-verbose", action="store_true", help="Не выводить ответы построчно")
    parser.add_argument("--output", help="Путь к JSON файлу результатов (по умолчанию auto)")
    args = parser.parse_args()

    # Загрузить датасет
    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    questions = dataset["questions"]

    # Фильтрация
    if args.ids:
        target_ids = {int(x.strip()) for x in args.ids.split(",")}
        questions = [q for q in questions if q["id"] in target_ids]
    if args.category:
        questions = [q for q in questions if q["category"] == args.category]

    if not questions:
        print("Нет вопросов для запуска. Проверь --ids / --category.")
        sys.exit(1)

    print(_c(f"\nЗапуск оценки: {len(questions)} вопросов → {args.api_url}", "bold"))
    print(f"Датасет: {DATASET_PATH}")
    print(f"Задержка между вопросами: {args.delay}s\n")

    # Проверяем доступность сервера
    try:
        requests.get(f"{args.api_url}/docs", timeout=5)
    except Exception:
        print(_c(f"⚠ Сервер {args.api_url} недоступен. Убедись что система запущена.", "red"))
        print("  Подсказка: docker-compose up")
        sys.exit(1)

    results = run_evaluation(
        base_url=args.api_url,
        questions=questions,
        delay=args.delay,
        verbose=not args.no_verbose,
    )

    # Печать итоговой сводки
    print_summary(results)

    # Сохранить JSON
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.output) if args.output else RESULTS_DIR / f"eval_{ts}.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "api_url": args.api_url,
        "total_questions": len(results),
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nРезультаты сохранены: {out_path}")


if __name__ == "__main__":
    main()
