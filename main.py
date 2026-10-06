"""Run the same Databricks agent locally using the selected CLI profile."""
import argparse
import configparser
import json
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    parser.add_argument('--profile', default=os.getenv('DATABRICKS_CONFIG_PROFILE', 'dev-52d59088'))
    args = parser.parse_args()
    # Capture CLI OAuth credentials only in memory; never print or persist tokens.
    profiles = configparser.ConfigParser()
    profiles.read(Path(os.getenv('DATABRICKS_CONFIG_FILE', str(Path.home() / '.databrickscfg'))))
    host = profiles.get(args.profile, 'host')
    credentials = json.loads(subprocess.check_output(['databricks', 'auth', 'token', args.profile], text=True))
    os.environ.update(DATABRICKS_HOST=host, DATABRICKS_TOKEN=credentials['access_token'], DATABRICKS_AUTH_TYPE='pat')
    os.environ.pop('DATABRICKS_CONFIG_PROFILE', None)
    from src.agents.agent import DataAgent
    from mlflow.types.responses import ResponsesAgentRequest
    response = DataAgent().predict(ResponsesAgentRequest(input=[{'role': 'user', 'content': args.question}]))
    for item in response.output:
        for part in item.content:
            if part.get('type') == 'output_text':
                print(part['text'])


if __name__ == '__main__':
    main()
