#!/usr/bin/env node
/**
 * Snapshot script to pull data from RooLLM API endpoints
 * Usage: node tools/snapshot.mjs
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, '../data');

// Ensure data directory exists
await fs.mkdir(dataDir, { recursive: true });

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8080';

/**
 * Fetch data from API endpoint and save to file
 */
async function snapshot(endpoint, filename) {
    const url = `${API_BASE_URL}${endpoint}`;

    try {
        console.log(`📡 Fetching ${url}...`);

        // For Node.js, we need to use fetch if available, or fall back to other methods
        let response;
        if (typeof fetch === 'undefined') {
            // If fetch is not available, try using a simple HTTP client
            console.log(`⚠️  Fetch not available, trying alternative method...`);
            console.log(`💡 Copy data manually from ${url} to ${filename}`);
            return;
        }

        response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        const filePath = path.join(dataDir, filename);

        await fs.writeFile(filePath, JSON.stringify(data, null, 2));
        console.log(`✅ Saved ${filename} (${JSON.stringify(data).length} chars)`);

    } catch (error) {
        console.error(`❌ Failed to fetch ${url}:`, error.message);
        console.log(`💡 Make sure the API server is running or copy data manually`);
    }
}

/**
 * Main snapshot function
 */
async function main() {
    console.log('🚀 Starting data snapshot from RooLLM API...\n');

    try {
        // Snapshot latest results
        await snapshot('/api/latest-results', 'multi_model_summary.json');

        // Get the list of models from the summary to snapshot individual model details
        const summaryPath = path.join(dataDir, 'multi_model_summary.json');

        try {
            const summaryData = JSON.parse(await fs.readFile(summaryPath, 'utf8'));

            if (summaryData.models_tested) {
                console.log(`\n📊 Found ${summaryData.models_tested.length} models to snapshot...`);

                for (const modelName of summaryData.models_tested) {
                    const filename = `tool_survey_${modelName.replace(':', '_')}.json`;
                    await snapshot(`/api/model-details/${encodeURIComponent(modelName)}`, filename);
                }
            }
        } catch (error) {
            console.log('⚠️  Could not read summary file to get model list, skipping individual model snapshots');
        }

    } catch (error) {
        console.error('💥 Snapshot failed:', error);
        process.exit(1);
    }

    console.log('\n🎉 Snapshot complete!');
    console.log('📁 Data saved to:', dataDir);
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(console.error);
}

export { main as snapshot };
