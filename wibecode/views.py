
import json
import logging
import re

import requests

from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST


logger = logging.getLogger(__name__)

# Подключение к локальной Ollama
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3:4b-instruct"

TOTAL_STEPS = 10


GENRES = {
    "fantasy": {
        "name": "Волшебное королевство",
        "english": "Fantasy",
        "description": (
            "Middle Ages, knights, princesses, secret "
            "castles, magic, and dragons. A dragon can "
            "kidnap a princess or knight, growl, and be "
            "scary, but strictly without violence or harm."
        ),
    },

    "space": {
        "name": "Космические миры",
        "english": "Sci-Fi",
        "description": (
            "Space, aliens, rocketry, unknown planets, "
            "spaceship breakdowns, mysterious robots, "
            "and cosmic secrets."
        ),
    },

    "life": {
        "name": "Приключения рядом",
        "english": "Adventure Time",
        "description": (
            "School, sports, vacations, searching for "
            "lost items, tricky riddles, escaping a "
            "grumpy dog, or friendly rivals in a game."
        ),
    },
}


# ------------------------------------------
# ДАННЫЕ РЕБЁНКА И ИСТОРИИ
# ------------------------------------------

def get_profile(request):
    return request.session.get("profile")


def get_stories(request):
    return request.session.get("stories", [])


def get_story(request, story_id):
    for story in get_stories(request):
        if story["id"] == story_id:
            return story

    return None


# ------------------------------------------
# ОСНОВНОЙ ПРОМПТ ДЛЯ QWEN
# ------------------------------------------

def build_system_prompt(
    profile,
    genre,
    step_number,
    user_choice=None,
):

    name = profile["name"]
    age = profile["age"]

    gender = (
        "girl"
        if profile["gender"] == "girl"
        else "boy"
    )

    genre_name = GENRES[genre]["english"]
    genre_description = GENRES[genre]["description"]

    if user_choice is None:
        user_choice = ""

    prompt = f"""
You are an engaging interactive storytelling AI for
children aged 6 to 12.

You create a dynamic, real-time, text-based role-playing
fairy tale.

All story text and options MUST be written in Russian.

PLAYER DATA:
- Child's Name: {name}
- Age: {age} years old
- Gender: {gender}
- Selected Genre: {genre_name}
- Child's Previous Choice: {user_choice}

GENRE & ADVENTURE DESCRIPTIONS:

Selected genre description:
{genre_description}

Available genres:

1. Fantasy:
Middle Ages, knights, princesses, secret castles,
magic, and dragons.

A dragon can kidnap a princess or knight, growl,
and be scary, but strictly without violence or harm.

2. Sci-Fi:
Space, aliens, rocketry, unknown planets,
spaceship breakdowns, mysterious robots,
and cosmic secrets.

3. Adventure Time:
School, sports, vacations, searching for lost items,
tricky riddles, escaping a grumpy dog,
or friendly rivals in a game.


CENSORSHIP & CONTENT BOUNDARIES (CRITICAL):

1. THRILL & SUSPENSE:

The story MUST be engaging and include suitable
obstacles, secrets, chases, scary moments,
fairy-tale kidnappings, and challenges.

The plot must not be overly sanitized,
predictable, or boringly safe.

Use genuine suspense, surprising events,
mysteries, and meaningful consequences.

Make every adventure exciting while remaining
appropriate for the child's age.

2. SAFETY:

Blood, death, graphic physical violence, cruelty,
fatal fights, and character deaths are
STRICTLY FORBIDDEN.

All conflicts and dangers must remain
fairy-tale-like.

Conflicts must be solved through cleverness,
courage, friendship, creativity, or logic.

Do not provide instructions for dangerous
real-world behavior.

Never request private information,
addresses, phone numbers, or contact details.


GENERATION & PLOT LOGIC RULES:

1. PLOT CONTINUITY:

On Step 1:
Create the opening scene from scratch
based on the selected genre.

Do not rely on previous choices.

On Steps 2-9:
The new story snippet MUST logically continue
the action chosen by the child.

The chosen action must visibly affect
the next events.

Remember important characters, places,
objects, secrets, and earlier decisions.

Do not restart the story.

2. TEXT LENGTH BASED ON AGE:

For ages 6-8:
Write exactly 3-4 short, simple sentences.

Each sentence should appear on a separate line.

Use simple vocabulary and plenty of action.

For ages 9-12:
Write exactly 5-7 sentences across 6-8
non-empty lines.

You may split a sentence over two lines
to achieve the required line count.

Include intrigue, descriptions, and
interesting details.

Do not make scenes too long.

3. MAIN CHARACTER:

The main character is ALWAYS {name}.

Use the child's name naturally.

Use correct Russian grammatical gender
and pronouns based on {gender}.

Never replace the main character
with another protagonist.

4. STORY STRUCTURE:

The story lasts exactly 10 scenes.

Current scene: #{step_number} out of 10.

Each scene must logically follow
the previous events.

Build one connected adventure
with a beginning, development,
climax, and resolution.

5. CHOICES:

For scenes 1-9:
Provide EXACTLY THREE meaningful choices.

Each choice must be written in Russian.

Each choice must contain EXACTLY
3 or 4 words.

Examples:
"Спрятаться за кустом"
"Заговорить с драконом"
"Убежать в тёмный лес"

The three choices must lead
to clearly different developments.

They must not be identical
or almost identical.

6. FINAL SCENE:

IF THIS IS STEP 10:

Write a bright and happy resolution
to the main conflict.

Provide a satisfying happy ending.

Summarize the adventure naturally.

Praise {name} for bravery, cleverness,
friendship, or perseverance.

DO NOT output any choice options.

The story must end completely.


RESPONSE STRUCTURE:

For scenes 1-9:
1. Story snippet.
2. On a new line ask exactly:
"Что будет дальше?"
3. Provide exactly three short choices.

For scene 10:
1. Final story snippet.
2. No question.
3. No choices.


TECHNICAL OUTPUT FORMAT:

Return ONLY valid JSON.

Do not output Markdown.
Do not use code fences.
Do not write explanations outside JSON.

Use this JSON structure:

{{
    "title": "Короткое название книги",
    "text": "Текст истории",
    "question": "Что будет дальше?",
    "options": [
        "Первый короткий выбор",
        "Второй короткий выбор",
        "Третий короткий выбор"
    ]
}}

The text field must contain ONLY the story snippet.
The question field contains the question separately.
The options field contains exactly three choices.

For step 10 return:

{{
    "title": "Название книги",
    "text": "Счастливый финал истории",
    "question": "",
    "options": []
}}

VERY IMPORTANT:
Return JSON only.
All story content must be in Russian.
"""

    return prompt


# ------------------------------------------
# ПРОВЕРКА ОТВЕТА НЕЙРОСЕТИ
# ------------------------------------------

def clean_qwen_response(content):

    # Удаляем размышления модели, если они есть
    content = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=re.DOTALL,
    ).strip()

    # Убираем случайные Markdown-ограждения
    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"\s*```$",
            "",
            content,
        )

    return json.loads(content)


def count_words(text):
    return len(text.strip().split())


def validate_scene(data, step_number, age):

    if not isinstance(data, dict):
        raise ValueError("Ответ должен быть объектом JSON")

    title = data.get("title", "Моё приключение")
    text = data.get("text", "")
    options = data.get("options", [])

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Пустой текст истории")

    if not isinstance(title, str):
        title = "Моё приключение"

    # Проверяем длину сцены по количеству строк.
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if age <= 8:
        min_lines = 3
        max_lines = 4
    else:
        min_lines = 6
        max_lines = 8

    if not min_lines <= len(lines) <= max_lines:
        raise ValueError(
            f"Неправильное количество строк: {len(lines)}. "
            f"Нужно от {min_lines} до {max_lines}."
        )

    # На десятом шаге выборов уже не будет
    if step_number == TOTAL_STEPS:
        options = []
        question = ""

    else:
        if not isinstance(options, list) or len(options) != 3:
            raise ValueError(
                "Нейросеть должна предложить ровно 3 варианта"
            )

        checked_options = []

        for option in options:

            if not isinstance(option, str):
                raise ValueError("Вариант выбора должен быть текстом")

            option = option.strip()

            words = count_words(option)

            if words < 3 or words > 4:
                raise ValueError(
                    "Каждый вариант должен содержать 3-4 слова"
                )

            checked_options.append(option)

        if len(set(checked_options)) != 3:
            raise ValueError("Варианты выбора повторяются")

        options = checked_options
        question = "Что будет дальше?"

    # Убираем вопрос из конца текста,
    # если модель случайно написала его внутри сцены.
    text = re.sub(
        r"\s*Что будет дальше\?\s*$",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )

    # На странице истории вопрос будет показан
    # отдельно от основного текста.
    if step_number < TOTAL_STEPS:
        text = text + "\n\n" + question

    return {
        "title": title.strip()[:150],
        "text": text,
        "options": options,
    }


# ------------------------------------------
# ГЕНЕРАЦИЯ СЦЕНЫ ЧЕРЕЗ OLLAMA
# ------------------------------------------

def generate_with_qwen(
    profile,
    genre,
    step_number,
    story=None,
    selected_choice=None,
):

    system_prompt = build_system_prompt(
        profile=profile,
        genre=genre,
        step_number=step_number,
        user_choice=selected_choice,
    )

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
                "This is scene 1 of 10. "
                "Create the beginning of an exciting "
                "interactive adventure from scratch. "
                "Introduce the main character, "
                "an interesting mystery or obstacle, "
                "and exactly three short choices. "
                "Return JSON only."
            ),
        })

    else:

        history = []

        # Передаём Qwen предыдущие события
        for number, page in enumerate(story["pages"], 1):

            history.append(
                f"SCENE {number}:\n{page['text']}"
            )

            if page.get("choice"):
                history.append(
                    f"CHILD'S CHOICE: {page['choice']}"
                )

        history_text = "\n\n".join(history)

        if step_number == TOTAL_STEPS:

            instruction = (
                f"The child's latest choice is: "
                f"{selected_choice}\n"
                "This is scene 10 of 10. "
                "Write the final scene. "
                "Resolve the central conflict. "
                "Make the ending bright, satisfying "
                "and happy. Praise the protagonist. "
                "Do not provide further choices. "
                "Return JSON only."
            )

        else:

            instruction = (
                f"The child's latest choice is: "
                f"{selected_choice}\n"
                f"This is scene {step_number} of 10. "
                "Continue directly from that action. "
                "The choice MUST affect the story. "
                "Include excitement, obstacles, "
                "mysteries or suspense. "
                "Provide exactly three options, "
                "each containing 3-4 Russian words. "
                "Return JSON only."
            )

        messages.append({
            "role": "user",
            "content": (
                "PREVIOUS STORY:\n"
                + history_text
                + "\n\nCURRENT TASK:\n"
                + instruction
            ),
        })

    # Если Qwen нарушила формат,
    # попробуем запросить сцену ещё раз.
    last_error = None

    for attempt in range(3):

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1000,
                    },
                },
                timeout=240,
            )

            response.raise_for_status()

            content = response.json()["message"]["content"]

            data = clean_qwen_response(content)

            return validate_scene(
                data,
                step_number,
                profile["age"],
            )

        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ) as error:

            last_error = error

            logger.warning(
                "Qwen returned invalid format on attempt %s: %s",
                attempt + 1,
                error,
            )

            messages.append({
                "role": "user",
                "content": (
                    "Your previous response did not meet "
                    "the required format. "
                    f"Validation error: {error}. "
                    "Please regenerate the current scene. "
                    "Follow the requested number of lines "
                    "and all JSON and choice rules exactly. "
                    "Return JSON only."
                ),
            })

    raise ValueError(
        f"Qwen не смогла соблюсти формат: {last_error}"
    )


# ------------------------------------------
# ЭКРАН ЗНАКОМСТВА
# ------------------------------------------

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

        elif not 6 <= age <= 12:
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


# ------------------------------------------
# ГЛАВНАЯ СТРАНИЦА
# ------------------------------------------

def home(request):

    profile = get_profile(request)

    if not profile:
        return redirect("wibecode:auth")

    return render(request, "wibecode/index.html", {
        "page": "home",
        "profile": profile,
        "stories": get_stories(request),
    })


# ------------------------------------------
# СОЗДАНИЕ НОВОЙ КНИГИ
# ------------------------------------------

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
            step_number=1,
        )

    except (requests.RequestException, ValueError,
            KeyError, TypeError):

        logger.exception("Ошибка создания истории")

        return render(request, "wibecode/index.html", {
            "page": "home",
            "profile": profile,
            "stories": get_stories(request),
            "error": (
                "Не получилось создать историю. "
                "Проверь Ollama и попробуй ещё раз."
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
        "step": 1,
        "is_finished": False,
    }

    stories.append(new_book)

    request.session["stories"] = stories
    request.session.modified = True

    return redirect(
        "wibecode:story",
        story_id=story_id,
    )


# ------------------------------------------
# СТРАНИЦА КНИГИ
# ------------------------------------------

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
            and story["step"] < TOTAL_STEPS
        ):

            selected_choice = story["options"][choice_index]

            next_step = story["step"] + 1

            is_final = next_step == TOTAL_STEPS

            try:

                scene = generate_with_qwen(
                    profile=profile,
                    genre=story["genre"],
                    step_number=next_step,
                    story=story,
                    selected_choice=selected_choice,
                )

                # Запоминаем выбор ребёнка
                story["pages"][-1]["choice"] = selected_choice

                # Добавляем следующую страницу
                story["pages"].append({
                    "text": scene["text"],
                    "choice": None,
                })

                story["step"] = next_step
                story["options"] = scene["options"]
                story["is_finished"] = is_final

                request.session["stories"] = stories
                request.session.modified = True

                return redirect(
                    "wibecode:story",
                    story_id=story_id,
                )

            except (requests.RequestException, ValueError,
                    KeyError, TypeError):

                logger.exception("Ошибка продолжения истории")

                error = (
                    "Не получилось продолжить историю. "
                    "Попробуй нажать ещё раз."
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


# ------------------------------------------
# БИБЛИОТЕКА
# ------------------------------------------

def library(request):

    if not get_profile(request):
        return redirect("wibecode:auth")

    return render(request, "wibecode/index.html", {
        "page": "library",
        "stories": get_stories(request),
    })


# ------------------------------------------
# ВЫХОД ИЗ ПРОФИЛЯ
# ------------------------------------------

@require_POST
def logout_page(request):

    request.session.flush()

    return redirect("wibecode:auth")
