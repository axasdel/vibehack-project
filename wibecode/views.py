from django.shortcuts import render

def index(request):
    context = {}
    if request.method == 'POST':
        user_message = request.POST.get('message', '')
        context['response_text'] = f"Вы написали: «{user_message}». Длина текста: {len(user_message)} символов."
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