#!/usr/bin/env node

import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const EMOJI_TEST_URL = 'https://unicode.org/Public/emoji/15.1/emoji-test.txt';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OUTPUT_PATH = path.resolve(__dirname, '../src/app/shared/emoji/emoji-data.ts');

const CATEGORY_LABEL_MAP = {
    'Smileys & Emotion': 'Смайлики и эмоции',
    'Animals & Nature': 'Животные и природа',
    'Food & Drink': 'Еда и напитки',
    'Travel & Places': 'Путешествия и места',
    Activities: 'Активности',
    Objects: 'Объекты',
    Symbols: 'Символы',
    Flags: 'Флаги',
    Component: 'Компоненты'
};

const EXCLUDED_GROUPS = new Set(['People & Body']);
const ZERO_WIDTH_JOINER = '\u200d';



function fetchText(url) {
    return new Promise((resolve, reject) => {
        https.get(url, (res) => {
            if (res.statusCode && res.statusCode >= 400) {
                reject(new Error('Failed to download emoji data. Status code: ' + res.statusCode));
                return;
            }

            let data = '';
            res.setEncoding('utf8');
            res.on('data', (chunk) => {
                data += chunk;
            });
            res.on('end', () => resolve(data));
        }).on('error', reject);
    });
}

const WORD_REGEX = /[a-z0-9#+]+/gi;

function tokenize(value) {
    if (!value) {
        return [];
    }
    const matches = value.toLowerCase().match(WORD_REGEX);
    return matches ? matches : [];
}

function slugify(value) {
    return value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function formatKeywords(keywords) {
    return JSON.stringify(keywords);
}

async function main() {
    console.log('📥  Downloading emoji data from Unicode...');
    const raw = await fetchText(EMOJI_TEST_URL);

    const lines = raw.split(/\r?\n/);
    let currentGroup = '';
    let currentSubgroup = '';
    let skipCurrentGroup = false;

    const categories = [];
    const categoryMap = new Map();
    const emojis = [];
    let skippedByJoiner = 0;
    let skippedByGroup = 0;

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) {
            continue;
        }

        if (line.startsWith('# group:')) {
            currentGroup = line.replace('# group:', '').trim();
            currentSubgroup = '';
            skipCurrentGroup = EXCLUDED_GROUPS.has(currentGroup);
            continue;
        }

        if (line.startsWith('# subgroup:')) {
            currentSubgroup = line.replace('# subgroup:', '').trim();
            continue;
        }

        if (line.startsWith('#')) {
            continue;
        }

        if (skipCurrentGroup) {
            skippedByGroup++;
            continue;
        }

        const parts = line.split('#');
        if (parts.length < 2) {
            continue;
        }

        const definition = parts[0];
        const comment = parts[1].trim();

        if (!definition.includes('fully-qualified')) {
            continue;
        }

        const commentParts = comment.split(/\s+/);
        if (commentParts.length < 3) {
            continue;
        }

        const symbol = commentParts[0];
        const name = commentParts.slice(2).join(' ');

        if (symbol.includes(ZERO_WIDTH_JOINER)) {
            skippedByJoiner++;
            continue;
        }

        const categoryLabel = CATEGORY_LABEL_MAP[currentGroup] ?? currentGroup;
        const categoryId = slugify(currentGroup);

        if (!categoryMap.has(categoryId)) {
            const categoryEntry = {
                id: categoryId,
                label: categoryLabel,
                icon: symbol
            };
            categories.push(categoryEntry);
            categoryMap.set(categoryId, categoryEntry);
        }

        const keywordsSet = new Set();
        tokenize(name).forEach((word) => keywordsSet.add(word));
        tokenize(currentSubgroup).forEach((word) => keywordsSet.add(word));
        tokenize(currentGroup).forEach((word) => keywordsSet.add(word));

        const keywords = Array.from(keywordsSet).sort();

        emojis.push({
            symbol: symbol,
            name: name,
            category: categoryId,
            keywords: keywords
        });
    }

    const header = [
        'export interface EmojiCategory {',
        '    readonly id: string;',
        '    readonly label: string;',
        '    readonly icon: string;',
        '}',
        '',
        'export interface EmojiDefinition {',
        '    readonly symbol: string;',
        '    readonly name: string;',
        '    readonly category: string;',
        '    readonly keywords: readonly string[];',
        '}',
        ''
    ].join('\n');

    const categoryLines = categories
        .map((cat) => '    { id: ' + JSON.stringify(cat.id) + ', icon: ' + JSON.stringify(cat.icon) + ', label: ' + JSON.stringify(cat.label) + ' },')
        .join('\n');

    const emojiLines = emojis
        .map((emoji) => '    { symbol: ' + JSON.stringify(emoji.symbol) + ', name: ' + JSON.stringify(emoji.name) + ', category: ' + JSON.stringify(emoji.category) + ', keywords: ' + formatKeywords(emoji.keywords) + ' },')
        .join('\n');

    const fileContent = [
        header,
        'export const EMOJI_CATEGORIES: readonly EmojiCategory[] = [',
        categoryLines,
        '];',
        '',
        'export const EMOJI_DATA: readonly EmojiDefinition[] = [',
        emojiLines,
        '];',
        ''
    ].join('\n');

    fs.writeFileSync(OUTPUT_PATH, fileContent, 'utf8');
    console.log('✅  Emoji data generated: ' + OUTPUT_PATH);
    console.log('   Categories: ' + categories.length + ', Emojis: ' + emojis.length);
    if (skippedByGroup) {
        console.log('   Skipped by group filter: ' + skippedByGroup);
    }
    if (skippedByJoiner) {
        console.log('   Skipped ZWJ sequences: ' + skippedByJoiner);
    }
}

main().catch((error) => {
    console.error('❌  Failed to generate emoji data');
    console.error(error);
    process.exit(1);
});
