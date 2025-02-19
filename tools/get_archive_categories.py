# Tool configuration
name = "get_archive_categories"
emoji = "🗄️"
description = (
   "Retrieve a list of archivable categories with their corresponding links."
   "Use this tool when a user asks for available category and their respective emojis."
   "Example query: 'What are the archive's memory categories?'"
)
parameters = {
    "type": "object",
    "properties": {},
    "required": []
}

# Archivable topics
TOPICS = {
    "💼": "[New Business Development](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=836481993)",
    "🕸️": "[DWeb](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=842831239)",
    "🥉": "[Web3](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=1058288410)",
    "🤝": "[Coops](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=1820372858)",
    "📚": "[Curriculum](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=2050744633)",
    "🌳": "[Dripline](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=729956168)",
    "🗞️": "[Press Coverage](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=0&fvid=2092259272)",
    "🧮": "[AI](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit#gid=380697275)",
    "💌": "[Newsletter](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit?gid=461055596)",
    "📜": "[Poetry](https://docs.google.com/spreadsheets/d/1FyL430qtch_ulnqUiknpfaSwMfHADAY3cYeZIGyHBtY/edit?gid=238120550#gid=238120550)"
}

async def tool(roo, arguments, user):
    """
    Retrieve a list of archivable categories with their corresponding links.
    """
    try:
        archive_message = "Here are all the archivable categories:\n"
        for emoji, description in TOPICS.items():
            archive_message += f"\n {emoji}: {description}\n"

        return archive_message
    except Exception as e:
        return {"error": f"Failed to retrieve archive categories: {str(e)}"}
