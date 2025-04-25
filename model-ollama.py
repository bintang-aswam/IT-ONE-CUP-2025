import psycopg2
import requests

# --- Настройки подключения ---
OLLAMA_API = "http://localhost:11434/v1/chat/completions"
MODEL_NAME = "mistral"

DB_CONFIG = {
    "dbname": "bpmn_db",
    "user": "postgres",
    "password": "your_password",  # Замените на свой пароль
    "host": "localhost",
    "port": 5432
}

# --- Шаблон запроса ---
PROMPT_TEMPLATE = """
Ты — аналитик бизнес-процессов. Проанализируй текст и верни элементы BPMN в следующем формате:

[EVENT]
Start: <название события>
End: <название события>

[TASK]
Task: <название задачи> | Performer: <исполнитель>

[GATEWAY]
Condition: <условие ветвления>

[SEQUENCE_FLOW]
From: <название элемента> | To: <название элемента> | Condition: <опционально>

Вот текст:
\"\"\"
{input_text}
\"\"\"
"""

# --- Получение последнего текста ---
def fetch_last_input():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, input_text FROM raw_inputs ORDER BY created_at DESC LIMIT 1;")
            return cur.fetchone()

# --- Отправка текста в Mistral через Ollama ---
def ask_mistral(prompt_text):
    response = requests.post(OLLAMA_API, json={
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(input_text=prompt_text)}],
        "temperature": 0.3
    })
    return response.json()["choices"][0]["message"]["content"]

# --- Парсинг ответа и сохранение в БД ---
def parse_response_to_db(response_text):
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

# --- Главная логика ---
def main():
    row = fetch_last_input()
    if not row:
        print("Нет новых данных.")
        return

    input_id, input_text = row
    print(f"[INFO] Получен текст ID {input_id}: {input_text}")

    result = ask_mistral(input_text)
    print("\n[ОТВЕТ МОДЕЛИ]:\n", result)

    parse_response_to_db(result)
    print("[INFO] Данные сохранены в БД.")

if __name__ == "__main__":
    main()
