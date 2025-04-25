import psycopg2
import requests
import sqlite3
import wave
import dash
from dash import html, dcc, Input, Output, State
import sounddevice as sd
import matplotlib.pyplot as plt
import networkx as nx
from io import BytesIO
import base64
from transformers import pipeline
import dotenv 
from dotenv import load_dotenv
import os

load_dotenv()

# Настройки для Ollama и базы данных
OLLAMA_API = "http://localhost:11434/v1/chat/completions"
MODEL_NAME = "mistral"
DB_CONFIG = {
    "dbname": "bpmn_db",
    "user": "postgres",
    "password": "1234",
    "host": "localhost",
    "port": 5432
}

# Инициализация модели Whisper для распознавания речи
speech_to_text = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo")

# Функция для записи аудио
def record_audio(duration=15, filename="speech.wav"):
    print(f"Запись аудио на {duration} секунд...")  # Лог для начала записи
    fs = 16000
    audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(audio_data.tobytes())
    print(f"Запись завершена: {filename}")  # Лог для завершения записи
    return filename

# Функция для распознавания речи
def recognize_speech(file_name):
    print(f"Начало распознавания речи для файла: {file_name}")  # Лог начала распознавания
    with open(file_name, 'rb') as f:
        audio_data = f.read()
    result = speech_to_text(audio_data)
    print(f"Распознанный текст: {result['text']}")  # Лог для распознанного текста
    return result['text']

# Отправка текста в Mistral через Ollama API
def ask_mistral(prompt_text):
    print(f"Отправка текста в Mistral: {prompt_text}")  # Лог отправки текста
    response = requests.post(OLLAMA_API, json={
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": f"Ты — аналитик бизнес-процессов. Проанализируй текст и верни элементы BPMN в следующем формате: {prompt_text}"}],
        "temperature": 0.3
    })
    result = response.json()
    print(f"Ответ от Mistral: {result}")  # Лог для ответа от Mistral
    return result["choices"][0]["message"]["content"]

# Парсинг ответа и сохранение в БД PostgreSQL
def parse_response_to_db(response_text):
    print(f"Парсинг ответа и сохранение в БД: {response_text}")  # Лог для парсинга
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for line in response_text.splitlines():
                if line.startswith("Start:"):
                    cur.execute("INSERT INTO events (name, type) VALUES (%s, %s)", (line.split(":")[1].strip(), 'start'))
                elif line.startswith("End:"):
                    cur.execute("INSERT INTO events (name, type) VALUES (%s, %s)", (line.split(":")[1].strip(), 'end'))
                elif line.startswith("Task:"):
                    parts = line.split("|")
                    name = parts[0].split(":")[1].strip()
                    performer = parts[1].split(":")[1].strip() if len(parts) > 1 else None
                    cur.execute("INSERT INTO tasks (name, performer) VALUES (%s, %s)", (name, performer))
                elif line.startswith("Condition:"):
                    cur.execute("INSERT INTO gateways (condition) VALUES (%s)", (line.split(":")[1].strip(),))
                elif line.startswith("From:"):
                    parts = line.split("|")
                    from_name = parts[0].split(":")[1].strip()
                    to_name = parts[1].split(":")[1].strip()
                    condition = parts[2].split(":")[1].strip() if len(parts) > 2 else None
                    cur.execute("""
                        INSERT INTO sequence_flows (from_id, to_id, from_type, to_type, condition)
                        VALUES (
                            (SELECT id FROM tasks WHERE name=%s LIMIT 1),
                            (SELECT id FROM tasks WHERE name=%s LIMIT 1),
                            'task', 'task', %s
                        );
                    """, (from_name, to_name, condition))
        conn.commit()

# Функция для создания базы данных, если она не существует
def create_db_if_not_exists():
    conn = psycopg2.connect(dbname="postgres", user="postgres", password="1234", host="localhost", port="5432")
    conn.autocommit = True  # Чтобы не нужно было делать COMMIT для создания базы
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_CONFIG['dbname']}';")
        exists = cur.fetchone()
        if not exists:
            cur.execute(f"CREATE DATABASE {DB_CONFIG['dbname']};")
            print(f"База данных {DB_CONFIG['dbname']} была создана.")
    conn.close()

# Функция для создания таблиц, если они не существуют
def create_tables_if_not_exists():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(50) NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    performer VARCHAR(255)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gateways (
                    id SERIAL PRIMARY KEY,
                    condition TEXT NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sequence_flows (
                    id SERIAL PRIMARY KEY,
                    from_id INTEGER NOT NULL REFERENCES tasks(id),
                    to_id INTEGER NOT NULL REFERENCES tasks(id),
                    from_type VARCHAR(50) NOT NULL,
                    to_type VARCHAR(50) NOT NULL,
                    condition TEXT
                );
            """)
            conn.commit()
            print("Таблицы были созданы (если они ещё не существуют).")

# Веб-интерфейс с Dash
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
    print(f"Callback сработал: {analyze_clicks} {record_clicks}")  # Лог для проверки, что callback срабатывает
    ctx = dash.callback_context
    if not ctx.triggered:
        return '', '', ''
    
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    print(f"Триггер: {triggered_id}")  # Лог для того, какой элемент сработал
    
    if triggered_id == 'record-button':
        filename = record_audio()
        recognized = recognize_speech(filename)
        # Анализируем распознанный текст
        result = ask_mistral(recognized)
        parse_response_to_db(result)  # Сохраняем результат в базу данных
        return f"Распознанный текст: {recognized}", result, ''
    elif triggered_id == 'analyze-button' and input_text:
        result = ask_mistral(input_text)
        parse_response_to_db(result)
        return '', result, ''

    return '', 'Ошибка: не удалось обработать ввод.', ''

if __name__ == '__main__':
    create_db_if_not_exists()  # Проверка создания базы данных
    create_tables_if_not_exists()  # Проверка создания таблиц
    app.run(debug=True)
