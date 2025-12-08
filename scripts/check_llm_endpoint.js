#!/usr/bin/env node
// Check if ROO_LLM_URL is set to a remote endpoint or if local Ollama is available

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Load ROO_LLM_URL from .env if not already set
let rooLLMUrl = process.env.ROO_LLM_URL;

if (!rooLLMUrl) {
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const match = envContent.match(/^ROO_LLM_URL=(.+)$/m);
    if (match) {
      rooLLMUrl = match[1].trim().replace(/^["']|["']$/g, '');
    }
  }
}

// Check endpoint type and handle accordingly
const isLocalEndpoint = !rooLLMUrl || 
  rooLLMUrl.includes('localhost') || 
  rooLLMUrl.includes('127.0.0.1');

if (isLocalEndpoint) {
  // Local endpoint - check for Ollama
  try {
    execSync('command -v ollama', { stdio: 'ignore' });
    console.log('\x1b[92mOllama is installed. Using local LLM API endpoint\x1b[0m');
    process.exit(0);
  } catch (e) {
    // Try 'where' command for Windows
    try {
      execSync('where ollama', { stdio: 'ignore' });
      console.log('\x1b[92mOllama is installed. Using local LLM API endpoint\x1b[0m');
      process.exit(0);
    } catch (e2) {
      console.error('Ollama not installed. Install it or set ROO_LLM_URL.');
      process.exit(1);
    }
  }
} else {
  // Remote endpoint - success
  console.log(`\x1b[92mUsing remote LLM endpoint: ${rooLLMUrl}\x1b[0m`);
  process.exit(0);
}

