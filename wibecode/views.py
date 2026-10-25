import json
import logging
import re

import requests

from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST


logger = logging.getLogger(__name__)

TOTAL_CHOICES = 10

GENRES = {
    "fantasy": {
        "name": "Фэнтези",
        "description": (
            "Средневековье, рыцари, принцессы, "
            "тайные замки, волшебство и драконы."
        ),
    },
    "space": {
        "name": "Фантастика",
        "description": (
            "Космос, инопланетяне, ракеты, "
            "неизвестные планеты и загадочные роботы."
        ),
    },
    "life": {
        "name": "Приключения",
        "description": (
            "Школа, спорт, путешествия, друзья, "
            "загадки и городские приключения."
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


def _call_ollama(messages):
    """Запрос к локальной Ollama."""
    response = requests.post(
        settings.OLLAMA_URL,
        json={
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.7,
                "num_predict": 500,
            },
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def _call_selectel(messages):
    """Запрос к Selectel Token Factory (OpenAI-совместимый API)."""
    response = requests.post(
        f"{settings.SELECTEL_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.SELECTEL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.SELECTEL_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        },
        timeout=240,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def generate_with_qwen(
    profile,
    genre,
    story=None,
    selected_choice=None,
    final=False,
):

    gender = (
        "девочка"
        if profile["gender"] == "girl"
        else "мальчик"
    )

    system_prompt = f"""
Ты автор увлекательных интерактивных историй
для детей в возрасте от 6 до 12 лет.

Пиши исключительно на русском языке.

ДАННЫЕ ГЕРОЯ:
Имя: {profile["name"]}
Возраст: {profile["age"]}
Пол: {gender}

ЖАНР:
{GENRES[genre]["description"]}

ПРАВИЛА:
1. Главный герой — ребёнок с указанным именем.
2. Учитывай предыдущие события и выборы.
3. Пиши понятным и интересным языком.
4. Добавляй загадки, препятствия и приключения.
5. Допускаются сказочные опасности, но без жестокости,
   крови, смертей и серьёзного насилия.
6. Не запрашивай личные данные ребёнка.
7. Каждый выбор должен влиять на развитие сюжета.
8. Возвращай только корректный JSON.

ДЛИНА ТЕКСТА:
Для 6-8 лет — 3-4 коротких предложения.
Для 9-12 лет — 5-7 предложений.

ИСТОРИЯ:
Всего 10 выборов ребёнка.
После десятого выбора напиши счастливый финал.

ФОРМАТ ОТВЕТА:
{{
    "title": "Название истории",
    "text": "Текст сцены",
    "options": [
        "Первое действие",
        "Второе действие",
        "Третье действие"
    ]
}}

Для финала:
{{
    "title": "Название истории",
    "text": "Завершение истории",
    "options": []
}}

В обычной сцене предложи ровно три коротких
варианта выбора по 3-4 слова каждый.

В финале не предлагай новых вариантов.
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
                "Начни новую интересную историю. "
                "Представь героя, создай интригу "
                "и предложи три действия."
            ),
        })

    else:
        history = []

        for page in story["pages"]:
            history.append(page["text"])

            if page.get("choice"):
                history.append(
                    "Выбор героя: " + page["choice"]
                )

        instruction = (
            f"Герой выбрал: {selected_choice}. "
        )

        if final:
            instruction += (
                "Это последний выбор. "
                "Заверши историю счастливым финалом. "
                "Не предлагай новых действий."
            )
        else:
            instruction += (
                "Продолжи историю на основе этого выбора. "
                "Предложи три новых действия."
            )

        messages.append({
            "role": "user",
            "content": "\n".join(history) + "\n" + instruction,
        })

    # Выбор движка в зависимости от settings.STORY_ENGINE
    if settings.STORY_ENGINE == "server":
        content = _call_selectel(messages)
    else:
        content = _call_ollama(messages)

    content = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=re.DOTALL,
    ).strip()

    data = json.loads(content)

    text = str(data.get("text", "")).strip()
    title = str(data.get("title", "Моё приключение"))[:150]
    options = data.get("options", [])

    if not text:
        raise ValueError("Нейросеть вернула пустой текст")

    if final:
        options = []

    elif not isinstance(options, list) or len(options) != 3:
        raise ValueError(
            "Нейросеть должна предложить три варианта"
        )

    return {
        "title": title,
        "text": text,
        "options": [str(option) for option in options],
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
            error = "Введи имя ребёнка."

        elif not 6 <= age <= 12:
            error = "Выбери возраст от 6 до 12 лет."

        elif gender not in ("girl", "boy"):
            error = "Выбери пол ребёнка."

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
    })


def genres(request):

    if not get_profile(request):
        return redirect("wibecode:auth")

    return render(request, "wibecode/index.html", {
        "page": "genres",
    })


def library(request):

    if not get_profile(request):
        return redirect("wibecode:auth")

    return render(request, "wibecode/index.html", {
        "page": "library",
        "stories": list(reversed(get_stories(request))),
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
        scene = generate_with_qwen(
            profile=profile,
            genre=genre,
        )

    except (requests.RequestException, ValueError, KeyError, TypeError):
        logger.exception("Story generation failed")

        return render(request, "wibecode/index.html", {
            "page": "genres",
            "error": (
                "Не удалось создать историю. "
                "Проверь Ollama и попробуй ещё раз."
            ),
        })

    stories = get_stories(request)

    story_id = max(
        (story["id"] for story in stories),
        default=0,
    ) + 1

    story = {
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

    stories.append(story)

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
    read_mode = request.GET.get("read") == "1"

    if request.method == "POST" and not read_mode:

        if story["is_finished"]:
            return redirect(
                "wibecode:story",
                story_id=story_id,
            )

        try:
            choice_index = int(
                request.POST.get("choice", "-1")
            )

            submitted_step = int(
                request.POST.get("step", "-1")
            )

        except ValueError:
            choice_index = -1
            submitted_step = -1

        if submitted_step != story["step"]:
            error = "Этот выбор уже был сделан."

        elif not 0 <= choice_index < len(story["options"]):
            error = "Выбери один из трёх вариантов."

        elif story["step"] >= TOTAL_CHOICES:
            error = "История уже завершена."

        else:
            selected_choice = story["options"][choice_index]

            final = story["step"] + 1 == TOTAL_CHOICES

            try:
                scene = generate_with_qwen(
                    profile=profile,
                    genre=story["genre"],
                    story=story,
                    selected_choice=selected_choice,
                    final=final,
                )

                story["pages"][-1]["choice"] = selected_choice

                story["pages"].append({
                    "text": scene["text"],
                    "choice": None,
                })

                story["step"] += 1
                story["options"] = scene["options"]
                story["is_finished"] = final

                request.session["stories"] = stories
                request.session.modified = True

                return redirect(
                    "wibecode:story",
                    story_id=story_id,
                )

            except (requests.RequestException, ValueError,
                    KeyError, TypeError):

                logger.exception("Story continuation failed")

                error = (
                    "Не удалось продолжить историю. "
                    "Попробуй ещё раз."
                )

    return render(request, "wibecode/index.html", {
        "page": "story",
        "profile": profile,
        "story": story,
        "current_page": story["pages"][-1],
        "progress_percent": story["step"] * 10,
        "read_mode": read_mode,
        "error": error,
    })


@require_POST
def logout_page(request):
    request.session.flush()
    return redirect("wibecode:auth")