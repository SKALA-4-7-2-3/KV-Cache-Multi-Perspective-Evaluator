import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict


class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    count: int


class FakeProcess:
    def __init__(self, args, captured, *, final='{"count": 2}', events=None,
                 returncode=0, failure=None, usage=True):
        self.pid = 987654
        self.returncode = returncode
        self.args, self.captured, self.failure = args, captured, failure
        self.waited = False
        Path(args[args.index('-o') + 1]).write_text(final)
        if '--output-schema' in args:
            captured['schema_json'] = Path(args[args.index('--output-schema') + 1]).read_text()
            captured['schema'] = json.loads(captured['schema_json'])
        self.events = events if events is not None else [
            {'type': 'thread.started', 'thread_id': 'thread-test'},
            {'type': 'turn.started'},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': final}},
            {'type': 'turn.completed', **({'usage': {'input_tokens': 10,
                'cached_input_tokens': 3, 'output_tokens': 5}} if usage else {})},
        ]

    def communicate(self, input=None, timeout=None):
        self.captured.update(prompt=input, timeout=timeout)
        if self.failure:
            raise self.failure
        return '\n'.join(json.dumps(e) for e in self.events), ''

    def wait(self, timeout=None):
        self.waited = True
        return self.returncode


class CodexProviderTests(unittest.TestCase):
    def setUp(self):
        from pipeline import codex_provider
        self.provider = codex_provider
        self.captured = {}
        self.processes = []
        self.fixture = {}
        self.version = patch.object(codex_provider, '_cli_version', return_value='0.153.2')
        self.version.start()
        self.popen = patch.object(codex_provider.subprocess, 'Popen', side_effect=self.spawn)
        self.popen.start()
        self.addCleanup(self.version.stop)
        self.addCleanup(self.popen.stop)

    def spawn(self, args, **kwargs):
        self.captured.update(args=args, **kwargs)
        process = FakeProcess(args, self.captured, **self.fixture)
        self.processes.append(process)
        return process

    def client(self, **kwargs):
        return self.provider.CodexClient(timeout=5, max_retries=0, **kwargs)

    def test_pydantic_parse_and_usage_match_existing_responses_contract(self):
        with self.client() as client:
            response = client.responses.parse(model='gpt-test', instructions='Count only.',
                input='private source', text_format=Answer, temperature=0, store=False,
                max_output_tokens=100)
        self.assertEqual(response.output_parsed, Answer(count=2))
        self.assertEqual(response.status, 'completed')
        self.assertEqual(response.usage.total_tokens, 15)
        self.assertEqual(response.usage.model_dump()['output_tokens'], 5)
        self.assertIsNone(response.incomplete_details)
        self.assertNotIn('private source', ' '.join(self.captured['args']))
        self.assertIn('private source', self.captured['prompt'])

    def test_cli_is_fresh_ephemeral_read_only_and_blocks_tools(self):
        self.client().responses.create(model='gpt-test', input='x')
        args = self.captured['args']
        for flag in ['--ignore-user-config', '--ephemeral', '--sandbox', '--json']:
            self.assertIn(flag, args)
        self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
        self.assertTrue(self.captured['start_new_session'])
        self.assertEqual(self.captured['umask'], 0o077)
        self.assertIn('forced_login_method="chatgpt"', args)
        for feature in ['apps', 'plugins', 'shell_tool', 'unified_exec', 'browser_use',
                        'computer_use', 'multi_agent', 'view_image', 'hooks']:
            self.assertTrue(any(args[i] == '--disable' and args[i + 1] == feature
                                for i in range(len(args) - 1)))
        self.assertFalse(Path(self.captured['cwd']).exists())

    def test_child_environment_scrubs_credentials_and_preserves_auth_home(self):
        values = {'OPENAI_API_KEY': 'test-key', 'TAVILY_API_KEY': 'test-search',
            'HF_TOKEN': 'test-token', 'DB_PASSWORD': 'test-password',
            'OPENAI_BASE_URL': 'test-url', 'CUSTOM_API_BASE': 'test-base',
            'CODEX_HOME': '/existing/auth-home', 'PATH': '/usr/bin'}
        with patch.dict('os.environ', values, clear=True):
            self.client().responses.create(model='gpt-test', input='x')
        self.assertEqual(self.captured['env']['CODEX_HOME'], '/existing/auth-home')
        for name in values.keys() - {'CODEX_HOME', 'PATH'}:
            self.assertNotIn(name, self.captured['env'])

    def test_tool_item_cannot_be_treated_as_a_successful_answer(self):
        self.fixture['events'] = [{'type': 'thread.started', 'thread_id': 'thread-test'},
            {'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'private'}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}]
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input='x')

    def test_missing_usage_cannot_be_synthetic_zero(self):
        self.fixture['usage'] = False
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input='x')

    def test_exit_failure_or_incomplete_event_fails_closed(self):
        self.fixture['returncode'] = 1
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input='x')
        self.fixture = {'events': [{'type': 'turn.failed', 'error': {'message': 'private'}}]}
        with self.assertRaises(self.provider.CodexProviderError) as error:
            self.client().responses.create(model='gpt-test', input='x')
        self.assertNotIn('private', str(error.exception))

    def test_timeout_kills_the_process_group_and_waits(self):
        self.fixture['failure'] = subprocess.TimeoutExpired('codex', 5)
        with patch.object(self.provider.os, 'killpg') as killed:
            with self.assertRaises(TimeoutError):
                self.client().responses.create(model='gpt-test', input='x')
        killed.assert_called_once()
        self.assertTrue(self.processes[0].waited)

    def test_cancellation_kills_the_process_group_and_waits(self):
        self.fixture['failure'] = KeyboardInterrupt()
        with patch.object(self.provider.os, 'killpg') as killed:
            with self.assertRaises(KeyboardInterrupt):
                self.client().responses.create(model='gpt-test', input='x')
        killed.assert_called_once()
        self.assertTrue(self.processes[0].waited)

    def test_schema_failure_records_real_usage_and_no_response_content(self):
        from pipeline import governance
        self.fixture['final'] = '{"count": "coercion-not-allowed"}'
        with tempfile.TemporaryDirectory() as d:
            ledger = governance.BudgetLedger(Path(d), limits={'tokens': 1000000})
            with patch.object(governance, '_ledger', ledger):
                with self.assertRaises(self.provider.CodexProviderError):
                    self.client().responses.parse(model='gpt-test', input='private prompt',
                        text_format=Answer)
            data = ledger.snapshot()
            self.assertEqual(data['used_tokens'], 15)
            self.assertEqual(data['unconfirmed_tokens'], 0)
            record = (Path(d) / 'codex.calls.jsonl').read_text()
            self.assertNotIn('private prompt', record)
            self.assertNotIn('coercion-not-allowed', record)
            self.assertEqual(json.loads(record)['provider'], 'codex_cli_chatgpt')

    def test_unknown_usage_retains_the_reservation_and_budget_timeout(self):
        from pipeline import governance
        self.fixture['usage'] = False
        with tempfile.TemporaryDirectory() as d:
            ledger = governance.BudgetLedger(Path(d), limits={'tokens': 1000000, 'seconds': 2})
            with patch.object(governance, '_ledger', ledger):
                with self.assertRaises(self.provider.CodexProviderError):
                    self.client().responses.create(model='gpt-test', input='x')
            self.assertGreater(ledger.snapshot()['unconfirmed_tokens'], 65536)
            self.assertLessEqual(self.captured['timeout'], 2)

    def test_dict_schema_is_validated_and_remote_refs_never_resolved(self):
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['count'],
                  'properties': {'count': {'type': 'integer', 'minimum': 3}}}
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input='x',
                text={'format': {'type': 'json_schema', 'name': 'result', 'strict': True, 'schema': schema}})
        count = len(self.processes)
        schema = {'$ref': 'https://example.invalid/private-schema'}
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input='x',
                text={'format': {'type': 'json_schema', 'schema': schema}})
        self.assertEqual(len(self.processes), count)

    def test_include_raw_chat_returns_validated_pydantic_and_usage(self):
        chat = self.provider.CodexChatModel(model='gpt-test', temperature=0, timeout=5,
            max_retries=0).with_structured_output(Answer, method='json_schema', strict=True,
                                               include_raw=True)
        response = chat.invoke([('system', 'Count.'), ('human', 'private input')])
        self.assertEqual(response['parsed'], Answer(count=2))
        self.assertIsNone(response['parsing_error'])
        self.assertEqual(response['raw'].usage_metadata['total_tokens'], 15)

    def test_raw_text_chat_and_codex_default_omit_explicit_model(self):
        self.fixture['final'] = 'plain answer'
        result = self.provider.CodexChatModel(model='codex-default', timeout=5).invoke('question')
        self.assertEqual(result.content, 'plain answer')
        self.assertNotIn('-m', self.captured['args'])

    def test_unknown_stream_tools_and_image_kwargs_never_spawn(self):
        for kwargs in ({'stream': True}, {'tools': [{'type': 'function'}]}, {'imaginary_option': True}):
            with self.assertRaises(self.provider.CodexProviderError):
                self.client().responses.create(model='gpt-test', input='x', **kwargs)
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input=[{'role': 'user',
                'content': [{'type': 'input_image', 'image_url': 'private'}]}])
        self.assertEqual(len(self.processes), 0)

    def test_output_limit_is_postchecked_not_faked_as_cli_wire_cap(self):
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(model='gpt-test', input='x', max_output_tokens=4)

    def test_exact_startup_warning_is_allowed_only_before_turn_started(self):
        warning = {'type': 'item.completed', 'item': {'type': 'error',
                   'message': self.provider._STARTUP_WARNING}}
        standard = [{'type': 'thread.started', 'thread_id': 'thread-test'},
            {'type': 'turn.started'}, {'type': 'item.completed',
            'item': {'type': 'agent_message', 'text': '{"count": 2}'}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}]
        self.fixture['events'] = [standard[0], warning, *standard[1:]]
        self.client().responses.create(input='x')
        self.fixture['events'] = [*standard[:2], warning, *standard[2:]]
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(input='x')
        warning['item']['message'] += ' unexpected'
        self.fixture['events'] = [standard[0], warning, *standard[1:]]
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(input='x')

    def test_sdk_strict_schema_is_sent_even_for_permissive_pydantic_models(self):
        class Permissive(BaseModel):
            count: int = 1
        self.client().responses.parse(input='x', text_format=Permissive)
        self.assertFalse(self.captured['schema']['additionalProperties'])
        self.assertEqual(self.captured['schema']['required'], ['count'])
        self.fixture['final'] = '{"count": 2, "extra": "discarding would hide a contract failure"}'
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.parse(input='x', text_format=Permissive)

    def test_local_refs_are_supported_and_file_refs_are_rejected(self):
        schema = {'$defs': {'count': {'type': 'integer', 'enum': [2]}}, 'type': 'object',
                  'properties': {'count': {'$ref': '#/$defs/count'}}, 'required': ['count'],
                  'additionalProperties': False}
        response = self.client().responses.create(input='x', text={'format':
            {'type': 'json_schema', 'schema': schema}})
        self.assertEqual(response.output_parsed, {'count': 2})
        count = len(self.processes)
        schema['properties']['count']['$ref'] = 'file:///private/schema.json'
        with self.assertRaises(self.provider.CodexProviderError):
            self.client().responses.create(input='x', text={'format':
                {'type': 'json_schema', 'schema': schema}})
        self.assertEqual(len(self.processes), count)

    def test_tool_failure_still_settles_known_usage(self):
        from pipeline import governance
        self.fixture['events'] = [{'type': 'turn.started'}, {'type': 'item.completed',
            'item': {'type': 'web_search', 'query': 'not recorded'}}, {'type': 'turn.completed',
            'usage': {'input_tokens': 10, 'output_tokens': 5}}]
        with tempfile.TemporaryDirectory() as d:
            ledger = governance.BudgetLedger(Path(d), limits={'tokens': 1000000})
            with patch.object(governance, '_ledger', ledger):
                with self.assertRaises(self.provider.CodexProviderError):
                    self.client().responses.create(input='x')
            self.assertEqual(ledger.snapshot()['used_tokens'], 15)
            record = json.loads((Path(d) / 'codex.calls.jsonl').read_text())
            self.assertEqual(record['error_category'], 'tool_or_error_event')
            self.assertNotIn('not recorded', json.dumps(record))

    def test_duplicate_fields_and_nonfinite_json_cannot_pass_schema(self):
        for output in ('{"count": 1, "count": 2}', '{"count": NaN}'):
            self.fixture['final'] = output
            with self.assertRaises(self.provider.CodexProviderError):
                self.client().responses.parse(input='x', text_format=Answer)

    def test_budget_refusal_cannot_start_a_model_process(self):
        from pipeline import governance
        with tempfile.TemporaryDirectory() as d:
            ledger = governance.BudgetLedger(Path(d), limits={'tokens': 1})
            with patch.object(governance, '_ledger', ledger):
                with self.assertRaises(governance.BudgetExceeded):
                    self.client().responses.create(input='x')
        self.assertEqual(len(self.processes), 0)

    def test_chat_root_client_close_applies_to_structured_runnables(self):
        chat = self.provider.CodexChatModel(timeout=5)
        runnable = chat.with_structured_output(Answer)
        self.assertIs(runnable.root_client, chat.root_client)
        chat.root_client.close()
        with self.assertRaises(self.provider.CodexProviderError):
            runnable.invoke('x')
        self.assertEqual(len(self.processes), 0)

    def test_reservation_includes_the_exact_utf8_schema_sent_to_cli(self):
        from pipeline import governance
        schema = {'type': 'object', 'description': '한글 스키마', 'properties':
            {'count': {'type': 'integer'}}, 'additionalProperties': False, 'required': ['count']}
        with tempfile.TemporaryDirectory() as d:
            ledger = governance.BudgetLedger(Path(d), limits={'tokens': 1000000})
            with patch.object(governance, '_ledger', ledger):
                response = self.client().responses.create(input='x', max_output_tokens=100,
                    text={'format': {'type': 'json_schema', 'schema': schema}})
            call = next(iter(ledger.snapshot()['calls'].values()))
            expected = len(self.captured['prompt'].encode('utf-8')) + 65536 + 100 + len(
                self.captured['schema_json'].encode('utf-8'))
            self.assertEqual(call['reserved_tokens'], expected)
            self.assertEqual(response.provider_metadata['authentication'], 'chatgpt')


if __name__ == '__main__':
    unittest.main()
