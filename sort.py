import pandas as pd

# Загружаем CSV-файл
df = pd.read_csv('app/data/temperature.csv')

# Удалим лишние пробелы в названиях колонок (на всякий случай)
df.columns = df.columns.str.strip()

# Пример 1: Сортировка по максимальной температуре по убыванию
df_sorted = df.sort_values(by='Максимальная температура', ascending=False)

# Пример 2: Сортировка по дате и затем по температуре
# Сначала убедимся, что столбец 'Дата акта' имеет тип datetime
df['Дата акта'] = pd.to_datetime(df['Дата акта'])

df_sorted = df.sort_values(by=['Дата акта', 'Максимальная температура'], ascending=[True, False])

# Если нужно — сохранить результат в новый CSV
df_sorted.to_csv('app/data/temperature_sorted.csv', index=False)

# Показать первые 10 строк отсортированного датафрейма
print(df_sorted.head(10))