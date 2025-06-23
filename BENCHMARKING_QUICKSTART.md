# 🚀 RooLLM Benchmarking Quick Start

## ⚡ TL;DR - How to Run Benchmarks

### Option 1: Interactive REPL (Recommended)
```bash
# Start the REPL
python repl.py

# Then use these commands:
/benchmark          # Run all tests
/benchmark tool     # Run tool-specific tests
/benchmark rag      # Run knowledge retrieval tests
/analytics          # Show quality metrics
/analytics 7        # Show last 7 days
```

### Option 2: npm Scripts
```bash
# Show available test cases
npm run benchmark:info

# View analytics
npm run analytics
npm run analytics:week

# For actual benchmarking, use REPL:
npm run benchmark  # (Shows instruction to use REPL)
```

## 🛠️ What Gets Tested

### Tool Accuracy Tests (15 test cases)
- ✅ GitHub operations (create/search/close issues)
- ✅ Calculations (arithmetic, percentages)  
- ✅ Handbook queries (policy lookups)
- ✅ Information retrieval (holidays, vacations)
- ✅ No-tool scenarios (greetings)

### RAG/Knowledge Tests (12 test cases)
- ✅ Organizational knowledge (values, processes)
- ✅ Technical documentation (setup guides)
- ✅ Policy queries (code of conduct, conflict resolution)
- ✅ Contextual reasoning (historical analysis)

### Conversation Flows (6 multi-turn scenarios)
- ✅ Context building across turns
- ✅ Tool chaining workflows
- ✅ Follow-up question handling

## 📊 Evaluation Metrics

1. **Tool Calling Accuracy (40% weight)**
   - Correct tool selection
   - Parameter accuracy
   - Execution success

2. **Response Quality (30% weight)**
   - Relevance to query
   - Helpfulness & completeness
   - Clarity & Roo personality

3. **Hallucination Detection (30% weight)**
   - Factual consistency
   - Tool result integration
   - Appropriate uncertainty

## 🎯 Quick Test

1. **Start REPL:**
   ```bash
   python repl.py
   ```

2. **Run a quick test:**
   ```
   /benchmark tool
   ```

3. **Check results:**
   - Overall score (0.0-1.0)
   - Metric breakdown
   - Success rates

## 📈 View Your Progress

```bash
# In REPL
/analytics

# Or via npm
npm run analytics
```

Shows:
- Manual feedback (👍/👎) rates
- Automated quality scores
- Tool usage statistics
- Quality trends

## 🔧 Configuration

Edit `benchmark_config.yaml` to customize:
- Evaluation thresholds
- Metric weights
- Sampling rates
- Output formats

## 🆘 Troubleshooting

### "No recent logs found"
- Run some conversations first: `python repl.py`
- Ask RooLLM a few questions
- Then check analytics again

### "Event loop" errors
- Use the REPL interface: `python repl.py`
- The `/benchmark` command handles async properly

### Missing test cases
- Check `benchmarks/datasets/` for JSON files
- Verify DeepEval is installed: `pip install deepeval`

## 📝 Example Session

```bash
$ python repl.py

Welcome to RooLLM Chat!
Type '/help' to see available commands

user > /benchmark tool
🧪 Running Benchmark: tool
This may take a few minutes...

📊 Benchmark Results:
Total test cases: 15
Successful evaluations: 14
Overall Score: 0.82

Metric Breakdown:
  tool_accuracy: 0.87 (success rate: 86.7%)
  response_quality: 0.79 (success rate: 78.6%)
  hallucination: 0.85 (success rate: 92.9%)

Execution Time: 23.45 seconds

user > /analytics
📈 Quality Analytics (Last 30 days):
Total interactions: 127
Manual feedback: 12👍 / 3👎 (11.8% response rate)
Automated evaluations: 45
Average quality score: 0.78
```

## 🎉 You're Ready!

The benchmarking system is now set up and ready to help you track RooLLM's performance over time. Start with `/benchmark tool` to get familiar with the system! 