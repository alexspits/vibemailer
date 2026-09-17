"""Подбор клиентов панели под получателя: по почте и базовому имени.

Одного и того же человека на разных панелях называли по-разному и в разное время:
`SolovArt1`, `artem_solo1de`, `artemsolo1`, `artem_solo1chain` — это всё он. Разделители
разные, порядок имени и фамилии разный, к имени липнут номер устройства и ключ сервера.
Поэтому сравнивать строки целиком бесполезно: нужно приводить к общему виду и мерить
похожесть несколькими способами сразу.

Меры три, берётся лучшая:

* **по словам** — `solov` и `soloviev` считаются одним словом, если общее начало не
  короче четырёх букв. Ловит перестановку («Соловьёв Артём» против `artem_solo`) и
  разные разделители, потому что слова сравниваются как множество, а не по порядку.
* **по самой длинной общей подстроке** — для слипшихся имён, где слов не выделить:
  `kboyko` и `boykokr` делят `boyko`, и это почти вся длина каждого.
* **по парам букв** — запасная мера на опечатки и сокращения, где двум первым не за что
  зацепиться.

Матчер ничего не решает сам: он возвращает оценку, а привязывает человек. Ошибиться тут
дороже, чем не найти: чужая привязка — это доступ одного получателя, уехавший другому.
Из этого же два ограничения на «отметить заранее»:

* совпадения одного лишь базового имени (`aleksandr-v`) недостаточно — имя общее у
  многих, а фамилия в нём сокращена до буквы. Такой кандидат показывается, но галочку
  не получает, пока его не подтвердит почта или введённая руками подсказка;
* если наверх вышли разные люди (`LitovkaE1` и `LitovkaP1`), заранее не отмечается
  никто: различить их может только человек.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

# Ниже этого совпадения кандидат не показывается: шум только мешает выбирать.
MIN_SCORE = 0.55

# Выше этого — отмечаем галочкой заранее. Порог подобран по живым панелям: «К. Бойко»
# в почте против `boykokr` на панели даёт 0.83, и это уже уверенное совпадение, а вот
# совпадения по одному лишь имени упираются в потолок ниже и галочки не получают.
CONFIDENT_SCORE = 0.82

# Потолок для совпадений, которые держатся только на базовом имени получателя.
# Ниже порога уверенности — такой кандидат виден, но не отмечен.
WEAK_SCORE_CAP = 0.8

# Насколько две основы могут разойтись по длине, оставаясь одним человеком:
# `kireev` и `kireevs` — один, `litovkae` и `litovkap` — уже разные.
_BASE_SLACK = 2

# Общее начало двух слов, начиная с которого они считаются одним и тем же словом.
_MIN_PREFIX = 4

# Слова короче — не признак: `de`, `p`, `1` встречаются у всех подряд.
_MIN_TOKEN = 3

# Границы слов: разделители, смена регистра (SolovArt) и цифры (solo1de).
_SPLIT_RE = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")


@dataclass(frozen=True)
class Candidate:
    """Клиент панели, похожий на получателя."""

    name: str
    score: float
    # Отметить ли галочкой заранее. Это не просто «оценка высокая»: учитывается ещё и
    # то, не спорят ли за первое место разные люди.
    suggested: bool = False


def _parts(value: str, stop_words: frozenset[str], min_length: int) -> list[str]:
    """Куски строки без разделителей, цифр и служебных хвостов."""
    parts = (part.lower() for part in _SPLIT_RE.split(value) if part)

    return [
        part
        for part in parts
        if len(part) >= min_length and not part.isdigit() and part not in stop_words
    ]


def _tokens(value: str, stop_words: frozenset[str]) -> list[str]:
    """Значимые слова строки. Короткие отброшены: `de`, `p`, `1` есть у всех подряд."""
    return _parts(value, stop_words, _MIN_TOKEN)


def _normalized(value: str) -> str:
    """Строка без разделителей и цифр — для сравнения слипшихся имён."""
    return re.sub(r"[^a-z]", "", value.lower())


def _shared_prefix(first: str, second: str) -> int:
    """Длина общего начала двух слов."""
    limit = min(len(first), len(second))
    length = 0

    while length < limit and first[length] == second[length]:
        length += 1

    return length


def _variants(word: str) -> list[str]:
    """Слово и оно же без инициала, приклеенного спереди или сзади.

    `kboyko` — это «К. Бойко», а на панели тот же человек записан как `boykokr`.
    Без этого такие пары не сходятся: общего начала у них нет вовсе.
    """
    if len(word) <= _MIN_PREFIX:
        return [word]

    return [word, word[1:], word[:-1]]


def _token_score(query: list[str], candidate: list[str]) -> float:
    """Доля букв, совпавших по словам, от более короткой из двух сторон.

    Считаем именно буквы, а не слова: иначе клиент с единственным коротким словом
    совпадал бы с кем угодно, у кого это слово есть.
    """
    if not query or not candidate:
        return 0.0

    matched = 0

    for word in query:
        best = max(
            (_shared_prefix(variant, other) for variant in _variants(word) for other in candidate),
            default=0,
        )

        if best >= _MIN_PREFIX or (best == len(word) and best >= _MIN_TOKEN):
            matched += best

    return matched / min(sum(map(len, query)), sum(map(len, candidate)))


def _substring_score(query: str, candidate: str) -> float:
    """Длина самой длинной общей подстроки от более короткой из строк."""
    if not query or not candidate:
        return 0.0

    match = SequenceMatcher(None, query, candidate, autojunk=False).find_longest_match(
        0, len(query), 0, len(candidate)
    )

    if match.size < _MIN_PREFIX:
        return 0.0

    return match.size / min(len(query), len(candidate))


def _bigrams(value: str) -> set[str]:
    return {value[i : i + 2] for i in range(len(value) - 1)}


def _bigram_score(query: str, candidate: str) -> float:
    """Похожесть по парам букв: не зависит от порядка слов, терпит опечатки."""
    first, second = _bigrams(query), _bigrams(candidate)

    if not first or not second:
        return 0.0

    return 2 * len(first & second) / (len(first) + len(second))


def _base(name: str, stop_words: frozenset[str]) -> str:
    """Имя без номера устройства и служебных хвостов — по нему отличаем людей.

    Хвост тут важен не меньше номера: `kireev1DE` и `kireevs-3` — один человек, но,
    пока `de` остаётся в основе, они выглядят как разные.

    А вот короткие куски здесь, в отличие от слов, сохраняются: инициал — единственное,
    чем `LitovkaE1` отличается от `LitovkaP1`, и выбросить его значит слить двух разных
    людей в одного.
    """
    return "".join(_parts(name, stop_words, 1))


def _same_person(first: str, second: str) -> bool:
    """Похожи ли две основы настолько, что это один человек, а не однофамильцы."""
    if first == second:
        return True

    shorter, longer = sorted((first, second), key=len)

    return longer.startswith(shorter) and len(longer) - len(shorter) <= _BASE_SLACK


def _score_against(terms: list[str], name: str, stop_words: frozenset[str]) -> float:
    """Похожесть имени на набор строк — лучшая из трёх мер."""
    if not terms:
        return 0.0

    query_tokens = [token for term in terms for token in _tokens(term, stop_words)]
    query_flat = _normalized(" ".join(terms))
    candidate_tokens = _tokens(name, stop_words)
    candidate_flat = _normalized(name)

    return max(
        _token_score(query_tokens, candidate_tokens),
        _substring_score(query_flat, candidate_flat),
        _bigram_score(query_flat, candidate_flat),
    )


def match(
    strong_terms: list[str],
    weak_terms: list[str],
    names: list[str],
    stop_words: frozenset[str],
) -> list[Candidate]:
    """Кандидаты среди `names`, отсортированные по убыванию похожести.

    `strong_terms` — то, что принадлежит лично человеку: левая часть его почты и
    подсказка, введённая руками. `weak_terms` — базовое имя получателя: в нём фамилия
    сокращена до буквы, поэтому совпадения по нему одного недостаточно для галочки.

    `stop_words` — слова, которые ничего не говорят о человеке: ключи серверов и прочие
    хвосты вроде `chain`, которыми на панели помечали, куда клиент заведён.
    """
    scored: list[Candidate] = []

    for name in names:
        strong = _score_against(strong_terms, name, stop_words)
        weak = min(_score_against(weak_terms, name, stop_words), WEAK_SCORE_CAP)
        score = max(strong, weak)

        if score >= MIN_SCORE:
            scored.append(Candidate(name=name, score=round(min(score, 1.0), 3)))

    scored.sort(key=lambda candidate: (-candidate.score, candidate.name))

    return _mark_suggested(scored, stop_words)


def _mark_suggested(scored: list[Candidate], stop_words: frozenset[str]) -> list[Candidate]:
    """Проставляет галочки — но только если за первое место не спорят разные люди.

    Несколько конфигов у одного человека это норма (`artem_solo1de`…`6de`), а вот два
    однофамильца с разными инициалами — повод не решать за пользователя.
    """
    confident = [candidate for candidate in scored if candidate.score >= CONFIDENT_SCORE]

    if not confident:
        return scored

    bases = [_base(candidate.name, stop_words) for candidate in confident]

    if not all(_same_person(bases[0], other) for other in bases[1:]):
        return scored

    return [
        Candidate(name=c.name, score=c.score, suggested=c.score >= CONFIDENT_SCORE) for c in scored
    ]
