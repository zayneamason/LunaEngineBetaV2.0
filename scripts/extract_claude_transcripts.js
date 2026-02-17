#!/usr/bin/env node
/**
 * Extract Claude.ai conversation transcripts from LevelDB stores
 */

const { ClassicLevel } = require('classic-level');
const fs = require('fs');
const path = require('path');

const HOME = process.env.HOME;
const CLAUDE_DIR = path.join(HOME, 'Library/Application Support/Claude');
const OUTPUT_DIR = path.join(__dirname, '../Tools/MemoryMatrix_SandBox/_CLAUDE_TRANSCRIPTS');

// LevelDB locations to check
const DB_PATHS = {
  sessionStorage: path.join(CLAUDE_DIR, 'Session Storage'),
  localStorage: path.join(CLAUDE_DIR, 'Local Storage/leveldb'),
  indexedDB: path.join(CLAUDE_DIR, 'IndexedDB/https_claude.ai_0.indexeddb.leveldb')
};

async function extractDatabase(dbPath, name) {
  console.log(`\n=== Extracting from ${name} ===`);
  console.log(`Path: ${dbPath}`);

  if (!fs.existsSync(dbPath)) {
    console.log(`Database not found: ${dbPath}`);
    return [];
  }

  const entries = [];

  try {
    const db = new ClassicLevel(dbPath, { keyEncoding: 'buffer', valueEncoding: 'buffer' });
    await db.open();

    return new Promise((resolve, reject) => {
      const stream = db.iterator();

      (async () => {
        try {
          for await (const [key, value] of stream) {
            try {
              const keyStr = key.toString('utf8', 0, Math.min(key.length, 200));
              const valueStr = value.toString('utf8', 0, Math.min(value.length, 1000));

              entries.push({
                key: keyStr,
                value: valueStr,
                keyRaw: key.toString('hex').substring(0, 100),
                valuePreview: valueStr.substring(0, 200)
              });

              // Log interesting keys
              if (keyStr.includes('conversation') || keyStr.includes('chat') || keyStr.includes('message') || keyStr.includes('transcript')) {
                console.log(`Found: ${keyStr.substring(0, 100)}`);
              }
            } catch (err) {
              // Skip binary data that can't be parsed
            }
          }
          console.log(`Total entries: ${entries.length}`);
          await db.close();
          resolve(entries);
        } catch (err) {
          console.error(`Error reading ${name}:`, err.message);
          reject(err);
        }
      })();
    });
  } catch (err) {
    console.error(`Failed to open ${name}:`, err.message);
    return [];
  }
}

async function main() {
  console.log('Claude Transcript Extraction Tool');
  console.log('==================================\n');

  // Create output directory
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const allData = {};

  // Extract from each database
  for (const [name, dbPath] of Object.entries(DB_PATHS)) {
    const entries = await extractDatabase(dbPath, name);
    allData[name] = entries;

    // Save raw dump
    const dumpFile = path.join(OUTPUT_DIR, `${name}_dump.json`);
    fs.writeFileSync(dumpFile, JSON.stringify(entries, null, 2));
    console.log(`Saved dump to: ${dumpFile}`);
  }

  // Generate summary
  const summary = {
    timestamp: new Date().toISOString(),
    databases: Object.keys(allData).map(name => ({
      name,
      path: DB_PATHS[name],
      entries: allData[name].length,
      sampleKeys: allData[name].slice(0, 10).map(e => e.key)
    }))
  };

  const summaryFile = path.join(OUTPUT_DIR, 'extraction_summary.json');
  fs.writeFileSync(summaryFile, JSON.stringify(summary, null, 2));
  console.log(`\nSummary saved to: ${summaryFile}`);

  console.log('\n=== Extraction Complete ===');
  console.log(`Output directory: ${OUTPUT_DIR}`);
}

main().catch(console.error);
