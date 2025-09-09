// data-loader.js - Static data loader to replace API calls
async function loadJSON(path) {
    const response = await fetch(path);
    if (!response.ok) {
        throw new Error(`Failed to load ${path}: ${response.status}`);
    }
    return response.json();
}

// Load latest results (replaces /api/latest-results)
async function getLatestResults() {
    try {
        return await loadJSON('./data/multi_model_summary.json');
    } catch (error) {
        console.error('Failed to load latest results:', error);
        // Return empty data structure if file doesn't exist
        return {
            timestamp: new Date().toISOString(),
            total_models: 0,
            models_tested: [],
            results: []
        };
    }
}

// Load model details (replaces /api/model-details/{modelName})
async function getModelDetails(modelName) {
    try {
        // Convert model name to filename format (replace : with _)
        const filename = `tool_survey_${modelName.replace(':', '_')}.json`;
        return await loadJSON(`./data/${filename}`);
    } catch (error) {
        console.error(`Failed to load model details for ${modelName}:`, error);
        throw error;
    }
}

// Load test details (replaces /api/test-details/{modelName}/{testCaseIndex})
async function getTestDetails(modelName, testCaseIndex) {
    try {
        const modelData = await getModelDetails(modelName);

        if (!modelData.test_cases || testCaseIndex >= modelData.test_cases.length) {
            throw new Error(`Test case ${testCaseIndex} not found for model ${modelName}`);
        }

        const testCase = modelData.test_cases[testCaseIndex];

        return {
            model_name: modelName,
            test_case_index: testCaseIndex,
            input: testCase.input || '',
            expected_output: testCase.expected_output || '',
            actual_output: testCase.actual_output || {},
            tool_calls: testCase.tool_calls || [],
            expected_tools: testCase.expected_tools || [],
            success: testCase.success || false,
            metrics: testCase.metrics || {},
            context: testCase.context || []
        };
    } catch (error) {
        console.error(`Failed to load test details for ${modelName}/${testCaseIndex}:`, error);
        throw error;
    }
}
