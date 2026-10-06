"""Verify the deployed agent and app through authenticated APIs, without UI automation."""
import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from gradio_client import Client


def active_model_version(endpoint):
    routes = [route for route in endpoint.config.traffic_config.routes if route.traffic_percentage > 0]
    if len(routes) != 1 or routes[0].traffic_percentage != 100:
        raise RuntimeError('Expected 100 percent of traffic on one model version')
    name = routes[0].served_entity_name or routes[0].served_model_name
    return next(entity.entity_version for entity in endpoint.config.served_entities if entity.name == name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--warehouse-id', required=True)
    parser.add_argument('--endpoint', default='ai_data_agent_endpoint')
    parser.add_argument('--app', default='ai-data-agent-app')
    parser.add_argument('--output', default='deployment-verification.json')
    args = parser.parse_args()
    # Keep OAuth credentials only in memory; report files never contain credentials.
    credentials = json.loads(subprocess.check_output(
        ['databricks', 'auth', 'token', args.profile], text=True))
    workspace = WorkspaceClient(host=args.host, token=credentials['access_token'], auth_type='pat')
    endpoint = workspace.serving_endpoints.get(args.endpoint)
    app = workspace.apps.get(args.app)
    if endpoint.state.ready.value != 'READY' or endpoint.state.config_update.value != 'NOT_UPDATING':
        raise RuntimeError('Serving endpoint has not finished provisioning')
    if app.app_status.state.value != 'RUNNING':
        raise RuntimeError('App is not running')
    count = workspace.statement_execution.execute_statement(
        warehouse_id=args.warehouse_id,
        statement='SELECT COUNT(*) FROM ai_agent_demo.customer_support.cust_service_data',
        wait_timeout='30s')
    deadline = time.monotonic() + 120
    while count.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() > deadline:
            workspace.statement_execution.cancel_execution(count.statement_id)
            raise TimeoutError('Ground-truth query timed out')
        time.sleep(1)
        count = workspace.statement_execution.get_statement(count.statement_id)
    if count.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f'Ground-truth query failed: {count.status.error}')
    expected_count = int(count.result.data_array[0][0])
    results = {}

    def ask(name, question):
        response = workspace.api_client.do(
            'POST', f'/serving-endpoints/{args.endpoint}/invocations',
            body={'input': [{'role': 'user', 'content': question}]})
        text = '\n'.join(part.get('text', '') for item in response.get('output', [])
                         for part in item.get('content', []) if part.get('type') == 'output_text')
        if not text:
            raise AssertionError(f'{name} returned no text')
        results[name] = text
        print(f'{name}: {json.dumps(text, ensure_ascii=True)}', flush=True)
        return text

    sql = ask('sql', 'How many customer service tickets are in the database?')
    if str(expected_count) not in re.sub(r'[,\s]', '', sql):
        raise AssertionError('SQL answer does not match the warehouse count')
    docs = ask('knowledge', 'What features does the documentation describe for AccountEase Pro? Cite the PDF filename.')
    if 'accountease' not in docs.lower() or '.pdf' not in docs.lower():
        raise AssertionError('Knowledge answer did not cite the expected PDF source')
    suffix = str(int(time.time()))
    etl = ask('etl', f'Extract https://jsonplaceholder.typicode.com/posts into posts_{suffix}.csv, '
              f'select only id and title and save transformed_{suffix}.csv, then inspect the saved output. '
              'Report the actual row count and column names.')
    if 'ipython' in etl.lower() or 'inspect_dataset(' in etl.lower():
        raise AssertionError('ETL answer exposes an internal tool transcript')
    if not all(value in etl.lower() for value in ('100', 'id', 'title')):
        raise AssertionError('ETL did not report the expected transformed dataset')
    chat = Client(app.url, headers={'Authorization': 'Bearer ' + credentials['access_token']}, verbose=False)
    text = chat.predict('How many customer service tickets are in the database?', api_name='/respond')
    results['app'] = text
    print(f'app: {json.dumps(text, ensure_ascii=True)}', flush=True)
    if str(expected_count) not in re.sub(r'[,\s]', '', text):
        raise AssertionError('App answer does not match the warehouse count')
    report = {'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'endpoint': args.endpoint, 'model_version': active_model_version(endpoint),
              'app_url': app.url, 'expected_ticket_count': expected_count, 'checks': results}
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
    print('All deployment checks passed', flush=True)


if __name__ == '__main__':
    main()
