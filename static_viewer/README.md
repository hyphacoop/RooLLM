# RooLLM Static Dashboard

A static, GitHub Pages-compatible dashboard for viewing RooLLM benchmark results without requiring a backend server.

## 🌟 Features

- **Static Site**: No backend required - serves directly from GitHub Pages
- **Interactive Charts**: Full Chart.js integration for data visualization
- **Model Comparison**: Compare performance across different LLM models
- **Test Case Details**: Drill down into individual test case results
- **Responsive Design**: Works on desktop and mobile devices
- **Offline Capable**: Works without internet once loaded

## 🚀 Quick Start

### Option 1: Development Server (Recommended)

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Then open [http://localhost:4173](http://localhost:4173) in your browser.

### Option 2: Simple HTTP Server

```bash
# Using Python (if available)
python -m http.server 8080

# Or using Node.js
npx http-server -p 8080 -o
```

## 📊 Data Management

### Current Data

The dashboard loads data from the `./data/` directory:

- `multi_model_summary.json` - Overview of all benchmark results
- `tool_survey_{model_name}.json` - Detailed results for each model

### Updating Data

#### Method 1: Automatic Snapshot (Recommended)

If you have the RooLLM API server running:

```bash
# Set API URL if different from localhost:8080
export API_BASE_URL="http://localhost:8080"

# Run snapshot
npm run snapshot
```

#### Method 2: Manual Copy

Copy the latest results from your benchmarks directory:

```bash
# Copy from the main benchmarks directory
cp ../benchmarks/comprehensive_model_results/*.json ./data/
```

## 🚀 Deployment to GitHub Pages

### Step 1: Prepare Repository

1. Create a new repository on GitHub (or use existing)
2. Push this `static_viewer` folder as the root of the repository

### Step 2: Enable GitHub Pages

1. Go to repository Settings → Pages
2. Select "Deploy from a branch"
3. Choose the main branch and `/` (root) folder
4. Save changes

### Step 3: Access Your Dashboard

Your dashboard will be available at: `https://yourusername.github.io/repository-name`

## 📁 Project Structure

```
static_viewer/
├── index.html          # Main dashboard page
├── js/
│   └── data-loader.js  # Static data loading utilities
├── data/               # JSON data files
├── tools/
│   └── snapshot.mjs    # Data snapshot script
├── package.json        # NPM configuration
└── README.md          # This file
```

## 🔧 Customization

### Adding New Data Sources

1. Add your JSON data file to `./data/`
2. Update `js/data-loader.js` to include a function for your data
3. Use the new function in `index.html`

Example:

```javascript
// In data-loader.js
export async function getCustomData() {
    return loadJSON('./data/custom_data.json');
}
```

### Styling Changes

The dashboard uses inline CSS for portability. To modify styles:

1. Edit the `<style>` section in `index.html`
2. Or create a separate CSS file and link it

### Chart Configuration

Charts are configured in the JavaScript section of `index.html`. The dashboard uses:
- Chart.js for all charts
- Chart.js Date Adapter for time-based charts

## 🐛 Troubleshooting

### Common Issues

**Dashboard shows "No Results Found"**
- Check that data files exist in `./data/`
- Verify JSON files are valid
- Ensure filenames match what `data-loader.js` expects

**Charts not loading**
- Check browser console for JavaScript errors
- Verify Chart.js CDN is accessible
- Ensure data format matches chart expectations

**CORS errors when snapshotting**
- Make sure API server allows cross-origin requests
- Or copy data files manually

### Browser Compatibility

Tested on:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Mobile Support

The dashboard is responsive and works on:
- iOS Safari
- Android Chrome
- Mobile Firefox

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## 📄 License

This project is part of RooLLM and follows the same license terms.

## 🔗 Related Projects

- [RooLLM Main Repository](https://github.com/your-org/roollm)
- [RooLLM Benchmarks](https://github.com/your-org/roollm-benchmarks)

## 📞 Support

For questions or issues:
1. Check the troubleshooting section above
2. Open an issue in the repository
3. Contact the RooLLM development team
