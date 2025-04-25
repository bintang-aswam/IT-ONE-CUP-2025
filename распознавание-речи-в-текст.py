import wave
import dash
from dash import html, dcc, Input, Output, State
import sounddevice as sd
import matplotlib.pyplot as plt
import networkx as nx
from io import BytesIO
import base64
from transformers import pipeline

from dotenv import load_dotenv
import os

load_dotenv()
# Yandex Cloud
FOLDER_ID = os.getenv("FOLDER_ID")
IAM_TOKEN = os.getenv("IAM_TOKEN")

# Инициализация модели Whisper для распознавания речи
speech_to_text = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo")

# Запись аудио
def record_audio(duration=15, filename="speech.wav"):
    fs = 16000
    audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(audio_data.tobytes())
    return filename

# Распознавание речи с использованием Whisper
def recognize_speech(file_name):
    # Чтение аудио файла
    with open(file_name, 'rb') as f:
        audio_data = f.read()
    
    # Применение модели Whisper для преобразования речи в текст
    result = speech_to_text(audio_data)
    return result['text']  # Вернем распознанный текст

# Анализ текста (можно использовать для других моделей или предобработки)
def analyze_text(text):
    # Простой анализ: делим текст на слова
    tokens = text.split()  # Разделение текста на слова
    
    # Извлечение слов, заканчивающихся на 'ed' (глаголы в прошедшем времени)
    actions_ed = [token for token in tokens if token.endswith('ed')]
    
    # Извлечение слов, заканчивающихся на 'ing' (глаголы в форме продолженного времени)
    actions_ing = [token for token in tokens if token.endswith('ing')]
    
    # Извлечение слов, заканчивающихся на 'ly' (наречия)
    actions_ly = [token for token in tokens if token.endswith('ly')]
    
    # Объединение всех найденных слов
    actions = actions_ed + actions_ing + actions_ly
    
    # Если нет найденных действий, вернуть сообщение "Нет действий"
    if not actions:
        actions = ["Нет действий"]
    
    return tokens, actions

# Визуализация зависимостей как base64-изображения (для будущих улучшений)
def draw_dependency_graph(tokens):
    G = nx.DiGraph()
    for i in range(len(tokens)-1):
        G.add_edge(tokens[i], tokens[i+1])  # Добавляем ребра между соседними токенами
    
    pos = nx.spring_layout(G, seed=42)
    fig, ax = plt.subplots(figsize=(10, 6))
    nx.draw(G, pos, with_labels=True, arrows=True, node_color="skyblue", node_size=2000, font_size=10, ax=ax)
    
    # Сохраняем изображение в буфер и конвертируем в base64
    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"

# Веб-интерфейс
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("Анализ речи с использованием Whisper"),
    dcc.Input(id='text-input', type='text', placeholder='Введите текст...', style={'width': '100%'}),
    html.Button('Анализировать текст', id='analyze-button', n_clicks=0),
    html.Button('Записать и распознать речь', id='record-button', n_clicks=0),
    html.Div(id='recognized-text', style={'marginTop': '20px', 'fontWeight': 'bold'}),
    html.Div(id='analysis-result'),
    html.Img(id='dep-graph', style={'marginTop': '30px', 'maxWidth': '100%'})
])

@app.callback(
    Output('recognized-text', 'children'),
    Output('analysis-result', 'children'),
    Output('dep-graph', 'src'),
    Input('analyze-button', 'n_clicks'),
    Input('record-button', 'n_clicks'),
    State('text-input', 'value')
)
def update_output(analyze_clicks, record_clicks, input_text):
    ctx = dash.callback_context
    if not ctx.triggered:
        return '', '', ''
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if triggered_id == 'record-button':
        filename = record_audio()
        recognized = recognize_speech(filename)
        tokens, actions = analyze_text(recognized)
        image_src = draw_dependency_graph(tokens)
        return f"Распознанный текст: {recognized}", format_results(tokens, actions), image_src
    elif triggered_id == 'analyze-button' and input_text:
        tokens, actions = analyze_text(input_text)
        image_src = draw_dependency_graph(tokens)
        return '', format_results(tokens, actions), image_src
    return '', 'Ошибка: не удалось обработать ввод.', ''

def format_results(tokens, actions):
    token_lines = [f"{t}" for t in tokens]
    action_lines = [f"- {a}" for a in actions]
    return html.Div([
        html.H4("Токены текста:"), 
        html.Pre("\n".join(token_lines)),
        html.H4("Найденные действия:"), 
        html.Pre("\n".join(action_lines) if action_lines else "Нет действий")
    ])

if __name__ == '__main__':
    app.run(debug=True)
