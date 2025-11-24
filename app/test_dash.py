# test_dashboard_api.py

import requests
import json

API_BASE = "http://localhost:8000"

def test_dashboard_summary_test():
    print("🧪 Тестируем /api/dashboard-summary-test")
    print("="*60)

    # Параметры
    params = {
        "start_date": "2019-11-21",
        "end_date": "2019-11-30"
    }

    url = f"{API_BASE}/api/dashboard-summary-test"
    print(f"📍 Отправляем GET на: {url}")
    print(f"📅 Параметры: {params}")
    print("-" * 60)

    try:
        response = requests.get(url, params=params)

        print(f"📡 Статус ответа: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            return

        data = response.json()
        print("✅ Ответ получен (JSON):")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        print("-" * 60)
        print("📊 Анализ ответа:")

        # Проверим, что возвращается
        period = data.get("period", "N/A")
        summary_by_day = data.get("summary_by_day", [])
        high_risk_incidents = data.get("high_risk_incidents", [])

        print(f"📅 Период: {period}")
        print(f"📈 Прогнозов по дням: {len(summary_by_day)}")
        print(f"🔥 Высокорисковых событий: {len(high_risk_incidents)}")

        if high_risk_incidents:
            print("\n🔥 Примеры высокорисковых событий:")
            for i, event in enumerate(high_risk_incidents[:3]):  # первые 3
                print(f"  {i+1}. Дата: {event.get('date')}, Склад: {event.get('warehouse')}, Штабель: {event.get('pile_id')}")

        if summary_by_day:
            print("\n📈 Примеры прогнозов по дням:")
            for i, day in enumerate(summary_by_day[:5]):  # первые 5
                print(f"  {i+1}. {day.get('date')}: {day.get('count')} рисков")

    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к серверу. Убедитесь, что uvicorn запущен на http://localhost:8000")
    except requests.exceptions.JSONDecodeError:
        print("❌ Ответ не в формате JSON:")
        print(response.text)
    except Exception as e:
        print(f"💥 Неожиданная ошибка: {e}")


if __name__ == "__main__":
    test_dashboard_summary_test()