from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core import source_analysis, source_index
from gxp_core.source_config import SourceRepositoriesConfig, repository_metadata, resolve_repository, save_source_config
from gxp_core.source_frontend import scan_requests
from gxp_core.source_lex import LexedSource


class UrlWriteContracts(unittest.TestCase):
    def requests(self, text):
        return scan_requests(LexedSource(text), "fixture.ts")["requests"]

    def test_all_unknown_writes_invalidate_literal(self):
        for write in ["url += suffix", "url -= 1", "url *= 2", "url **= 2", "url /= 2", "url %= 2", "url <<= 1", "url >>= 1", "url >>>= 1", "url |= 1", "url &= 1", "url ^= 1", "url ||= suffix", "url &&= suffix", "url ??= suffix", "++url", "--url", "url++", "url--", "[url] = values", "({url} = values)", "({other: url} = values)", "(url) += suffix"]:
            with self.subTest(write=write):
                self.assertEqual([], self.requests("function load(suffix, values) { let url='/api/items'; " + write + "; return request.get(url); }"))

    def test_query_append_keeps_only_proven_path(self):
        requests = self.requests("function load(page) { let url='/api/items'; if(page) url += '?page=' + page; return request.get(url); }")
        self.assertEqual(1, len(requests))
        self.assertEqual('/api/items', requests[0]['route'])
        self.assertTrue(requests[0]['dynamic'])
        self.assertTrue(requests[0]['query_dynamic'])
        self.assertEqual('structural', requests[0]['path_confidence'])
        self.assertEqual('candidate', requests[0]['confidence'])

    def test_api_path_match_retains_query_and_wrapper_uncertainty(self):
        frontend = self.requests("function load(page) { let url='/api/items'; url += '?page='+page; return request.get(url); }")
        indexes = {'frontend/requests.json': frontend, 'backend/routes.json': [{'route':'/api/items','method':'GET','controller':'ItemsController','action':'Load','path':'Items.cs','line':1}]}
        status = {'index': {}, 'repositories': {'frontend': {'stale':False}, 'backend': {'stale':False}}}
        with patch.object(source_analysis,'ensure_source_index',return_value=status), patch.object(source_analysis,'load_index_file',side_effect=lambda filename,default: indexes.get(filename,default)):
            result = source_analysis.trace_api_contract.__wrapped__('/api/items')
        self.assertEqual('wrapper_unresolved',result['contract_status'])
        self.assertEqual('unresolved',result['query_status'])

    def test_query_append_disallows_conditional_replacement(self):
        for expression in ["flag ? '?page=1' : suffix", "'?page=1' && suffix", "'?page=1' + flag ? suffix : other", "'?page=1'.slice(1)"]:
            with self.subTest(expression=expression):
                self.assertEqual([], self.requests("function load(flag,suffix,other) { let url='/api/items'; url += " + expression + "; return request.get(url); }"))

    def test_shadow_binding_does_not_inherit_or_poison_outer_literal(self):
        self.assertEqual([], self.requests("function load(input) { let url='/api/items'; { let url; return request.get(url); } }"))
        requests = self.requests("function load(input) { let url='/api/items'; { let url=input; url += input; } return request.get(url); }")
        self.assertEqual(['/api/items'], [item['route'] for item in requests])

    def test_block_and_closure_writes_invalidate_outer_binding(self):
        for write in ["if(flag) { url += suffix; }", "function mutate() { url += suffix; } mutate();", "for (url of values) {}"]:
            with self.subTest(write=write):
                self.assertEqual([], self.requests("function load(flag,suffix,values) { let url='/api/items'; " + write + " return request.get(url); }"))

    def test_rest_parameters_and_expression_arrows_do_not_leak_bindings(self):
        self.assertEqual([], self.requests("const url='/api/items'; function load(...url) { return request.get(url); }"))
        requests = self.requests("const url='/api/items'; const load = url => request.get(url); request.get(url);")
        self.assertEqual(['/api/items'], [item['route'] for item in requests])
        self.assertIsNone(requests[0]['function'])

    def test_distinct_parameters_and_destructured_bindings_do_not_share_writes(self):
        self.assertEqual([], self.requests("function load(first, second) { first='/api/items'; return request.get(second); }"))
        self.assertEqual([], self.requests("function load(input) { let [first, second]=input; first='/api/items'; return request.get(second); }"))

    def test_unrelated_property_and_later_function_writes_are_isolated(self):
        requests = self.requests("function first(obj) { let url='/api/items'; obj.url += 'x'; return request.get(url); } function next() { let url='other'; url++; }")
        self.assertEqual(['/api/items'], [item['route'] for item in requests])


class ResponseBudgetContracts(unittest.TestCase):
    def check_budget(self, payload):
        original = copy.deepcopy(payload)
        result = source_index.bounded_result(payload)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8')), 65536)
        self.assertEqual(original, payload)
        self.assertTrue(result['response_truncated'])
        self.assertFalse(result['response_complete'])
        self.assertNotEqual('ok', result['status'])
        return result

    def test_single_large_unlisted_field_is_bounded(self):
        self.check_budget({'status':'ok','frontend_callers':[{'payload':'x' * 70000}]})

    def test_unicode_and_nested_payload_preserve_uncertainty(self):
        result = self.check_budget({'status':'ok','contract_status':'closed','unresolved':['pending target'], 'evidence':[{'name':'中文'*10000,'children':[{'payload':'字段'*5000}]} for index in range(12)]})
        self.assertEqual('unresolved', result['contract_status'])
        self.assertIn('pending target', result['unresolved'])

    def test_ten_large_items_and_many_dynamic_keys_are_bounded(self):
        self.check_budget({'status':'ok','evidence':[{'value':'x'*10000} for index in range(10)]})
        self.check_budget({'status':'ok','repositories':{str(index):'字段'*1000 for index in range(200)}})

    def test_unavailable_layer_errors_are_also_bounded(self):
        status = {'index': {}, 'repositories': {}, 'errors': [{'code': 'MISSING', 'message': '失败'*40000}]}
        with patch.object(source_analysis, 'ensure_source_index', return_value=status):
            result = source_analysis.inspect_component_source('TestPaper')
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8')), 65536)
        self.assertEqual('unresolved', result['status'])
        self.assertTrue(result['response_truncated'])

    def test_small_payload_is_unchanged(self):
        result = {'status':'ok','evidence':[{'confidence':'exact'}]}
        self.assertEqual(result, source_index.bounded_result(result))

    def test_deep_payload_is_bounded_without_recursive_failure(self):
        payload = {'status':'ok'}
        cursor = payload
        for index in range(80):
            cursor['nested'] = {'value':'汉'*1000}
            cursor = cursor['nested']
        self.check_budget(payload)


class SymbolEntryContracts(unittest.TestCase):
    def query(self, text):
        symbols = [{'kind':'method','name':'Worker.Run','symbol_id':namespace+'.Worker.Run('+parameter+')','namespace':namespace,'type_id':namespace+'.Worker','member':'Run','parameters':[{'name':'value','type':parameter}],'path':namespace+'.cs','line':1} for namespace,parameter in [('App','string'),('App','int'),('Other','string')]]
        status = {'index':{'exists':True},'repositories':{'backend':{'stale':False}}}
        edges = [{'caller_id':symbol['symbol_id'],'caller':'Worker.Run','callee_member':'Continue','category':'unresolved','target_ids':[],'path':symbol['path'],'line':2} for symbol in symbols]
        with patch.object(source_analysis,'ensure_source_index',return_value=status), patch.object(source_analysis,'load_index_file',side_effect=lambda filename,default: symbols if filename=='backend/symbols.json' else edges if filename=='graph/backend-call-edges.json' else []):
            return source_analysis.trace_backend_call_chain.__wrapped__(text)

    def test_full_symbol_selects_one_namespace_and_overload(self):
        result = self.query('App.Worker.Run(string)')
        self.assertEqual('ok',result['status'])
        self.assertEqual(['App.Worker.Run(string)'],[item['symbol_id'] for item in result['starts']])

    def test_stack_parameter_names_and_system_aliases_are_normalized(self):
        result = self.query('at App.Worker.Run(System.String value) in C:/fixture.cs:line 5')
        self.assertEqual('ok',result['status'])
        self.assertEqual(['App.Worker.Run(string)'],[item['symbol_id'] for item in result['starts']])

    def test_missing_full_identity_does_not_fall_back_to_wrong_namespace(self):
        self.assertEqual('not_found',self.query('Missing.Worker.Run(string)')['status'])
        self.assertEqual('not_found',self.query('App.Worker.Run(bool)')['status'])

    def test_short_ambiguous_name_does_not_expand_all_candidates(self):
        result = self.query('Worker.Run')
        self.assertEqual('ambiguous',result['status'])
        self.assertEqual(3,len(result['starts']))
        self.assertEqual([],result['call_tree'])


class DirtyScopeContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / 'checkout'
        self.source = self.checkout / 'src/core/common/service.ts'
        self.source.parent.mkdir(parents=True)
        self.source.write_text("export function load(){return request.get('/api/one')}",encoding='utf-8')
        for arguments in [('init','-q'),('add','.'),('-c','user.email=test@example.invalid','-c','user.name=Test','commit','-q','-m','fixture')]:
            subprocess.run(['git',*arguments],cwd=self.checkout,stdin=subprocess.DEVNULL,capture_output=True,check=True)
        self.enterContext(patch.dict('os.environ',{'GXP_LOWCODE_SOURCE_CONFIG':str(self.root/'config.json'),'GXP_LOWCODE_SOURCE_INDEX':str(self.root/'index')}))
        self.enterContext(patch('gxp_core.source_config.DEFAULT_REPOSITORIES',{'frontend':(),'backend':()}))
        save_source_config(SourceRepositoriesConfig(frontend=(str(self.checkout),)))

    def selected(self):
        return resolve_repository('frontend')['selected']

    def test_document_and_unrelated_artifact_do_not_rebuild_or_hash(self):
        source_index.refresh_source_index(layers=('frontend',))
        before = self.selected()['fingerprint']
        (self.checkout/'notes.md').write_text('documentation',encoding='utf-8')
        artifact = self.checkout/'artifact.bin'
        artifact.write_bytes(b'x'*1024)
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            if path == artifact:
                raise AssertionError('unrelated artifact was read')
            return original_open(path,*args,**kwargs)
        with patch.object(Path,'open',guarded_open),patch.object(source_index,'_scan_frontend',wraps=source_index._scan_frontend) as scanner:
            self.assertEqual(before,self.selected()['fingerprint'])
            source_index.ensure_source_index(('frontend',))
            scanner.assert_not_called()
        self.assertEqual(2,self.selected()['dirty_file_count'])

    def test_same_length_edits_keep_content_freshness(self):
        self.source.write_text('const value = 1;',encoding='utf-8')
        before = self.selected()['fingerprint']
        original = self.source.stat()
        self.source.write_text('const value = 2;',encoding='utf-8')
        os.utime(self.source,ns=(original.st_atime_ns,original.st_mtime_ns))
        self.assertNotEqual(before,self.selected()['fingerprint'])

    def test_rename_outside_scope_and_delete_remain_changes(self):
        before = self.selected()['fingerprint']
        subprocess.run(['git','mv',str(self.source),'moved.txt'],cwd=self.checkout,check=True,capture_output=True)
        self.assertNotEqual(before,self.selected()['fingerprint'])
        (self.checkout/'moved.txt').unlink()
        self.assertNotEqual(before,self.selected()['fingerprint'])

    def test_live_filter_search_and_fingerprint_share_exclusions(self):
        ignored = self.source.parent / 'node_modules/TestPaper/file.ts'
        ignored.parent.mkdir(parents=True)
        ignored.write_text('conditionFilter', encoding='utf-8')
        self.assertEqual([], source_analysis._term_evidence(self.checkout, ('conditionFilter',), 'TestPaper'))
        from gxp_core.source_scope import is_source_dependency
        self.assertTrue(is_source_dependency('src/core/common/service.ts', 'frontend'))
        self.assertTrue(is_source_dependency('src' + chr(92) + 'core' + chr(92) + 'common' + chr(92) + 'service.ts', 'frontend'))

    def test_configuration_dependency_invalidates_source(self):
        before = self.selected()['fingerprint']
        (self.checkout/'tsconfig.json').write_text('{}',encoding='utf-8')
        self.assertNotEqual(before,self.selected()['fingerprint'])

    def test_unrelated_mirror_dirt_does_not_create_ambiguity(self):
        mirror = self.root/'mirror'
        subprocess.run(['git','clone','-q',str(self.checkout),str(mirror)],capture_output=True,check=True)
        for checkout in (self.checkout,mirror):
            subprocess.run(['git','remote','remove','origin'],cwd=checkout,capture_output=True)
            subprocess.run(['git','remote','add','origin','https://example.invalid/shared.git'],cwd=checkout,capture_output=True,check=True)
        (mirror/'notes.md').write_text('mirror notes',encoding='utf-8')
        config = SourceRepositoriesConfig(frontend=(str(self.checkout),str(mirror)))
        result = resolve_repository('frontend',config=config)
        self.assertEqual(str(self.checkout),result['selected']['path'])


if __name__ == '__main__':
    unittest.main()
