import sqlite3

# Подключение к базе данных
def get_bpmn_elements():
    cnct = sqlite3.connect("bpmn.db")
    cursor = cnct.cursor()
    
    # Предзаполнение таблицы
    basic_elements = [
        ("start", "startEvent", "Старт процесса"),
        ("end", "endEvent", "Конец процесса"),
        
        ("task", "task", "Общая задача"),
        ("user_task", "userTask", "Заполнить форму"),
        ("service_task_", "serviceTask", "Обработать данные"),
        
        ("parallel_gateway", "parallelGateway", "Параллельный шлюз"),
        ("exclusive_gateway", "exclusiveGateway", "Эксклюзивный шлюз")
    ]

    # Создание таблицы bpmn_elements
    cursor.execute(
        "CREATE TABLE raw inputs"(
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            input_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        );
        "CREATE TABLE events"(
            id SERIAL PRIMARY KEY,
            name TEXT,
            type TEXT   --start | intermediate | end,
            basic_elements[0], 
            basic_elements[1]
        );
        "CREATE TABLE tasks"(
            id SERIAL PRIMARY KEY,
            name TEXT,
            performer TEXT,
            basic_elements[2],
            basic_elements[3],
            basic_elements[4]
        );
        "CREATE TABLE gateways"(
            id SERIAL PRIMARY KEY,
            condition TEXT,
            basic_elements[5],
            basic_elements[6]
        );
        "CREATE TABLE sequence_flows"(
            id SERIAL PRIMARY KEY,
            from_id INT,
            to_id INT,
            from_type TEXT,
            to_type TEXT,
            condition TEXT
        );
    
    )

    rows = cursor.fetchall()
    cnct.close()
    elements = [{"id": r[0], "type": r[1], "label": r[2]} for r in rows]
    return elements

# Пример использования
Elements = get_bpmn_elements()
for elem in Elements:
    print(elem)



