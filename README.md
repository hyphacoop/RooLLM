# RooLLM

Hypha Worker Coop gives Roo, its digital pet, access to an LLM. 

Roo is our chatbot and we gave it access to an ollama API endpoint running on a GPU in our datacenter. This project can also run fully locally by installing ollama and running the model yourself.

## Installation

### Install Dependencies

To install the project dependencies, run:

```bash
pip install -r requirements.txt && npm install
```

### Set Environment Variables

To set the environment variables, run:

```bash
cp .env.example .env
```

Edit the `.env` file with the following variables:
```
ROO_LLM_MODEL=hermes3
ROO_LLM_URL=
ROO_LLM_AUTH_USERNAME=
ROO_LLM_AUTH_PASSWORD=
# Optional tools
GITHUB_TOKEN=
GITHUB_APP_ID=
GITHUB_PRIVATE_KEY_BASE64=
GITHUB_INSTALLATION_ID=
GOOGLE_CREDENTIALS=
```

#### Required credentials

1. `ROO_LLM_MODEL`: The model to use.

Hypha's API endpoint currently runs the hermes3 model. If you are running ollama locally, you can experiment with other models. See the [ollama website](https://ollama.com/download) for installation instructions and downloading a model.

2. `ROO_LLM_URL`: The URL of the ollama endpoint.

If you are running ollama locally, the default URL is `http://localhost:11434`.

#### Optional credentials

##### Hypha's API endpoint

Our endpoint is running on basic auth. To access it, you will need to set the `ROO_LLM_AUTH_USERNAME` and `ROO_LLM_AUTH_PASSWORD` environment variables.
Contact vincent to get the credentials.

##### Github

The github tools can access the github api by using a PAT (personal access token) or by using a github app.

###### PAT

1. `GITHUB_TOKEN`: a github personal access token to access the github api and have RooLLM take actions from your github account.

###### Github app

1. `GITHUB_APP_ID`: the id of the github app.
2. `GITHUB_PRIVATE_KEY_BASE64`: the private key of the github app in base64 encoded format.
3. `GITHUB_INSTALLATION_ID`: the installation id of the github app.


### Run the project

To start the project, run:

```bash
npm run start
```

This will start the project and open a new browser window with the RooLLM client.

### Run the project locally

To run the project locally, install ollama and run the model yourself.

```bash
ollama run hermes3
```

This will start the model on your local machine.

Then, run the project with:

```bash
npm run start
```

### CLI interface

As an alternative to the web interface, you can have LLM interactions in the terminal by running:

```bash
python repl.py
```
