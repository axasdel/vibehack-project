
import json
import logging
import re
import requests

from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST


logger = logging.getLogger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3:4b-instruct"

GENRES = {
    "fantasy": {
        "name": "Волшебное королевство",
        "description": (
            "Средневековое фэнтези: рыцари, драконы, "
            "принцессы, замки и волшебство."
        ),
    },
    "space": {
        "name": "Космические миры",
        "description": (
            "Научная фантастика: космос, другие планеты, "
            "инопланетяне и параллельные миры."
        ),
    },
    "life": {
        "name": "Приключения рядом",
        "description": (
            "Интересные приключения: школа, друзья, "
            "путешествия, спорт и необычные открытия."
        ),
    },
}


def get_profile(request):
    return request.session.get("profile")


def get_stories(request):
    return request.session.get("stories", [])


def get_story(request, story_id):
    for story in get_stories(request):
        if story["id"] == story_id:
            return story

    return None


def generate_with_qwen(profile, genre, story=None,
                       selected_choice=None, final=False):

    gender = (
        "девочка"
        if profile["gender"] == "girl"
        else "мальчик"
    )

    system_prompt = f"""
Ты писатель интерактивных книг для детей 6-12 лет.

Ты создаёшь интересную добрую историю, в которой
главный герой — сам ребёнок.

ДАННЫЕ ГЕРОЯ:
Имя: {profile["name"]}
Возраст: {profile["age"]}
Пол: {gender}

ЖАНР:
{GENRES[genre]["description"]}

ВАЖНЫЕ ПРАВИЛА:
1. Всегда пиши на русском языке.
2. Главный герой — ребёнок с указанными данными.
3. Используй имя героя в повествовании.
4. Пиши живым, интересным, понятным детям языком.
5. Учитывай все предыдущие действия героя.
6. Выбор ребёнка должен реально менять сюжет.
7. Не используй жестокость, опасные инструкции,
   сексуальное содержание и сильные пугающие сцены.
8. Не спрашивай личные данные и контакты ребёнка.
9. Текст сцены — примерно 80-130 слов.
10. Не используй Markdown, HTML или пояснения.
11. Возвращай только корректный JSON.

ФОРМАТ ОБЫЧНОЙ СЦЕНЫ:
{{
    "title": "Короткое название книги",
    "text": "Текст сцены",
    "options": [
        "Первое действие",
        "Второе действие",
        "Третье действие"
    ]
}}

Предлагай три РАЗНЫХ варианта развития сюжета.
Формулируй каждый вариант коротко и понятно.

ФОРМАТ ФИНАЛА:
{{
    "title": "Название книги",
    "text": "Красивое завершение истории",
    "options": []
}}

Если требуется финал, заверши сюжет логично,
с учётом всех предыдущих решений героя.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    if story is None:
        messages.append({
            "role": "user",
            "content": (
                "Начни новую увлекательную историю. "
                "Познакомь героя с необычным местом "
                "или событием. Создай интригу и предложи "
                "ровно три варианта действий."
            ),
        })

    else:
        history = []

        for number, page in enumerate(story["pages"], 1):
            history.append(
                f"Сцена {number}: {page['text']}"
            )

            if page.get("choice"):
                history.append(
                    f"Решение героя: {page['choice']}"
                )

        history_text = "\n".join(history)

        if final:
            instruction = (
                f"Последнее решение героя: {selected_choice}. "
                "Это ДЕСЯТЫЙ и последний выбор! "
                "Напиши красивый законченный финал. "
                "Разреши основную загадку истории. "
                "Не предлагай новых вариантов действий. "
                "В поле options верни пустой список."
            )
        else:
            instruction = (
                f"Новое решение героя: {selected_choice}. "
                "Продолжи историю именно на основе "
                "этого выбора. Предложи три новых "
                "варианта действий."
            )

        messages.append({
            "role": "user",
            "content": (
                "История до этого момента:\n"
                + history_text
                + "\n\n"
                + instruction
            ),
        })

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.8,
                "num_predict": 800,
            },
        },
        timeout=240,
    )

    response.raise_for_status()

    content = response.json()["message"]["content"]

    content = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=re.DOTALL,
    ).strip()

    result = json.loads(content)

    if not isinstance(result, dict):
        raise ValueError("Неверный ответ нейросети")

    text = result.get("text")
    title = result.get("title", "Моё приключение")
    options = result.get("options", [])

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Нейросеть не создала текст")

    if final:
        options = []
    else:
        if not isinstance(options, list) or len(options) != 3:
            raise ValueError("Нужно ровно три варианта выбора")

        if not all(isinstance(item, str) and item.strip()
                   for item in options):
            raise ValueError("Некорректные варианты выбора")

        options = [item.strip()[:200] for item in options]

    return {
        "title": str(title)[:150],
        "text": text.strip(),
        "options": options,
    }


def auth_page(request):
    if get_profile(request):
        return redirect("wibecode:home")

    error = None

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        age_text = request.POST.get("age", "")
        gender = request.POST.get("gender", "")

        try:
            age = int(age_text)
        except ValueError:
            age = 0

        if not name or len(name) > 50:
            error = "Введи имя героя (до 50 символов)."

        elif age < 6 or age > 12:
            error = "Выбери возраст от 6 до 12 лет."

        elif gender not in ("girl", "boy"):
            error = "Выбери пол героя."

        else:
            request.session.cycle_key()

            request.session["profile"] = {
                "name": name,
                "age": age,
                "gender": gender,
            }

            request.session["stories"] = []

            return redirect("wibecode:home")

    return render(request, "wibecode/index.html", {
        "page": "auth",
        "error": error,
    })


def home(request):
    profile = get_profile(request)

    if not profile:
        return redirect("wibecode:auth")

    return render(request, "wibecode/index.html", {
        "page": "home",
        "profile": profile,
        "stories": get_stories(request),
    })


@require_POST
def new_story(request):
    profile = get_profile(request)

    if not profile:
        return redirect("wibecode:auth")

    genre = request.POST.get("genre")

    if genre not in GENRES:
        return HttpResponseBadRequest("Неверный жанр")

    try:
        scene = generate_with_qwen(profile, genre)

    except (requests.RequestException, ValueError,
            KeyError, TypeError, json.JSONDecodeError):

        logger.exception("Ошибка создания истории")

        return render(request, "wibecode/index.html", {
            "page": "home",
            "profile": profile,
            "stories": get_stories(request),
            "error": (
                "Не удалось создать историю. "
                "Убедись, что Ollama запущена, "
                "и попробуй снова."
            ),
            "show_genres": True,
        })

    stories = get_stories(request)

    story_id = max(
        (item["id"] for item in stories),
        default=0,
    ) + 1

    new_book = {
        "id": story_id,
        "title": scene["title"],
        "genre": genre,
        "genre_name": GENRES[genre]["name"],
        "pages": [
            {
                "text": scene["text"],
                "choice": None,
            }
        ],
        "options": scene["options"],
        "step": 0,
        "is_finished": False,
    }

    stories.append(new_book)

    request.session["stories"] = stories
    request.session.modified = True

    return redirect(
        "wibecode:story",
        story_id=story_id,
    )


def story_page(request, story_id):
    profile = get_profile(request)

    if not profile:
        return redirect("wibecode:auth")

    stories = get_stories(request)
    story = get_story(request, story_id)

    if story is None:
        return redirect("wibecode:library")

    error = None

    if request.method == "POST" and not story["is_finished"]:

        try:
            choice_index = int(
                request.POST.get("choice", "-1")
            )
        except ValueError:
            choice_index = -1

        if (
            0 <= choice_index < len(story["options"])
            and story["step"] < 10
        ):
            selected_choice = story["options"][choice_index]

            is_final = story["step"] + 1 == 10

            try:
                scene = generate_with_qwen(
                    profile=profile,
                    genre=story["genre"],
                    story=story,
                    selected_choice=selected_choice,
                    final=is_final,
                )

                story["pages"][-1]["choice"] = selected_choice

                story["pages"].append({
                    "text": scene["text"],
                    "choice": None,
                })

                story["step"] += 1
                story["options"] = scene["options"]
                story["is_finished"] = is_final

                request.session["stories"] = stories
                request.session.modified = True

                return redirect(
                    "wibecode:story",
                    story_id=story_id,
                )

            except (requests.RequestException, ValueError,
                    KeyError, TypeError, json.JSONDecodeError):

                logger.exception("Ошибка продолжения истории")

                error = (
                    "Не получилось продолжить историю. "
                    "Попробуй ещё раз."
                )

        else:
            error = "Выбери один из предложенных вариантов."

    current_page = story["pages"][-1]

    return render(request, "wibecode/index.html", {
        "page": "story",
        "profile": profile,
        "story": story,
        "current_page": current_page,
        "error": error,
        "progress_percent": story["step"] * 10,
    })


def library(request):
    if not get_profile(request):
        return redirect("wibecode:auth")

    return render(request, "wibecode/index.html", {
        "page": "library",
        "stories": get_stories(request),
    })


@require_POST
def logout_page(request):
    request.session.flush()

    return redirect("wibecode:auth")
