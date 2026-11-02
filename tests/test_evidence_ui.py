"""Exercise the UI renderer with actual retrieval output using Node's VM."""
import json
from pathlib import Path
import subprocess
import unittest

from app import PRODUCTS, agent, graph


class EvidenceUITests(unittest.TestCase):
    def test_unsupported_searches_have_no_products_or_evidence(self):
        queries = ['umbrella', 'dress', 'sandals', 'umbrellas for hiking in rain',
                   'find me a dress under $100', 'hiking sandals', 'telescope']
        for query in queries:
            with self.subTest(query=query):
                result = agent(query)
                self.assertEqual(result['products'], [])
                self.assertIn('No catalog match', result['answer'])
                self.assertIn('0 matching products', result['trace'][1]['detail'])
        script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({catalog:input.catalog});
vm.runInContext(fs.readFileSync('static/local-agent.js','utf8'),context);
for(const query of input.queries){
  context.query=query;
  const result=vm.runInContext('localAgent(query)',context);
  assert.equal(result.products.length,0,query);
  assert.ok(result.answer.includes('No catalog match'),query);
}
assert.equal(vm.runInContext("localAgent('waterproof hiking boots under $200').products[0].id",context),'p2');
assert.ok(vm.runInContext("localAgent('hiking in rain under $150').products.length",context)>0);
"""
        subprocess.run(['node', '-e', script], text=True, check=True,
                       input=json.dumps({'queries': queries,
                                         'catalog': {'products': PRODUCTS, 'graph': graph()}}),
                       cwd=Path(__file__).resolve().parents[1])

    def test_retrieved_edges_and_empty_state(self):
        products = agent('waterproof hiking boots under $200')['products']
        script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const elements=new Map();
function element(){return {children:[],textContent:'',replaceChildren(...items){this.children=items;}};}
const document={
  querySelector(selector){if(!elements.has(selector))elements.set(selector,element());return elements.get(selector);},
  querySelectorAll(){return [];}, createElement:element
};
const context=vm.createContext({document,fetch:()=>new Promise(()=>{}),input});
vm.runInContext(fs.readFileSync('static/app.js','utf8')+'\ncatalog={graph:input.graph};renderEvidence(input.products);',context);
const texts=()=>elements.get('#graph-evidence').children.map(n=>n.textContent);
const labels=new Map(input.graph.nodes.map(n=>[n.id,n.label]));
const edges=input.products.flatMap(p=>p.evidence);
assert.ok(edges.length>0);
assert.deepEqual(texts(),edges.map(e=>`${labels.get(e.source)} — ${e.relation} → ${labels.get(e.target)}`));
assert.ok(texts().some(t=>t==='Stormcrest Hiking Boots — SUITS_WEATHER → rain'));
assert.ok(!texts().some(t=>t.includes('HAS_FEATURE'))); // Full catalog neighbors are not answer evidence.
vm.runInContext('renderEvidence([...input.products,...input.products]);',context);
assert.equal(texts().length,edges.length);
vm.runInContext('renderEvidence(input.emptyProducts);',context);
assert.deepEqual(texts(),['No supporting graph evidence found.']);
vm.runInContext('renderEvidence([{id:"p2"}]);',context);
assert.deepEqual(texts(),['No supporting graph evidence found.']);
"""
        subprocess.run(
            ['node', '-e', script],
            input=json.dumps({'products': products, 'graph': graph(),
                              'emptyProducts': agent('hiking boots under $1')['products']}),
            text=True, check=True, cwd=Path(__file__).resolve().parents[1],
        )
