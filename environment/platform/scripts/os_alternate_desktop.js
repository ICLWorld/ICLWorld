/* Aurora: a tabbed desktop with a searchable application shelf, same state transport. */
function installAlternateDesktop(){
  if(!session)return;
  let shelf=document.getElementById('aurora-shelf');
  if(!shelf){shelf=document.createElement('aside');shelf.id='aurora-shelf';document.body.append(shelf);}
  const query=shelf.querySelector('input')?.value||'';
  shelf.innerHTML='<strong>AURORA</strong><small>Workspace</small><input aria-label="Find application" placeholder="Find application"><div class="aurora-apps"></div><h3>Open windows</h3><div class="aurora-tabs"></div>';
  const field=shelf.querySelector('input');field.value=query;
  function applicationList(){const container=shelf.querySelector('.aurora-apps');container.replaceChildren();
    for(const [id,label] of APPS){if(!label.toLowerCase().includes(field.value.toLowerCase()))continue;
      const button=document.createElement('button');button.textContent=label;button.onclick=()=>{
        const existing=windows.filter(w=>w.app===id).sort((a,b)=>b.z-a.z)[0];
        if(existing){existing.minimized=false;existing.z=++z;render();}else open(id);
      };container.append(button);
    }}
  field.oninput=applicationList;applicationList();
  for(const w of windows){const button=document.createElement('button');button.textContent=app(w.app)[1]+(w.app==='editor'&&file(w.fileId)?' · '+file(w.fileId).name:'');button.setAttribute('aria-pressed',String(w.z===z&&!w.minimized));button.onclick=()=>{w.minimized=false;w.z=++z;render();};shelf.querySelector('.aurora-tabs').append(button);}
}
const nativeRender=render;
render=function(){nativeRender();installAlternateDesktop();};
document.documentElement.dataset.environment='aurora';
installAlternateDesktop();
