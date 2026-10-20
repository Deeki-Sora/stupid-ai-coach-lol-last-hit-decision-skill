'use strict';
(()=>{
 const L=(zh,en)=>window.uiLang==='en'?en:zh;
 const command=(kind,scope)=>({annotation:scope==='all'?L('标注所有帧','annotate all frames'):L('标注当前帧','annotate current frame'),configuration:scope==='all'?L('填写所有帧配置','fill all frame configurations'):L('填写当前帧配置','fill current frame configuration'),strategy:L('查询工作台攻略','search workbench guides'),matchup:L('查询工作台胜率','fetch workbench matchup rates'),analysis:L('分析当前对局','analyze current match')}[kind]||L('处理工作台请求','process workbench request'));
 let revision=null,polling=false,batchBusy=false,lastRequest=null;
 const lockedControls=new Map();
 new MutationObserver(()=>{if(batchBusy)batchState(lastRequest)}).observe($('loadoutPanel'),{childList:true,subtree:true});
 function batchState(current){
  lastRequest=current;
  let busy=['annotation','configuration'].includes(current.kind)&&current.scope==='all'&&['pending','partial','running'].includes(current.status);
  window.skillBatchBusy=batchBusy=busy;
  if(busy){
   for(let node of document.querySelectorAll('#loadoutPanel input,#loadoutPanel select,#loadoutPanel button,#loadoutPanel textarea,#action input,#action select,#action textarea,#gameClock,#refreshFrame,#reloadAssistant,#reloadMechanics,#askAssistant,#askFrameSkill,#askAllSkill,#askConfigFrameSkill,#askConfigAllSkill,#askMechanicsAssistant,#runAnalysis,#save,#export,#hideUnit,#restoreUnit,#deadUnit,#deleteUnit')){if(!lockedControls.has(node))lockedControls.set(node,node.disabled);node.disabled=true}
   message(current.status==='running'?L('Skill 正在处理所有帧，完成或取消后可刷新和编辑。','The Skill is processing all frames. Refresh and editing resume after completion or cancellation.'):L('请求已保存，请在 AI 工具对话中输入：','Request saved. Enter this in your AI conversation: ')+command(current.kind,current.scope)+L('。等待处理期间，刷新和编辑暂不可用。','. Refresh and editing are paused until completion or cancellation.'));
  }else{for(let [node,disabled] of lockedControls)if(node.isConnected)node.disabled=disabled;lockedControls.clear()}
  for(let node of document.querySelectorAll('.cancelSkillRequest'))node.disabled=!['pending','partial','running'].includes(current.status);
 }
 window.addEventListener('beforeunload',event=>{if(batchBusy){event.preventDefault();event.returnValue=''}});
 document.querySelectorAll('.cancelSkillRequest').forEach(node=>node.onclick=async()=>{try{let wasBatch=batchBusy,current=await api('/api/assistant-cancel',{});revision=current.revision;batchState(current);if(wasBatch){dirty=false;await reload()}let text=L('已取消 Skill 请求，已保存的草稿保留。','Skill request cancelled; saved drafts are retained.');message(text);if(current.kind==='analysis')$('analysisStatus').textContent=text}catch(e){message(e.message)}});

 function renderReport(markdown){let container=$('analysisReport');container.replaceChildren();let table=null;for(let line of markdown.split('\n')){if(/^\|[- :|]+\|$/.test(line))continue;if(line.startsWith('|')){if(!table){table=document.createElement('table');container.append(table)}let row=document.createElement('tr');for(let cell of line.split('|').slice(1,-1)){let element=document.createElement(table.children.length?'td':'th');element.textContent=cell.trim();row.append(element)}table.append(row);continue}table=null;if(!line.trim())continue;let heading=line.match(/^(#{1,3})\s+(.*)/),node=document.createElement(heading?'h3':'p');node.textContent=heading?heading[2]:line;container.append(node)}}
 async function refreshAnalysis(){let language=window.uiLang==='en'?'en':'zh',data=await api('/api/analysis-report?language='+language);if(data.markdown){renderReport(data.markdown);$('analysisDownload').hidden=false;$('analysisDownload').href=url('/assessment/analysis_report_'+language+'.md');$('analysisDownload').textContent=L('下载分析报告（MD）','Download report (MD)')}else $('analysisReport').replaceChildren()}
 $('runAnalysis').onclick=async()=>{
  let button=$('runAnalysis'),requestedFrameId=frame().id;button.disabled=true;
  try{
   $('analysisStatus').textContent=L('正在保存证据并生成评估包…','Saving evidence and preparing the assessment bundle…');
   $('analysisReport').replaceChildren();
   await window.flushPendingLoadoutState?.();await save();
   let result=await api('/api/request-analysis',{frame_id:requestedFrameId,language:window.uiLang});
   revision=result.request.revision;
   $('analysisDownload').hidden=false;$('analysisDownload').href=url('/'+result.bundle);
   $('analysisDownload').textContent=L('\u4e0b\u8f7d\u8bc4\u4f30\u5305','Download assessment bundle');
   $('analysisStatus').textContent=L('评估包已准备好。请在 AI 工具对话中输入“分析当前对局”；Skill 分析并回填后，刷新本页查看报告。','Assessment bundle ready. Enter "analyze current match" in your AI conversation. Refresh this page after the Skill saves the report.');
  }catch(e){$('analysisStatus').textContent=e.message}finally{button.disabled=false}
 };

 function message(text){$('assistantStatus').textContent=text;$('configAssistantStatus').textContent=text}
 async function mechanics(){let data=await api('/api/mechanics-workspace',{});estimatedModels=data.models;$('mechanicsStatus').textContent=L('已自动载入工作区观察表。独立观察机会：','Workspace observations loaded. Distinct opportunities: ')+(data.models.coverage?.unique_opportunities||0);return data}
 async function request(kind,scope='current'){
  if(batchBusy)throw Error(L('请等待当前批量任务完成，或先取消任务。','Wait for the active batch task or cancel it first.'));
  let requestedFrameId=frame().id;
  await window.flushPendingLoadoutState?.();await save();
  if(kind==='configuration'&&!p.configuration)throw Error(L('请先选择版本和双方英雄并保存全局配置。','Save the patch and fixed champion setup first.'));
  let result=await api('/api/assistant-request',{frame_id:requestedFrameId,kind,scope,language:window.uiLang});revision=result.revision;batchState(result);
  if(!batchBusy)message(L('请求已准备好。请在 AI 工具对话中输入：','Request ready. Enter this in your AI conversation: ')+command(kind,scope)+L('。Skill 回填后刷新工作台查看并复核。','. Refresh the workbench after the Skill saves the results.'));
  $('assistantPanel').open=true;return result;
 }
 async function reload(){if(dirty)throw Error(L('请先保存当前填写内容，再载入识别结果。','Save your edits before loading recognition results.'));let state=await api('/api/state');a=state.annotations;p.units=state.project.units;await window.reloadLoadoutConfiguration?.(state.project.configuration);let selected=$('unit').value;options();if(p.units.some(u=>u.id===selected))$('unit').value=selected;loadFields();updateFrameLabel();dirty=false;message(L('识别结果已载入，标为待复核。请检查坐标、动作及血量后确认。','Recognition results loaded as unreviewed drafts. Check centers, actions and HP before confirming.'));await mechanics()}
 $('askAssistant').onclick=()=>request('annotation').catch(e=>message(e.message));
 $('askFrameSkill').onclick=()=>request('annotation').catch(e=>message(e.message));
 $('askAllSkill').onclick=()=>request('annotation','all').catch(e=>message(e.message));
 $('askConfigFrameSkill').onclick=()=>request('configuration').catch(e=>message(e.message));
 $('askConfigAllSkill').onclick=()=>request('configuration','all').catch(e=>message(e.message));
 $('askMechanicsAssistant').onclick=()=>request('mechanics').then(()=>{$('mechanicsStatus').textContent=$('assistantStatus').textContent}).catch(e=>{$('mechanicsStatus').textContent=e.message});
 $('reloadAssistant').onclick=()=>reload().catch(e=>message(e.message));
 $('reloadMechanics').onclick=()=>mechanics().catch(e=>{$('mechanicsStatus').textContent=e.message});
 $('confirmAssistant').onclick=async()=>{try{apply();let count=0;for(let [uid,value] of Object.entries(ann().units||{}))if(value.ai_evidence){value.reviewed=true;let unit=p.units.find(u=>u.id===uid);if(unit?.roster_reviewed===false)unit.roster_reviewed=true;count++}if(ann().game_time_s!=null)ann().game_time_reviewed=true;await save();message(L('已确认当前帧的 AI 识别结果：','AI results confirmed for this frame: ')+count)}catch(e){message(e.message)}};
 for(let input of $('action').querySelectorAll('input,select'))input.addEventListener('input',()=>{dirty=true});
 window.workbenchReady.then(async()=>{try{await mechanics();await refreshAnalysis();let current=await api('/api/assistant-status',{});revision=current.revision;batchState(current)}catch(e){$('mechanicsStatus').textContent=e.message}});
 window.addEventListener('languagechange',()=>{refreshAnalysis().catch(e=>{$('analysisStatus').textContent=e.message});window.refreshStrategyReference?.().catch(e=>message(e.message))});
 setInterval(async()=>{
  if(polling||!p)return;polling=true;
  try{
   let current=await api('/api/assistant-status',{}),wasBatch=batchBusy;batchState(current);
   if(batchBusy)return;
   if(['filled','partial'].includes(current.status)&&current.revision!==revision){
    if(!wasBatch&&(dirty||document.activeElement?.matches('input,select,textarea')))return;
    if(wasBatch)dirty=false;
    await reload();await refreshAnalysis();await window.refreshStrategyReference?.();await window.refreshMatchupPrior?.();revision=current.revision;
    if(current.scope==='all'&&['annotation','configuration'].includes(current.kind))message(L('所有帧已处理完成。请查看 Skill 对话中的未知项和复核说明；现在可以刷新页面。','All frames are processed. See the Skill conversation for unknowns and review notes; refresh is now available.'));
    else if(current.status==='partial')message(L('已载入部分结果，尚有未处理帧：','Partial results loaded; remaining frames: ')+current.remaining_frames.length);
   }
  }catch(e){message(e.message)}finally{polling=false}
 },2000);
})();
