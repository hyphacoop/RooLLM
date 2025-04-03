# RooLLM

RooLLM is a conversational AI assistant designed for Hypha Worker Coop to streamline organizational workflows and enhance productivity. Powered by large language models through Ollama, Roo offers a variety of tool calls such as GitHub integration and organizational support capabilities.

## Overview

Roo serves as Hypha's digital assistant, providing access to an LLM through an Ollama API endpoint running on a GPU in our datacenter. This project is designed to be flexible - it can run fully locally by installing Ollama and running the model yourself, or connect to a hosted endpoint.

### Key Features

- **GitHub Integration**: Manage issues, pull requests, comments, labels, and other GitHub operations directly through chat
- **Documentation Search**: Quickly search through Hypha's handbook
- **Organizational Tools**: Access calendar information, vacation tracking, and other organizational data
- **Multiple Interfaces**: Use either the web interface or CLI according to your workflow

Roo is built to be extensible, with a modular tool system that makes it easy to add new capabilities as needed.

## Installation

### Requirements

To run RooLLM, ensure you have the following installed:

- **Python**: Version 3.8 or higher
- **Node.js**: Version 16 or higher
- **Pip**: Python package manager (use `pip3` if necessary)

Additionally, if you plan to run the project locally with Ollama, ensure you have installed [Ollama](https://ollama.com/download).

### Install Dependencies

To install the project dependencies, run:

```bash
pip install -r requirements.txt && npm install
```

You might need to use pip3:

```bash
pip3 install -r requirements.txt && npm install
```

### Set Environment Variables

To set the environment variables, run the following command to copy the example:

```bash
cp .env.example .env
```

You can edit the `.env` file with the following required credentials:

#### Required credentials

1. `ROO_LLM_MODEL`: The model to use.

Hypha's API endpoint currently runs the hermes3 model. If you are running ollama locally, you can experiment with other models. See the [ollama website](https://ollama.com/) for installation instructions and commands for downloading a specific model.

2. `ROO_LLM_URL`: The URL of the ollama endpoint.

This can be any ollama endponit. You can run your own or use Hypha's ollama API endpoint URL.
If you are running ollama locally, the default URL is `http://localhost:11434`.

##### Hypha's API endpoint

Our endpoint is running on basic auth. To access it, you will need to set the `ROO_LLM_AUTH_USERNAME` and `ROO_LLM_AUTH_PASSWORD` environment variables.

Access to Hypha's API endpoint is currently limited to friends and collaborators. Please reach out to the Hypha team for more information if you're interested in accessing our hosted endpoint.

#### Optional credentials
##### Github

The github tools provide access to the github api by using a personal access token (pat) or through a github app.

###### PAT

1. `GITHUB_TOKEN`: a github personal access token to access the github api and have RooLLM take actions from your github account.

###### Github app

Creating a github app allows to control permissions more granularly. Hypha runs this codebase as [RooLLM](https://github.com/apps/roollm) Github App.

1. `GITHUB_APP_ID`: the id of the github app.
2. `GITHUB_PRIVATE_KEY_BASE64`: the private key of the github app in base64 encoded format.
3. `GITHUB_INSTALLATION_ID`: the installation id of the github app.


Additionnally, RooLLM can be configured for your specific organization by setting the following environment variables:

- `DEFAULT_GITHUB_ORG`: Your GitHub organization name
- `DEFAULT_GITHUB_REPO`: Your default GitHub repository

These are used to set the default organization and repository for the github tools. Your personal access token (or Github App) will need to have access to this organization and repository.

These default values are used when users don't provide an organization or repository in their prompt.

### Google Integration Setup

RooLLM supports integration with Google Sheets for organizational data like vacation tracking. To set this up, you will need to create a service account and share the Google Sheets with the service account email address.


1. **Create a Service Account**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Sheets API
   - Create a Service Account
   - Generate a JSON key for the Service Account

2. **Base64 Encode the Credentials**:
   ```bash
   cat your-credentials.json | base64 -w 0
   ```

3. **Add to Environment Variables**:
   - Add the base64-encoded string to your `.env` file:
   ```
   GOOGLE_CREDENTIALS=your_base64_encoded_credentials
   ```

4. **Share Google Sheets**:
   - Share any Google Sheets you want to access with the Service Account email address
   - Set appropriate permissions (usually Editor)

5. **Configure Sheet IDs**:
   - Set the following environment variables:
   ```
   VACATION_SHEET_ID=your_vacation_sheet_id
   VACATION_TAB_NAME=Vacation
   REMAINING_VACATION_TAB_NAME=Remaining
   ```

6. **Expected Sheet Formats**:
   - For the **upcoming vacations** sheet (`VACATION_SHEET_ID`) referenced in `get_upcoming_vacations.py`, these columns are expected:
     ```
     Employee Name | Start of Vacation | End of Vacation
     ------------- | ----------------- | ---------------
     John Doe      | 05/15/2023        | 05/20/2023
     Jane Smith    | 06/01/2023        | 06/10/2023
     ```
     
   - For the **remaining vacation days** sheet (referenced in `fetch_remaining_vacation_days.py`), use these columns:
     ```
     Name        | Day entitlement | Days used | Days left
     ----------- | --------------- | --------- | ---------
     John Doe    | 20              | 5         | 15
     Jane Smith  | 25              | 12        | 13
     ```
     
   Note: Dates should be in MM/DD/YYYY format.

---

### Run the project

To start the project, run:

```bash
npm run start
```

This will start the project and open a new browser window with the RooLLM client.
If your browser doesn't open automatically, you can access the web interface at http://localhost:8080/ once it is running.

### Folder and File Structure

Here's an overview of the main folders and files in the project:

- **`frontend/`**: Contains the web interface for interacting with RooLLM. This folder includes all the client-side code for the user-facing application.
  
- **`api/`**: Exposes the RooLLM API to the frontend. This folder contains server-side code that handles requests and communicates with the core logic.

- **`tools/`**: Includes all the tool calls that RooLLM can use.

- **`roollm.py`**: The core logic of the project. This file handles LLM instantiation and the main functionality of RooLLM.

- **`repl.py`**: A CLI interface for interacting with RooLLM.

### Run the project locally

To run the project entirely locally, [install ollama](https://ollama.com/download) and run the model yourself.

```bash
ollama run hermes3
```

This will start the model on your local machine.

Then, run the project with:

```bash
npm run start
```

### CLI interface

As an alternative to the web interface, you can have interactions with RooLLM in the terminal by running:

```bash
python repl.py
```

## Contributing

We welcome contributions! Here are some guidelines to help you get started:

### How to Contribute

1. **Fork the repository**: Create your own copy of the project to work on.

2. **Create a branch**: Make your changes in a new branch.
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**: Implement your feature or bug fix.

4. **Test your changes**: Ensure your changes don't break existing functionality.

5. **Submit a pull request**: Open a PR with a clear description of your changes.

### Development Guidelines

- Follow the existing code style and conventions
- Write clear, descriptive commit messages
- Document new features or changes to existing functionality
- Add tests for new features when possible

### Reporting Issues

If you encounter any bugs or have feature requests, please open an issue on the repository with:
- A clear description of the problem or suggestion
- Steps to reproduce (for bugs)
- Any relevant screenshots or error messages

### Code of Conduct

We expect all contributors to be respectful and considerate of others. Harassment or offensive behavior will not be tolerated.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) - see the [LICENSE](LICENSE) file for details.

The AGPL-3.0 is a copyleft license that requires anyone who distributes your code or a derivative work to make the source available under the same terms, and also requires the source to be provided to users who interact with the software over a network.


