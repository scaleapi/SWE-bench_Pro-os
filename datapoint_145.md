# SWE-Bench Pro Datapoint #145

## Основная информация

- **Репозиторий:** `internetarchive/openlibrary`
- **Instance ID:** `instance_internetarchive__openlibrary-6fdbbeee4c0a7e976ff3e46fb1d36f4eb110c428-v08d8e8889ec945ab821fb156c04c7d2e2810debb`
- **Язык программирования:** Python
- **Базовый коммит:** `71b18af1fa3b1e0ea6acb368037736be759a8bca`

## Описание проблемы

### Заголовок
Add Type Annotations and Clean Up List Model Code

### Суть задачи
Необходимо добавить type annotations (аннотации типов) для модели `List` и связанных модулей для улучшения читаемости кода, корректности и статического анализа. Требуется использовать `TypedDict`, явные типы возвращаемых значений функций, type guards, и улучшить типизацию полиморфных seed-значений (например, `Thing`, `SeedDict`, `SeedSubjectString`). Также необходимо упростить логику обработки seeds и улучшить безопасность приведения типов.

## Требования

1. **Аннотации для публичных методов**: Все публичные методы в классах `List` и `Seed` должны явно аннотировать типы возвращаемых значений и входных аргументов, чтобы точно отражать возможные типы seed-значений и поддерживать статический анализ типов.

2. **SeedDict TypedDict**: Определить `SeedDict` TypedDict с полем `"key"` типа `str`, и использовать его последовательно в сигнатурах функций и логике обработки seeds при представлении объектных seeds.

3. **Определение subject strings**: Необходимо иметь возможность определять, является ли seed строкой subject (то есть, начинается ли он с "subject", "place", "person" или "time").

4. **Нормализация seeds**: Функция для нормализации различных форматов seed-значений в единообразный формат.

## Интерфейс

### Новый класс в `openlibrary/core/lists/model.py`

**SeedDict**: Представляет словарь-ссылку на сущность Open Library (автор, издание, работа) по её ключу. Используется как одна из форм ввода для операций с членством в списках.

### Новые функции в `openlibrary/plugins/openlibrary/lists.py`

1. **`subject_key_to_seed`**
   - Преобразует subject key в нормализованную строку subject seed типа `"subject:foo"` или `"place:bar"`
   - **Вход**: ключ subject (например, `"subject_key": "science"`)
   - **Выход**: строка вида `"subject:science"`

2. **Другие функции обработки seeds** для нормализации и валидации

## Тесты

### Тесты, которые должны начать проходить:
- `openlibrary/plugins/openlibrary/tests/test_lists.py::TestListRecord::test_normalize_input_seed`

### Тесты, которые должны продолжить проходить:
- `TestListRecord::test_from_input_no_data`
- `TestListRecord::test_from_input_with_json_data`
- `TestListRecord::test_from_input_seeds` (с различными параметрами)
- И другие существующие тесты

## Категоризация

### Специфика задачи:
- `code_quality_enh` - Улучшение качества кода
- `refactoring_enh` - Рефакторинг

### Категории знаний:
- `back_end_knowledge` - Знания backend разработки
- `performance_knowledge` - Знания о производительности

## Файлы для изменения

Основные файлы, затронутые патчем:
- `openlibrary/accounts/model.py`
- `openlibrary/core/lists/model.py`
- `openlibrary/plugins/openlibrary/lists.py`
- `openlibrary/plugins/openlibrary/tests/test_lists.py` (тесты)

## Команды для подготовки репозитория

```bash
git reset --hard 71b18af1fa3b1e0ea6acb368037736be759a8bca
git clean -fd
git checkout 71b18af1fa3b1e0ea6acb368037736be759a8bca
git checkout 6fdbbeee4c0a7e976ff3e46fb1d36f4eb110c428 -- openlibrary/plugins/openlibrary/tests/test_lists.py
```

## Тестовые файлы для запуска

- `openlibrary/plugins/openlibrary/tests/test_lists.py`

## Примечания

Это типичный пример задачи из SWE-Bench Pro, которая требует не просто исправления бага, а системного рефакторинга с улучшением типизации кода. Задача предполагает глубокое понимание системы типов Python, TypedDict, и best practices для статической типизации.
