# Clips Kitty — локальные модификации

Патчи для Windows-сборки [Clips Kitty](https://github.com/ColinGPT9/clips-studio). В них входят шаблоны монтажа, несколько дополнительных видео на один клип, локальная анимация шарика и колец, обрезка и восстановление клипов, ручная цензура слов и окно прогресса очереди.

Для сборки нужна совместимая распакованная версия Clips Kitty и исходные файлы патчера `repair/before-template-and-branding/api.exe` и `repair/before-template-and-branding/app.asar`. Первый файл должен включать исправление совместимости с FFmpeg, второй — интерфейс до применения локальных патчей. Сохраните эти два файла из рабочей копии рядом с исходниками патчей.

Из корневой папки сборки в PowerShell запустите:

```powershell
$env:CLIPSKITTY_SCRIPT_HOST = '1'
& ./resources/backend/api.exe ./repair/build_features.py
```

Скрипт подготовит `resources/backend/api.features.exe` и `resources/app.features.asar`. Закройте приложение и сделайте резервные копии перед заменой `api.exe` и `app.asar`.

Этот репозиторий хранит код патчей, скрипты и проверки. Для запуска нужна отдельная Windows-сборка с зависимостями. Оригинальный Clips Kitty распространяется по [AGPL-3.0](https://github.com/ColinGPT9/clips-studio/blob/main/LICENSE).
