import requests
from django.shortcuts import render


# ============================================================
# Системный промпт, который отправляется модели с каждым запросом.
# Меняйте его здесь — он применится ко всем запросам к модели.
# ============================================================
SYSTEM_PROMPT = """
You are the intellectual model. Answer shortly, without using tables. Maximum length of the answer 5 sentences."""


def index(request):
    context = {}
    if request.method == 'POST':
        user_message = request.POST.get('message', '')

        if user_message.strip():
            # Формируем список сообщений: system (если задан) + user
            messages = []
            if SYSTEM_PROMPT.strip():
                messages.append({'role': 'system', 'content': SYSTEM_PROMPT})
            messages.append({'role': 'user', 'content': user_message})

            try:
                response = requests.post(
                    'http://localhost:11434/api/chat',
                    json={
                        'model': 'qwen3:4b-instruct',  # точное имя из `ollama list`
                        'messages': messages,
                        'stream': False
                    },
                    timeout=600  # 10 минут — с запасом на загрузку модели
                )
                response.raise_for_status()
                data = response.json()
                model_reply = data.get('message', {}).get('content', '')
                context['response_text'] = model_reply
            except requests.exceptions.HTTPError as e:
                context['response_text'] = f"Ollama вернула ошибку: {e.response.text}"
            except requests.exceptions.ConnectionError:
                context['response_text'] = (
                    "Не удалось подключиться к Ollama. "
                    "Убедитесь, что она запущена (ollama serve)."
                )
            except requests.exceptions.Timeout:
                context['response_text'] = (
                    "Модель не ответила за отведённое время. "
                    "Попробуйте ещё раз — первый запрос может быть долгим."
                )
            except requests.exceptions.RequestException as e:
                context['response_text'] = f"Ошибка при обращении к модели: {e}"
        else:
            context['response_text'] = "Вы не ввели сообщение."

        context['user_message'] = user_message

    return render(request, 'wibecode/index.html', context)


def about(request):
    return render(request, 'wibecode/about.html')


def choice(request):
    context = {}

    if request.method == 'POST':
        # Получаем значение из радиокнопок (name="user_choice")
        selected_option = request.POST.get('user_choice')

        if selected_option == '1':
            context['result_text'] = "Спасибо, мы вам перезвоним"
        elif selected_option == '2':
            context['result_text'] = "Очень рады с вами сотрудничать"
        elif selected_option == '3':
            context['result_text'] = "Приходите к нам ещё"

    return render(request, 'wibecode/choice.html', context)