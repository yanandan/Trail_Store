// Browser-only retrieval agent. No network, credentials or language model.
function localAgent(message, category = 'All') {
  if (typeof message !== 'string' || !message.trim() || message.length > 2000) throw Error('Enter a request of 1–2000 characters');
  const text = message.toLowerCase();
  const aliases = {hiking:['hike','hiking','day walk'],backpacking:['backpacking','multi-day','overnight'],running:['running','run'],camping:['camping','camp']};
  const activities = Object.keys(aliases).filter(k => aliases[k].some(t => text.includes(t)));
  const weatherAliases = {rain:['rain','wet','waterproof'],cold:['cold','winter','warm'],wind:['wind'],dry:['dry','sunny']};
  const weather = Object.keys(weatherAliases).filter(k => weatherAliases[k].some(t => text.includes(t)));
  const match = text.match(/(?:under|below|budget(?:\s+of)?|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d{1,2})?)|\$(\d+(?:\.\d{1,2})?)/);
  const budget = match ? Number(match[1] || match[2]) : null;
  let requested = category;
  if (requested === 'All') {
    const categories = {Footwear:['shoes','boots','footwear'],Packs:['backpack ','pack ','packs'],Apparel:['jacket','shell','fleece','apparel'],Shelter:['tent','shelter']};
    for (const [cat, words] of Object.entries(categories)) if (words.some(w => text.includes(w))) {requested=cat;break;}
  }
  // Match the server's conservative catalog vocabulary; never ignore unknown terms.
  const vocabulary = catalog.products.map(p=>[p.name,p.category,...p.activities,...p.features,...p.weather].join(' ')).join(' ')+' '+Object.values(aliases).flat().join(' ')+' i me my we our a an the for to in on with and or of is it please find show recommend want need looking buy get some any gear equipment product products item items under below budget up max maximum dollar dollars cost price than less day walk wet waterproof winter warm windy rainy sunny jacket backpack pack footwear apparel shelter lightweight';
  const normalize=word=>word.endsWith('s')?word.slice(0,-1):word;
  const known=new Set((vocabulary.toLowerCase().match(/[a-z]+/g)||[]).map(normalize));
  const unsupported=[...new Set((text.match(/[a-z]+/g)||[]).filter(word=>!known.has(normalize(word))))].sort();
  const trace = [{tool:'plan_request',detail:`Activity: ${activities.join(', ')||'any'} · Weather: ${weather.join(', ')||'any'} · Category: ${requested} · Per-item budget: ${budget===null?'not set':'$'+budget}`}];
  const candidates = unsupported.length?[]:catalog.products.filter(p => (requested==='All'||p.category===requested) && (!activities.length||activities.some(a=>p.activities.includes(a))) && weather.every(w=>p.weather.includes(w)));
  trace.push({tool:'query_knowledge_graph',detail:`Traversed SUITED_FOR, SUITS_WEATHER and IN_CATEGORY edges; found ${candidates.length} matching products.`});
  const available = candidates.filter(p=>p.stock>0&&(budget===null||p.price<=budget));
  trace.push({tool:'check_inventory_and_price',detail:`${available.length} products in stock and within the per-item budget. No constraints were relaxed.`});
  const score=p=>p.features.filter(f=>text.includes(f)).length;
  available.sort((a,b)=>score(b)-score(a)||a.price-b.price);
  const products=available.slice(0,4).map(p=>({...p,evidence:catalog.graph.edges.filter(e=>e.source===p.id&&(e.relation==='IN_CATEGORY'||activities.map(a=>'activities:'+a).concat(weather.map(w=>'weather:'+w)).includes(e.target))),reason:[...activities.filter(a=>p.activities.includes(a)).map(a=>'Suited for '+a),...weather.map(w=>'Suitable for '+w),p.stock+' in stock','$'+p.price].join('; ')}));
  trace.push({tool:'explain_recommendations',detail:`Returned ${products.length} recommendations with graph evidence. Inventory and prices are sample data.`});
  let answer=products.length?'Here are the strongest matches from our sample catalog. Your budget applies to each item, not a complete kit.':'No in-stock products match all those constraints. Try a higher per-item budget or a different category or weather condition.';
  if(unsupported.length)answer='No catalog match for: '+unsupported.join(', ')+'. This local demo only supports the products and terms in its sample catalog.';
  if(!activities.length)answer+=' Tell me your activity for more focused recommendations.';
  return {answer,products,trace,constraints:{activities,weather,budget,category:requested},mode:'Browser-only tool agent · no language model'};
}
