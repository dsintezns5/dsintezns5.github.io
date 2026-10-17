# КЕПА⚡POE — билды и гайды Path of Exile от Кепки

Сайт со стримерскими билдами и гайдами Path of Exile (PoE 1) — для новичков и не только.
Хостится на **GitHub Pages**, собирается на **Astro 5**.

- 📺 Twitch: https://www.twitch.tv/kepa_mita
- 📺 YouTube: https://www.youtube.com/@Kepa_mita
- ✈️ Telegram: https://t.me/kepa_mita
- 💬 Discord: https://discord.gg/Gefd6QDrB4

## Страницы

| Путь | Что это |
|------|---------|
| `/` | Главная: приветствие, таймер до лиги 3.30, рекомендуемый билд, сетка билдов |
| `/builds/` | Каталог билдов с фильтрами (класс / сложность / бюджет / роль) |
| `/builds/[slug]/` | Страница билда: быстрый старт, кнопка «Скопировать PoB», стадии прогрессии |
| `/newbies/` | Раздел для новичков (в работе) |

## Как добавить/обновить билд

1. Скопируй любой файл из `src/content/builds/` и назови по-своему (kebab-case, латиницей).
2. Заполни поля в шапке (frontmatter):

```markdown
---
title: "Название билда"
description: "1-2 предложения: что за билд, для кого, почему стоит взять."
cls: "Witch"                 # класс игры
ascendancy: "Herald"         # возвышение
skills: ["Lava Lancer"]      # основные скиллы
tags: ["league-starter", "mapping"]   # league-starter | mapping | bossing | endgame | ssf
difficulty: 1                # 1 лёгкий / 2 средний / 3 сложный
budget: "starter"            # starter | mid | expensive
league: "3.30"               # для какой лиги актуален
updated: 2026-11-01          # дата обновления (показывается на карточке и странице)
demo: false                  # true = пометка «ДЕМО» на карточке и странице
pob: "https://pobb.in/..."   # ссылка на PoB (копируется кнопкой)
video: "https://youtube.com/..."  # опционально: видео-гайд
image: "/images/builds/my-build.jpg"  # обложка 16:9, лежит в public/images/builds/
---

Текст гайда в Markdown ниже...
```

3. Положи обложку в `public/images/builds/` (размер ~1200×675).
4. Закоммить и запушь в `main` — GitHub Actions пересоберёт сайт за ~1 минуту.

Каталог, карточки, фильтры и страницы строятся из этих полей автоматически.

## Локальная разработка

```bash
npm install
npm run dev      # dev-сервер http://localhost:4321
npm run build    # сборка в dist/
```

## Деплой

- Репозиторий — user-site, сайт публикуется в корне домена `https://dsintezns5.github.io`.
- GitHub Pages → **Source: GitHub Actions** (см. `.github/workflows/deploy.yml`).
- Пуш в `main` = прод. PR = превью-деплой (ссылка появится в Checks PR).
- Таймер до лиги и дата старта — в `src/pages/index.astro` (константы `LEAGUE_START`, `LEAGUE`).
- Фирменные цвета — в начале `src/styles/global.css` (CSS-переменные `--primary`, `--purple` и т.д.).

## Документация по проекту

- `docs/BRIEF.md` — бриф: решения, таймлайн лиг, открытые вопросы
- `docs/analysis/` — анализ похожих сайтов и технический план
