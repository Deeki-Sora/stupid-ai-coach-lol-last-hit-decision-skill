'use strict';
(()=>{
 const L=(zh,en)=>window.uiLang==='en'?en:zh;
 async function update(operation){
  if(window.skillBatchBusy)return;
  let uid=$('unit').value;
  if(operation==='delete'&&!confirm(L('删除此误建单位及整段录像中的相关标注？修改前会自动备份。','Delete this mistaken unit and its annotations throughout the recording? A backup will be saved first.')))return;
  await save();
  let result=await api('/api/unit-update',{unit_id:uid,frame_id:frame().id,operation});
  p=result.project;a=result.annotations;options();loadFields();dirty=false;
  status(L('已更新单位；历史备份：','Unit updated; backup: ')+result.backup);
 }
 for(let [id,operation] of [['hideUnit','hide'],['restoreUnit','restore'],['deadUnit','death'],['deleteUnit','delete']]){
  $(id).onclick=()=>update(operation).catch(e=>status(e.message));
 }
})();
