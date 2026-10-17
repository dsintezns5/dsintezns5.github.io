import { defineCollection, z } from 'astro:content';

// Один билд = один .md файл в src/content/builds/.
// Поля в шапке (frontmatter) автоматически строят карточку, фильтры и страницу.
const builds = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    cls: z.string(), // класс игры: Marauder, Witch, ...
    ascendancy: z.string(), // возвышение: Chieftain, Elementalist, ...
    skills: z.array(z.string()).default([]),
    tags: z.array(z.enum(['league-starter', 'mapping', 'bossing', 'endgame', 'ssf'])).default([]),
    difficulty: z.number().int().min(1).max(3), // 1=лёгкий, 3=сложный
    budget: z.enum(['starter', 'mid', 'expensive']),
    league: z.string(), // для какой лиги актуален, напр. "3.30"
    updated: z.coerce.date(),
    demo: z.boolean().default(false), // демо-заглушка до реального контента
    pob: z.string(), // ссылка на PoB
    video: z.string().optional(), // ссылка на видео-гайд
    image: z.string(), // обложка /images/builds/...
  }),
});

export const collections = { builds };
