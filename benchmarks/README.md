# RooLLM Benchmarking System

A comprehensive benchmarking system for RooLLM using DeepEval framework to evaluate LLM performance across tool calling accuracy, response quality, and hallucination detection.

## 🚀 Quick Start

> **⚡ Want to get started immediately?** Check out [BENCHMARKING_QUICKSTART.md](../BENCHMARKING_QUICKSTART.md)

### Prerequisites

1. Install DeepEval:
```bash
pip install deepeval
```

2. Ensure RooLLM is properly configured with your environment variables

### Running Benchmarks

#### From the REPL (Recommended)
```bash
python repl.py
```

Then use the interactive commands:
- `/benchmark` - Run full benchmark suite
- `/benchmark tool` - Run tool-focused tests only
- `/benchmark rag` - Run RAG/knowledge tests only
- `/analytics` - Show quality analytics (last 30 days)
- `/analytics 7` - Show analytics for last 7 days

#### npm Scripts (For Analytics & Info)
```bash
# Show info about available tests
npm run benchmark:info

# Show analytics
npm run analytics
npm run analytics:week

# For actual benchmarking
npm run benchmark  # (Shows instruction to use REPL)
```

#### Simple CLI (For Scripting)
```bash
# Show analytics
python benchmarks/simple_cli.py analytics --days 7

# Show test case information
python benchmarks/simple_cli.py benchmark-info --dataset tool
```

> **Note**: Full benchmarking requires async handling, so we recommend using the REPL interface (`python repl.py`) which properly manages the event loop. The simple CLI is perfect for analytics and getting information about test cases.

## 📊 Evaluation Metrics

### 1. Tool Calling Accuracy (40% weight)
- **Measures**: Correct tool selection, parameter accuracy, execution success
- **Threshold**: 0.8 (configurable)
- **Key Features**:
  - Validates expected vs actual tool usage
  - Checks parameter matching with fuzzy string matching
  - Tracks tool execution success rates

### 2. Response Quality (30% weight)
- **Measures**: Relevance, helpfulness, clarity, personality appropriateness
- **Threshold**: 0.7 (configurable)
- **Components**:
  - Relevance to user query (30%)
  - Helpfulness and completeness (30%)
  - Clarity and coherence (25%)
  - Roo personality appropriateness (15%)

### 3. Hallucination Detection (30% weight)
- **Measures**: Factual consistency, tool result integration, uncertainty expression
- **Threshold**: 0.8 (configurable)
- **Components**:
  - Factual consistency with context (40%)
  - Tool result consistency (30%)
  - Appropriate uncertainty expression (20%)
  - Source citation accuracy (10%)

## 🗂️ Test Datasets

### Tool Test Cases (`tool_test_cases.json`)
- GitHub operations (issue creation, search, management)
- Calculations (arithmetic, percentages)
- Handbook queries (policy lookups)
- Information queries (holidays, vacations)
- No-tool scenarios (greetings, capability questions)

### RAG Test Cases (`rag_test_cases.json`)
- Knowledge retrieval (organizational values, processes)
- Technical documentation (setup guides, requirements)
- Policy queries (code of conduct, conflict resolution)
- Contextual queries (historical analysis, evolution tracking)

### Conversation Flows (`conversation_flows.json`)
- Multi-turn conversations with context building
- Tool chaining workflows
- Context-aware follow-up responses

## 📈 Continuous Evaluation

The system includes real-time evaluation capabilities:

### Features
- **Sampling**: Evaluates 10% of responses by default (configurable)
- **Lightweight**: Uses subset of metrics to minimize impact
- **Integration**: Seamlessly integrates with existing stats system
- **Alerts**: Configurable quality threshold alerts

### Configuration
Edit `benchmark_config.yaml` to customize:
- Sampling rates
- Evaluation thresholds  
- Metric weights
- Output formats

## 🔧 Configuration

### Benchmark Configuration (`benchmark_config.yaml`)

```yaml
# Evaluation Thresholds
thresholds:
  tool_accuracy: 0.8
  response_quality: 0.7
  hallucination: 0.8

# Continuous Evaluation
continuous_eval:
  enabled: true
  sampling_rate: 0.1
  min_response_length: 10

# Metric Weights
metric_weights:
  tool_accuracy: 0.4
  response_quality: 0.3
  hallucination: 0.3
```

## 📋 Results and Analytics

### Benchmark Results Include:
- **Summary Statistics**: Total tests, success rates, score distributions
- **Metric Breakdown**: Individual scores for each evaluation metric
- **Category Analysis**: Performance by test category
- **Execution Metrics**: Response times, evaluation overhead

### Analytics Features:
- **Quality Trends**: Track improvement/degradation over time
- **Tool Usage**: Most used tools, success rates, performance
- **Manual vs Automated**: Compare human feedback with automated scores
- **Distribution Analysis**: Score ranges and patterns

## 🏗️ Architecture

```
benchmarks/
├── __init__.py                 # Module initialization
├── evaluators/                 # Evaluation metrics
│   ├── tool_accuracy.py       # Tool calling accuracy
│   ├── response_quality.py    # Response quality assessment  
│   └── hallucination.py       # Hallucination detection
├── runners/                    # Benchmark execution
│   ├── benchmark_runner.py    # Main benchmark orchestrator
│   └── continuous_eval.py     # Real-time evaluation
├── datasets/                   # Test cases
│   ├── tool_test_cases.json   # Tool-focused tests
│   ├── rag_test_cases.json    # Knowledge retrieval tests
│   └── conversation_flows.json # Multi-turn conversations
├── simple_cli.py               # Simple CLI for analytics and info
└── README.md                   # This file
```

## 🧪 Adding New Test Cases

### Single Response Tests
```json
{
  "id": "test_001",
  "input": "User query here",
  "expected_tool": "tool_name",
  "expected_params": {
    "param1": "value1"
  },
  "expected_output": "Expected response",
  "description": "Test description",
  "category": "test_category"
}
```

### Multi-turn Conversations
```json
{
  "id": "conv_001", 
  "conversation": [
    {
      "turn": 1,
      "input": "First message",
      "expected_tool": "tool_name"
    },
    {
      "turn": 2,
      "input": "Follow-up message",
      "expected_tool": "another_tool"
    }
  ],
  "description": "Conversation description",
  "category": "conversation_category"
}
```

## 📊 Example Output

```
🧪 Running Benchmark: tool

📊 Benchmark Results:
Total test cases: 15
Successful evaluations: 14
Failed evaluations: 1
Overall Score: 0.82
Score Range: 0.45 - 0.95

Metric Breakdown:
  tool_accuracy: 0.87 (success rate: 86.7%)
  response_quality: 0.79 (success rate: 78.6%)
  hallucination: 0.85 (success rate: 92.9%)

Execution Time: 23.45 seconds
```

## 🔗 Integration Points

### Stats System Integration
- Automatic logging of benchmark scores
- Quality analytics dashboard
- Trend analysis and alerting

### REPL Integration  
- Interactive benchmark commands
- Real-time quality feedback
- User-friendly result display

### Bridge Integration
- Hooks into message processing
- Tool execution monitoring
- Response quality assessment

## 🚀 Future Enhancements

1. **Advanced Metrics**: Custom domain-specific evaluations
2. **ML-Powered Evaluation**: LLM-based judges for complex assessments
3. **Automated Regression Testing**: CI/CD integration for model updates
4. **Performance Benchmarking**: Response time and resource usage tracking
5. **A/B Testing**: Compare different model configurations
6. **Dashboard**: Web-based visualization of results and trends

## 🤝 Contributing

1. **Add new test cases** to appropriate dataset files in `benchmarks/datasets/`
2. **Create custom evaluators** by extending `BaseMetric` in `benchmarks/evaluators/`
3. **Enhance continuous evaluation** with new sampling strategies in `continuous_eval.py`
4. **Improve analytics** with additional insights in `stats.py` and `simple_cli.py`
5. **Add new output formats** or visualization options
6. **Extend REPL commands** for new benchmarking features in `repl.py`

### Available Interfaces

- **🎯 REPL (Primary)**: `python repl.py` - Full benchmarking with `/benchmark` commands
- **📊 Simple CLI**: `benchmarks/simple_cli.py` - Analytics and test case information
- **🔧 npm Scripts**: Convenient wrappers for common operations

## 📝 License

This benchmarking system is part of the RooLLM project and follows the same license terms. 