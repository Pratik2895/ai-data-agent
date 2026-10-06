import sys
from pathlib import Path
from types import SimpleNamespace as N
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'agents'))
from runtime import validate_sql, data_path, transform_dataset, extract_api, execute_statement

@pytest.mark.parametrize('sql', ['DELETE FROM ai_agent_demo.customer_support.products', 'SELECT 1; DROP TABLE x', 'SELECT * FROM other.schema.products', 'SELECT * FROM products', "SELECT evil()", 'SELECT * INTO foo FROM ai_agent_demo.customer_support.products'])
def test_unsafe_sql(sql):
    with pytest.raises(Exception): validate_sql(sql)

def test_cte():
    validate_sql('WITH p AS (SELECT * FROM ai_agent_demo.customer_support.products) SELECT * FROM p')

def test_transform(tmp_path, monkeypatch):
    monkeypatch.setenv('ETL_DATA_ROOT', str(tmp_path))
    data_path('input.csv').write_text('a,b\n1,x\n1,x\n2,\n')
    transform_dataset('input.csv', 'output.csv', ['a','b'], True, True)
    assert data_path('output.csv').read_text().splitlines() == ['a,b','1,x']
    with pytest.raises(ValueError): data_path('../outside.csv')

@pytest.mark.parametrize('url',['http://jsonplaceholder.typicode.com/posts','https://localhost/test','https://jsonplaceholder.typicode.com.evil.org/posts','https://user:pass@jsonplaceholder.typicode.com/posts'])
def test_api_boundary(url):
    with pytest.raises(ValueError): extract_api(url)

def test_sql_failure(monkeypatch):
    from databricks.sdk.service.sql import StatementState
    monkeypatch.setenv('DATABRICKS_WAREHOUSE_ID', 'test')
    client=N(statement_execution=N(execute_statement=lambda **kw: N(status=N(state=StatementState.FAILED,error='broken'))))
    with pytest.raises(RuntimeError, match='SQL failed'): execute_statement(client, 'SELECT 1')

def test_responses_wrapper(monkeypatch):
    import agent
    from mlflow.types.responses import ResponsesAgentRequest
    model=agent.DataAgent()
    model.graph=N(invoke=lambda state: {'final_answer':'42'})
    result=model.predict(ResponsesAgentRequest(input=[{'role':'user','content':'Count tickets'}]))
    assert result.output[0].content[0]["text"] == '42'

def test_sql_graph(monkeypatch):
    import agent
    monkeypatch.setattr(agent, 'pick_llm', lambda level: N(invoke=lambda prompt: N(content='Summary'),with_structured_output=lambda schema: N(invoke=lambda prompt: agent.JudgeSchema(answer='yes'))))
    monkeypatch.setattr(agent,'_execute_sql_sdk', lambda sql: '{"rows": [[42]]}')
    monkeypatch.setattr(agent,'_generate_sql',lambda state: state.model_copy(update={'generated_sql':'SELECT COUNT(*) FROM ai_agent_demo.customer_support.products'}))
    result=agent._build_sql_analyst_graph().invoke({'user_question':'Count products'})
    assert result['final_answer'] == 'Summary'

def test_app_responses_contract(monkeypatch):
    import importlib.util
    import databricks.sdk.core
    monkeypatch.setattr(databricks.sdk.core,'Config',lambda: N(host='https://example.test'))
    spec=importlib.util.spec_from_file_location('chat_app',Path(__file__).resolve().parents[1]/'src/app/app.py')
    app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
    calls=[]
    def do(method,path,body):
        calls.append((method,path,body))
        return {'output':[{'content':[{'type':'output_text','text':'42'}]}]}
    monkeypatch.setattr(app,'_workspace_client',lambda token: N(api_client=N(do=do)))
    assert app.respond('Count tickets',[{'role':'assistant','content':'Hello'}],None)=='42'
    assert calls[0][2]['input'][-1]=={'role':'user','content':'Count tickets'}

def test_content_blocks():
    import agent
    from langchain_core.messages import AIMessage
    msg=AIMessage(content=[{'type':'reasoning','summary':[]},{'type':'text','text':'SELECT 1'}])
    assert agent.message_text(msg)=='SELECT 1'


def test_verification_uses_traffic_routed_model():
    from scripts.verify_deployment import active_model_version
    entities=[N(name='old', entity_version='2'), N(name='new', entity_version='3')]
    routes=[N(served_entity_name='new', served_model_name='new', traffic_percentage=100),
            N(served_entity_name='old', served_model_name='old', traffic_percentage=0)]
    endpoint=N(config=N(served_entities=entities,traffic_config=N(routes=routes)))
    assert active_model_version(endpoint)=='3'
    routes[0].traffic_percentage=50
    routes[1].traffic_percentage=50
    with pytest.raises(RuntimeError,match='100 percent'): active_model_version(endpoint)
