# RooLLM

Hypha Worker Coop gives Roo, its digital pet, access to an LLM. 

Roo is our chatbot and we gave it access to an ollama API endpoint running on a GPU in our datacenter. This project can also run fully locally by installing ollama and running the model yourself.

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

Contact vincent to get the required credentials.

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

---

### Run the project

To start the project, run:

```bash
npm run start
```
### Folder and File Structure

Here’s an overview of the main folders and files in the project:

- **`frontend/`**: Contains the web interface for interacting with RooLLM. This folder includes all the client-side code for the user-facing application.
  
- **`backend/`**: Exposes the RooLLM API to the frontend. This folder contains server-side code that handles requests and communicates with the core logic.

- **`tools/`**: Includes tool calls

- **`roollm.py`**: The core logic of the project. This file handles LLM instantiation and the main functionality of RooLLM.


This will start the project and open a new browser window with the RooLLM client.
If your browser doesn't open automatically, you can access the web interface at http://localhost:8080/ once it is running.

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
````


